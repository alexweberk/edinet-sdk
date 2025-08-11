import datetime
import logging
import os
import time
from typing import Any

import httpx

from src.config import (
    API_CSV_DOCUMENT_TYPE,
    API_TYPE_METADATA_AND_RESULTS,
    DEFAULT_DOWNLOAD_DIR,
    DELAY_SECONDS,
    EDINET_API_BASE_URL,
    EDINET_API_KEY,
    EDINET_DOCUMENT_API_BASE_URL,
    HTTP_CLIENT_ERROR_START,
    HTTP_SERVER_ERROR_END,
    HTTP_SUCCESS,
    MAX_RETRIES,
    SUPPORTED_DOC_TYPES,
)
from src.edinet.schemas import (
    EdinetConnectionError,
    EdinetDocumentFetchError,
    EdinetRetryExceededError,
    ValidationError,
)
from src.edinet.utils import handle_api_errors

# Use module-specific logger
logger = logging.getLogger(__name__)


class EdinetClient:
    """
    Simplified EDINET API client with minimal, reusable methods.

    Core Methods:
    - list_documents(): Search and filter document metadata for date/date range
    - get_document(): Download a single document by ID
    - download_documents(): Download multiple documents to local storage
    """

    def __init__(
        self,
        api_key: str | None = None,
        max_retries: int = MAX_RETRIES,
        delay_seconds: int = DELAY_SECONDS,
        download_dir: str = DEFAULT_DOWNLOAD_DIR,
        timeout: int = 30,
    ):
        """
        Initialize the EDINET client.

        Args:
            api_key: EDINET API key. If None, uses EDINET_API_KEY from config.
            max_retries: Maximum number of retry attempts for failed requests.
            delay_seconds: Delay between retry attempts in seconds.
            download_dir: Default directory for downloading documents.
            timeout: Request timeout in seconds.
        """
        self.api_key = api_key or EDINET_API_KEY
        self.max_retries = max_retries
        self.delay_seconds = delay_seconds
        self.download_dir = download_dir
        self.timeout = timeout
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        if not self.api_key:
            raise ValidationError("EDINET API key is required")

        # Ensure download directory exists
        os.makedirs(self.download_dir, exist_ok=True)
        self.logger.info(
            f"EdinetClient initialized with download directory: {self.download_dir}"
        )

    # PUBLIC METHODS

    @handle_api_errors
    def get_document(self, doc_id: str) -> bytes:
        """
        Download a single document by ID and return raw bytes.

        Args:
            doc_id: The ID of the document to download.

        Returns:
            The raw bytes of the document.

        Raises:
            EdinetDocumentFetchError: If document download fails.
        """
        url = f"{EDINET_DOCUMENT_API_BASE_URL}/documents/{doc_id}"
        params = {
            "type": API_CSV_DOCUMENT_TYPE,
            "Subscription-Key": self.api_key,
        }

        operation_name = f"download document {doc_id}"
        try:
            return self._make_request_with_retry(
                url, params, operation_name, return_content=True
            )
        except (EdinetConnectionError, EdinetRetryExceededError) as e:
            raise EdinetDocumentFetchError(str(e)) from e

    def list_documents(
        self,
        start_date: datetime.date,
        end_date: datetime.date | None = None,
        edinet_codes: list[str] | None = None,
        doc_type_codes: list[str] | None = None,
        excluded_doc_type_codes: list[str] | None = None,
        require_sec_code: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Search and filter document metadata for a single date or date range.

        Args:
            start_date: Start date (or single date if end_date is None).
            end_date: End date for range queries. If None, queries single date.
            edinet_codes: List of EDINET codes to filter by.
            doc_type_codes: List of document type codes to filter by.
            excluded_doc_type_codes: List of document type codes to exclude.
            require_sec_code: Whether to require a security code.

        Returns:
            List of document metadata dictionaries that match the criteria.
        """
        # Handle single date vs date range
        if end_date is None:
            end_date = start_date

        # Normalize filter parameters
        edinet_codes = edinet_codes or []
        doc_type_codes = doc_type_codes or []
        excluded_doc_type_codes = excluded_doc_type_codes or []

        matching_docs = []
        current_date = start_date

        while current_date <= end_date:
            try:
                docs_res = self._fetch_documents_for_date(current_date)
                if docs_res and docs_res.get("results"):
                    self.logger.info(
                        f"Found {len(docs_res['results'])} documents for {current_date}"
                    )
                    filtered_docs = self._filter_documents(
                        docs_res["results"],
                        edinet_codes,
                        doc_type_codes,
                        excluded_doc_type_codes,
                        require_sec_code,
                    )
                    matching_docs.extend(filtered_docs)
                    self.logger.info(
                        f"Added {len(filtered_docs)} matching documents for {current_date}"
                    )
                else:
                    self.logger.info(f"No documents found for {current_date}")

            except Exception as e:
                self.logger.error(f"Error processing documents for {current_date}: {e}")
            finally:
                current_date += datetime.timedelta(days=1)

        self.logger.info(f"Retrieved {len(matching_docs)} total matching documents")
        return matching_docs

    def download_documents(
        self,
        docs: list[dict[str, Any]],
        download_dir: str | None = None,
    ) -> None:
        """
        Download all documents in the provided list.

        Args:
            docs: List of document dictionaries to download.
            download_dir: Directory to save documents. If None, uses instance default.
        """
        target_dir = download_dir or self.download_dir
        os.makedirs(target_dir, exist_ok=True)

        total_docs = len(docs)
        self.logger.info(f"Downloading {total_docs} documents to {target_dir}")

        for i, doc in enumerate(docs, 1):
            doc_id = doc.get("docID")
            doc_type_code = doc.get("docTypeCode")
            filer = doc.get("filerName")

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
                doc_content = self.get_document(doc_id)
                self.save_bytes(filepath, doc_content)
            except Exception as e:
                self.logger.error(f"Failed to download {filename}: {e}")

        self.logger.info("Download complete")

    def save_bytes(self, filepath: str, data: bytes) -> None:
        """
        Save bytes data to a file with error handling.

        Args:
            filepath: Path where the file should be saved.
            data: Raw bytes data to save.

        Raises:
            OSError: If file writing fails.
        """
        try:
            with open(filepath, "wb") as f:
                f.write(data)
            self.logger.info(f"Saved file: {filepath}")
        except Exception as e:
            self.logger.error(f"Error saving file {filepath}: {e}")
            raise

    # PRIVATE METHODS

    @handle_api_errors
    def _fetch_documents_for_date(
        self,
        date: str | datetime.date,
        api_type: int = int(API_TYPE_METADATA_AND_RESULTS),
    ) -> dict[str, Any]:
        """
        Internal method to retrieve documents from EDINET API for a single date.
        """
        date_str = self._validate_date(date)

        url = f"{EDINET_API_BASE_URL}/documents.json"
        params = {
            "date": date_str,
            "type": str(api_type),
            "Subscription-Key": self.api_key,
        }

        operation_name = f"fetch documents for {date_str}"
        return self._make_request_with_retry(url, params, operation_name)

    def _filter_documents(
        self,
        docs: list[dict[str, Any]],
        edinet_codes: list[str],
        doc_type_codes: list[str],
        excluded_doc_type_codes: list[str],
        require_sec_code: bool,
    ) -> list[dict[str, Any]]:
        """
        Internal method to filter documents by criteria.
        """
        filtered_list = []
        for doc in docs:
            # Validate required fields
            if not all(key in doc for key in ["docID", "docTypeCode", "filerName"]):
                self.logger.warning(f"Skipping document with incomplete metadata")
                continue

            # Check supported document types
            if doc["docTypeCode"] not in SUPPORTED_DOC_TYPES:
                continue

            # Apply filters
            if edinet_codes and doc.get("edinetCode") not in edinet_codes:
                continue
            if doc_type_codes and doc["docTypeCode"] not in doc_type_codes:
                continue
            if doc["docTypeCode"] in excluded_doc_type_codes:
                continue
            if require_sec_code and doc.get("secCode") is None:
                continue

            filtered_list.append(doc)

        return filtered_list

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

    def _make_request_with_retry(
        self,
        url: str,
        params: dict[str, str],
        operation_name: str,
        return_content: bool = False,
    ) -> Any:
        """
        Make HTTP request with retry logic and error handling.

        Args:
            url: The URL to make the request to.
            params: Query parameters for the request.
            operation_name: Name of the operation for logging purposes.
            return_content: If True, return raw bytes; otherwise return JSON.

        Returns:
            JSON response as dict or raw bytes content.

        Raises:
            EdinetConnectionError: If connection fails after all retries.
            EdinetRetryExceededError: If retry limit is exceeded.
        """
        for attempt in range(self.max_retries):
            try:
                self.logger.info(f"Attempt {attempt + 1} for {operation_name}...")

                with httpx.Client(timeout=self.timeout) as client:
                    response = client.get(url, params=params)

                    if response.status_code != HTTP_SUCCESS:
                        self.logger.error(
                            f"API returned status code {response.status_code} for {operation_name}"
                        )

                        try:
                            error_body = response.text
                            self.logger.error(f"Error body: {error_body}")
                        except Exception:
                            pass

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
                        self.logger.info(f"Successfully completed {operation_name}")
                        return content
                    else:
                        data = response.json()
                        self.logger.info(f"Successfully completed {operation_name}")
                        return data

            except httpx.HTTPError as e:
                self.logger.error(f"HTTP Error in {operation_name}: {e}")
                if attempt < self.max_retries - 1:
                    self.logger.warning(f"Retrying in {self.delay_seconds}s...")
                    time.sleep(self.delay_seconds)
                else:
                    self.logger.error(f"Max retries reached for {operation_name}")
                    raise EdinetConnectionError(
                        f"Failed {operation_name} after {self.max_retries} attempts"
                    ) from e

            except Exception as e:
                self.logger.error(f"Unexpected error in {operation_name}: {e}")
                if attempt < self.max_retries - 1:
                    self.logger.warning(f"Retrying in {self.delay_seconds}s...")
                    time.sleep(self.delay_seconds)
                else:
                    self.logger.error(f"Max retries reached for {operation_name}")
                    raise EdinetConnectionError(
                        f"Failed {operation_name} after {self.max_retries} attempts"
                    ) from e

        raise EdinetRetryExceededError(
            f"Failed {operation_name} after multiple retries"
        )
