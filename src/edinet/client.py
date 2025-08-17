import datetime
import logging
import os
import time
from pathlib import Path
from typing import Any

import httpx

from src.cache import CacheManager
from src.config import (
    API_CSV_DOCUMENT_TYPE,
    API_TYPE_METADATA_AND_RESULTS,
    CACHE_DIR,
    CACHE_ENABLED,
    CACHE_TTL_DOCUMENTS,
    CACHE_TTL_FILINGS,
    DEFAULT_DOWNLOAD_DIR,
    DELAY_SECONDS,
    EDINET_API_BASE_URL,
    EDINET_DOCUMENT_API_BASE_URL,
    HTTP_CLIENT_ERROR_START,
    HTTP_SERVER_ERROR_END,
    HTTP_SUCCESS,
    MAX_RETRIES,
    validate_api_key,
)
from src.edinet.decorators import handle_api_errors
from src.edinet.funcs import filter_filings
from src.models import (
    EdinetAuthenticationError,
    EdinetConnectionError,
    EdinetDocumentFetchError,
    EdinetErrorResponse,
    EdinetRetryExceededError,
    EdinetSuccessResponse,
    Filing,
    FilingMetadata,
    ValidationError,
)
from src.processors.base_processor import BaseProcessor

# Use module-specific logger
logger = logging.getLogger(__name__)


class EdinetClient:
    """
    Simplified EDINET API client with minimal, reusable methods.

    Core Methods:
    - list_recent_filings(): Get recent filings metadata for the last N days.
    - list_filings(): Search and filter document metadata for date/date range
    - get_filing(): Download a single document by ID
    - download_filings(): Download multiple documents to local storage
    - save_bytes(): Save bytes data to a file with error handling

    """

    def __init__(
        self,
        api_key: str | None = None,
        max_retries: int = MAX_RETRIES,
        delay_seconds: int = DELAY_SECONDS,
        download_dir: str = DEFAULT_DOWNLOAD_DIR,
        timeout: int = 30,
        enable_cache: bool = CACHE_ENABLED,
        cache_dir: str = CACHE_DIR,
    ):
        """
        Initialize the EDINET client.

        Args:
            api_key: EDINET API key. If None, validates and uses EDINET_API_KEY environment variable.
            max_retries: Maximum number of retry attempts for failed requests.
            delay_seconds: Delay between retry attempts in seconds.
            download_dir: Default directory for downloading documents.
            timeout: Request timeout in seconds.
            enable_cache: Whether to enable response caching.
            cache_dir: Directory for cache files.
        """
        self.api_key = api_key or validate_api_key()

        # Validate numeric parameters
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if delay_seconds < 0:
            raise ValueError("delay_seconds must be non-negative")
        if timeout <= 0:
            raise ValueError("timeout must be positive")

        self.max_retries = max_retries
        self.delay_seconds = delay_seconds
        self.download_dir = download_dir
        self.timeout = timeout
        self.enable_cache = enable_cache
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Initialize cache manager if caching is enabled
        self.cache_manager = CacheManager(cache_dir) if enable_cache else None

        # Ensure download directory exists
        os.makedirs(self.download_dir, exist_ok=True)

        cache_status = "enabled" if enable_cache else "disabled"
        self.logger.info(
            f"EdinetClient initialized with download directory: {self.download_dir}, cache: {cache_status}"
        )

    # PUBLIC METHODS
    @handle_api_errors
    def list_recent_filings(
        self,
        lookback_days: int = 7,
        edinet_codes: list[str] | None = None,
        filing_type_codes: list[str] | None = None,
        excluded_filing_type_codes: list[str] | None = None,
        require_sec_code: bool = False,
        filer_names: list[str] | None = None,
    ) -> list[FilingMetadata]:
        """
        Get recent filings metadata for the last N days.

        Args:
            lookback_days: Number of days to look back from today (default: 7).
            edinet_codes: List of EDINET codes to filter by.
            filing_type_codes: List of document type codes to filter by.
            excluded_filing_type_codes: List of document type codes to exclude.
            require_sec_code: Whether to require a security code.
            filer_names: List of filer names to filter by.

        Returns:
            List of document metadata that match the criteria from the last N days.
        """
        # Validate lookback_days parameter
        if lookback_days <= 0:
            raise ValueError("lookback_days must be positive")

        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=lookback_days - 1)

        return self.list_filings(
            start_date=start_date,
            end_date=end_date,
            edinet_codes=edinet_codes,
            filing_type_codes=filing_type_codes,
            excluded_filing_type_codes=excluded_filing_type_codes,
            require_sec_code=require_sec_code,
            filer_names=filer_names,
        )

    @handle_api_errors
    def list_filings(
        self,
        start_date: datetime.date,
        end_date: datetime.date | None = None,
        edinet_codes: list[str] | None = None,
        filing_type_codes: list[str] | None = None,
        excluded_filing_type_codes: list[str] | None = None,
        require_sec_code: bool = False,
        filer_names: list[str] | None = None,
    ) -> list[FilingMetadata]:
        """
        Search and filter document metadata for a single date or date range.

        Args:
            start_date: Start date (or single date if end_date is None).
            end_date: End date for range queries. If None, queries single date.
            edinet_codes: List of EDINET codes to filter by.
            filing_type_codes: List of document type codes to filter by.
            excluded_filing_type_codes: List of document type codes to exclude.
            require_sec_code: Whether to require a security code.
            filer_names: List of filer names to filter by.

        Returns:
            List of document metadata dictionaries that match the criteria.
        """
        # Handle single date vs date range
        if end_date is None:
            end_date = start_date

        # Validate date range
        if start_date > end_date:
            raise ValueError("start_date must be <= end_date")

        # Normalize filter parameters - convert empty lists to None for proper filtering
        edinet_codes = edinet_codes or None
        filing_type_codes = filing_type_codes or None
        excluded_filing_type_codes = excluded_filing_type_codes or None

        matching_docs = []
        current_date = start_date

        while current_date <= end_date:
            try:
                docs_res = self._fetch_filings_for_date(current_date)
                if isinstance(docs_res, EdinetErrorResponse):
                    raise EdinetAuthenticationError(
                        f"Error fetching documents for {current_date}: {docs_res}. Errors: {docs_res.message}"
                    )

                if docs_res and docs_res.results:
                    self.logger.info(
                        f"Found {len(docs_res.results)} documents for {current_date}"
                    )

                    # Apply exclusion filter first (only logic not handled by filter_filings)
                    docs_to_filter = docs_res.results
                    if excluded_filing_type_codes:
                        docs_to_filter = [
                            doc
                            for doc in docs_to_filter
                            if doc.docTypeCode not in excluded_filing_type_codes
                        ]

                    # Handle require_sec_code since filter_filings doesn't support "require non-null"
                    if require_sec_code:
                        docs_to_filter = [
                            doc for doc in docs_to_filter if doc.secCode is not None
                        ]

                    # Use filter_filings for all other filtering
                    filtered_docs = filter_filings(
                        docs_to_filter,
                        edinet_codes=edinet_codes,
                        doc_type_codes=filing_type_codes,
                        filer_names=filer_names,
                    )

                    matching_docs.extend(filtered_docs)
                    self.logger.info(
                        f"Added {len(filtered_docs)} matching documents for {current_date}"
                    )
                else:
                    self.logger.info(f"No documents found for {current_date}")

            except EdinetAuthenticationError:
                # Re-raise authentication errors immediately to stop execution
                raise
            except (
                EdinetConnectionError,
                EdinetRetryExceededError,
                EdinetDocumentFetchError,
            ) as e:
                self.logger.error(
                    f"API error processing documents for {current_date}: {e}"
                )
            except (ValueError, TypeError) as e:
                self.logger.error(f"Data validation error for {current_date}: {e}")
            except Exception as e:
                self.logger.error(
                    f"Unexpected error processing documents for {current_date}: {e}"
                )
            finally:
                current_date += datetime.timedelta(days=1)

        self.logger.info(f"Retrieved {len(matching_docs)} total matching documents")
        return matching_docs

    def filter_filings(
        self,
        filings: list[FilingMetadata],
        **kwargs,
    ) -> list[FilingMetadata]:
        """
        Filter filings based on the given criteria.
        """
        return filter_filings(filings, **kwargs)

    @handle_api_errors
    def get_filing(self, filing_metadata: FilingMetadata) -> Filing | None:
        """
        Download a single document by ID and return raw bytes.

        Args:
            filing_metadata: The metadata of the document to download.

        Returns:
            A Filing object, which has the metadata and the files from the zip file,
            or None if the document does not exist.

        Raises:
            EdinetDocumentFetchError: If document download fails.
        """
        try:
            zip_bytes = self.get_zip_bytes(filing_metadata)
            filing = BaseProcessor.zip_bytes_to_filing(
                zip_bytes=zip_bytes,
                filing_metadata=filing_metadata,
            )
            return filing

        except (EdinetConnectionError, EdinetRetryExceededError) as e:
            raise EdinetDocumentFetchError(str(e)) from e

    @handle_api_errors
    def get_zip_bytes(self, filing_metadata: FilingMetadata) -> bytes:
        """
        Download a single document by ID and return raw bytes.
        """
        doc_id = filing_metadata.docID

        # Check cache first if enabled
        if self.cache_manager:
            cache_key = f"document:{doc_id}:{API_CSV_DOCUMENT_TYPE}"
            cached_bytes = self.cache_manager.get_binary(cache_key, CACHE_TTL_DOCUMENTS)
            if cached_bytes:
                self.logger.info(f"Cache hit for document {doc_id}")
                return cached_bytes

        url = f"{EDINET_DOCUMENT_API_BASE_URL}/documents/{doc_id}"
        params = {
            "type": API_CSV_DOCUMENT_TYPE,
            "Subscription-Key": self.api_key,
        }

        zip_bytes = self._fetch_with_retry(
            url,
            params,
            return_content=True,
        )
        if not zip_bytes:
            raise EdinetDocumentFetchError(f"Failed to fetch zip bytes for {doc_id}.")

        # Cache the result if caching is enabled
        if self.cache_manager:
            cache_key = f"document:{doc_id}:{API_CSV_DOCUMENT_TYPE}"
            if self.cache_manager.set_binary(cache_key, zip_bytes):
                self.logger.info(f"Cached document {doc_id}")

        return zip_bytes

    def download_filings(
        self,
        filing_metadatas: list[FilingMetadata],
        download_dir: str | None = None,
    ) -> None:
        """
        Download all filings in the provided list.

        Args:
            filing_metadatas: The metadata of the documents to download.
            download_dir: Directory to save documents. If None, uses instance default.
        """
        target_dir = download_dir or self.download_dir
        Path(target_dir).mkdir(parents=True, exist_ok=True)

        total_docs = len(filing_metadatas)
        self.logger.info(f"Downloading {total_docs} documents to {target_dir}")

        for i, filing_metadata in enumerate(filing_metadatas, 1):
            doc_id = filing_metadata.docID
            doc_type_code = filing_metadata.docTypeCode
            filer = filing_metadata.filerName

            if not all([doc_id, doc_type_code, filer]):
                self.logger.warning(
                    f"Skipping document {i}/{total_docs} - missing metadata"
                )
                continue

            filename = f"{doc_id}-{doc_type_code}-{filer}.zip"
            filepath = os.path.join(target_dir, filename)

            if os.path.exists(filepath):
                continue  # Skip if already downloaded

            self.logger.info(f"Downloading {i}/{total_docs}: {filename}")

            try:
                zip_bytes = self.get_zip_bytes(filing_metadata)
                self.save_bytes(zip_bytes, filepath)
            except (
                EdinetConnectionError,
                EdinetRetryExceededError,
                EdinetDocumentFetchError,
            ) as e:
                self.logger.error(f"API error downloading {filename}: {e}")
            except OSError as e:
                self.logger.error(f"File system error saving {filename}: {e}")
            except Exception as e:
                self.logger.error(f"Unexpected error downloading {filename}: {e}")

        self.logger.info("Download complete")

    def clear_cache(self) -> dict[str, int | str]:
        """
        Clear all cached data.

        Returns:
            Dictionary with cache clearing statistics.
        """
        if not self.cache_manager:
            return {"files_removed": 0, "message": "Caching is disabled"}

        files_removed = self.cache_manager.clear_all()
        self.logger.info(f"Cleared {files_removed} cache files")
        return {"files_removed": files_removed}

    def clear_expired_cache(self) -> dict[str, int | str]:
        """
        Clear only expired cache entries.

        Returns:
            Dictionary with cache clearing statistics.
        """
        if not self.cache_manager:
            return {"files_removed": 0, "message": "Caching is disabled"}

        files_removed = self.cache_manager.clear_expired()
        self.logger.info(f"Cleared {files_removed} expired cache files")
        return {"files_removed": files_removed}

    def get_cache_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics.
        """
        if not self.cache_manager:
            return {"message": "Caching is disabled"}

        return self.cache_manager.get_cache_stats()

    def save_bytes(self, data: bytes, filepath: str) -> None:
        """
        Save bytes data to a file with error handling.

        Args:
            data: Raw bytes data to save.
            filepath: Path where the file should be saved.

        Raises:
            OSError: If file writing fails.
        """
        try:
            with open(filepath, "wb") as f:
                f.write(data)
            self.logger.info(f"Saved file: {filepath}")
        except OSError as e:
            self.logger.error(f"File system error saving {filepath}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error saving file {filepath}: {e}")
            raise

    # PRIVATE METHODS

    @handle_api_errors
    def _fetch_filings_for_date(
        self,
        date: str | datetime.date,
        api_type: int = int(API_TYPE_METADATA_AND_RESULTS),
    ) -> EdinetSuccessResponse | EdinetErrorResponse:
        """
        Internal method to retrieve documents from EDINET API for a single date.
        """
        date_str = self._validate_date(date)

        # Check cache first if enabled
        if self.cache_manager:
            cache_key = f"filings:{date_str}:{api_type}"
            cached_response = self.cache_manager.get_json(cache_key, CACHE_TTL_FILINGS)
            if cached_response:
                self.logger.info(f"Cache hit for filings on {date_str}")
                # Return appropriate response type based on cached data
                if "results" in cached_response:
                    return EdinetSuccessResponse.model_validate(cached_response)
                else:
                    return EdinetErrorResponse.model_validate(cached_response)

        url = f"{EDINET_API_BASE_URL}/documents.json"
        params = {
            "date": date_str,
            "type": str(api_type),
            "Subscription-Key": self.api_key,
        }

        response = self._fetch_with_retry(url, params, return_content=False)

        # Cache the raw response if caching is enabled
        if self.cache_manager:
            cache_key = f"filings:{date_str}:{api_type}"
            if self.cache_manager.set_json(cache_key, response):
                self.logger.info(f"Cached filings for {date_str}")

        if "results" not in response.keys():
            return EdinetErrorResponse.model_validate(response)

        return EdinetSuccessResponse.model_validate(response)

    def _validate_date(self, date: str | datetime.date) -> str:
        """
        Validate and convert date to string format.

        Args:
            date: Date as string (YYYY-MM-DD) or datetime.date object.

        Returns:
            Date string in YYYY-MM-DD format.

        Raises:
            ValidationError: If date format is invalid.
        """
        if isinstance(date, str):
            try:
                datetime.datetime.strptime(date, "%Y-%m-%d")
                return date
            except ValueError as e:
                raise ValidationError(
                    f"Invalid date string. Use format 'YYYY-MM-DD'. Got: {date}"
                ) from e
        elif isinstance(date, datetime.date):
            return date.strftime("%Y-%m-%d")
        else:
            # This should never happen
            raise ValidationError(
                f"Date must be 'YYYY-MM-DD' string or datetime.date. Got: {type(date)}"
            )

    def _fetch_with_retry(
        self,
        url: str,
        params: dict[str, str],
        return_content: bool = False,
    ) -> Any:
        """
        Make HTTP request with retry logic and error handling.

        Args:
            url: The URL to make the request to.
            params: Query parameters for the request.
            return_content: If True, return raw bytes; otherwise return JSON.

        Returns:
            JSON response as dict or raw bytes content.

        Raises:
            EdinetConnectionError: If connection fails after all retries.
            EdinetRetryExceededError: If retry limit is exceeded.
        """
        for attempt in range(self.max_retries):
            try:
                self.logger.info(f"Attempt {attempt + 1} for {url}...")

                with httpx.Client(timeout=self.timeout) as client:
                    response = client.get(url, params=params)

                    if response.status_code != HTTP_SUCCESS:
                        self.logger.error(
                            f"API returned status code {response.status_code} for {url}"
                        )

                        try:
                            error_body = response.text
                            self.logger.error(f"Error body: {error_body}")
                        except (AttributeError, UnicodeDecodeError):
                            self.logger.warning("Could not decode error response body")

                        # Check if retryable error
                        if (
                            HTTP_CLIENT_ERROR_START
                            <= response.status_code
                            < HTTP_SERVER_ERROR_END
                            and attempt < self.max_retries - 1
                        ):
                            self.logger.warning(f"Retrying in {self.delay_seconds}s...")
                            time.sleep(self.delay_seconds)
                            continue
                        else:
                            response.raise_for_status()

                    if return_content:
                        content = response.content
                        self.logger.info(f"Successfully completed {url}")
                        return content
                    else:
                        data = response.json()
                        self.logger.info(f"Successfully completed {url}")
                        return data

            except httpx.HTTPError as e:
                self.logger.error(f"HTTP Error in {url}: {e}")
                if attempt < self.max_retries - 1:
                    self.logger.warning(f"Retrying in {self.delay_seconds}s...")
                    time.sleep(self.delay_seconds)
                else:
                    self.logger.error(f"Max retries reached for {url}")
                    raise EdinetConnectionError(
                        f"Failed {url} after {self.max_retries} attempts"
                    ) from e

            except (ValueError, TypeError, KeyError) as e:
                self.logger.error(f"Data processing error for {url}: {e}")
                if attempt < self.max_retries - 1:
                    self.logger.warning(f"Retrying in {self.delay_seconds}s...")
                    time.sleep(self.delay_seconds)
                else:
                    self.logger.error(f"Max retries reached for {url}")
                    raise EdinetConnectionError(
                        f"Failed {url} after {self.max_retries} attempts"
                    ) from e
            except Exception as e:
                self.logger.error(f"Unexpected error in {url}: {e}")
                if attempt < self.max_retries - 1:
                    self.logger.warning(f"Retrying in {self.delay_seconds}s...")
                    time.sleep(self.delay_seconds)
                else:
                    self.logger.error(f"Max retries reached for {url}")
                    raise EdinetConnectionError(
                        f"Failed {url} after {self.max_retries} attempts"
                    ) from e

        raise EdinetRetryExceededError(f"Failed {url} after multiple retries")
