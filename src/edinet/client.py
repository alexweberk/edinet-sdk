import datetime
import logging
import os
import time
from pathlib import Path
from typing import Any

import httpx

from src.config import (
    API_CSV_DOCUMENT_TYPE,
    API_TYPE_METADATA_AND_RESULTS,
    DAYS_BACK,
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
from src.edinet.utils import handle_api_errors
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
    - list_docs(): Search and filter document metadata for date/date range
    - get_doc(): Download a single document by ID
    - download_documents(): Download multiple documents to local storage
    - save_bytes(): Save bytes data to a file with error handling

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
    def list_docs(
        self,
        start_date: datetime.date,
        end_date: datetime.date | None = None,
        edinet_codes: list[str] | None = None,
        doc_type_codes: list[str] | None = None,
        excluded_doc_type_codes: list[str] | None = None,
        require_sec_code: bool = False,
    ) -> list[FilingMetadata]:
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
                if isinstance(docs_res, EdinetErrorResponse):
                    raise EdinetAuthenticationError(
                        f"Error fetching documents for {current_date}: {docs_res}. Errors: {docs_res.message}"
                    )

                if docs_res and docs_res.results:
                    self.logger.info(
                        f"Found {len(docs_res.results)} documents for {current_date}"
                    )
                    filtered_docs = self._filter_documents(
                        docs_res.results,
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

            except EdinetAuthenticationError:
                # Re-raise authentication errors immediately to stop execution
                raise
            except Exception as e:
                self.logger.error(f"Error processing documents for {current_date}: {e}")
            finally:
                current_date += datetime.timedelta(days=1)

        self.logger.info(f"Retrieved {len(matching_docs)} total matching documents")
        return matching_docs

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
        url = f"{EDINET_DOCUMENT_API_BASE_URL}/documents/{doc_id}"
        params = {
            "type": API_CSV_DOCUMENT_TYPE,
            "Subscription-Key": self.api_key,
        }

        operation_name = f"get zip bytes for {doc_id}"
        zip_bytes = self._make_request_with_retry(
            url,
            params,
            operation_name,
            return_content=True,
        )
        if not zip_bytes:
            raise EdinetDocumentFetchError(f"Failed to fetch zip bytes for {doc_id}.")
        return zip_bytes

    def download_documents(
        self,
        filing_metadatas: list[FilingMetadata],
        download_dir: str | None = None,
    ) -> None:
        """
        Download all documents in the provided list.

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
            except Exception as e:
                self.logger.error(f"Failed to download {filename}: {e}")

        self.logger.info("Download complete")

    def get_most_recent_documents(
        self,
        doc_type_codes: list[str],
        days_back: int = DAYS_BACK,
        edinet_codes: list[str] | None = None,
        excluded_doc_type_codes: list[str] | None = None,
        require_sec_code: bool = True,
    ) -> tuple[list[FilingMetadata], datetime.date | None]:
        """
        Fetch documents from the most recent day with filings within a date range.
        Searches back day by day up to `days_back`.

        Args:
            doc_type_codes: List of document type codes to filter by.
            days_back: Number of days to search back.
            edinet_codes: List of EDINET codes to filter by.
            excluded_doc_type_codes: List of document type codes to exclude.
            require_sec_code: Whether to require a security code.

        Returns:
            Tuple containing a list of documents and the date of the most recent documents found.
        """
        current_date = datetime.date.today()
        end_date = current_date  # Search up to today
        start_date = current_date - datetime.timedelta(
            days=days_back
        )  # Search back up to days_back

        self.logger.info(
            f"Searching for documents in the last {days_back} days ({start_date} to {end_date})..."
        )

        # Iterate backwards day by day from end_date to start_date
        date_to_check = end_date
        while date_to_check >= start_date:
            self.logger.info(f"Fetching documents for {date_to_check}...")
            try:
                # Get documents for a single date
                docs = self.list_docs(
                    start_date=date_to_check,
                    end_date=date_to_check,
                    doc_type_codes=doc_type_codes,
                    edinet_codes=edinet_codes,
                    excluded_doc_type_codes=excluded_doc_type_codes,
                    require_sec_code=require_sec_code,
                )

                if docs:
                    self.logger.info(
                        f"Found {len(docs)} documents for {date_to_check}. Processing these."
                    )

                    return (
                        docs,
                        date_to_check,  # Return documents for the first day with results
                    )

                self.logger.info(
                    f"No documents found for {date_to_check}. Trying previous day."
                )
                date_to_check -= datetime.timedelta(days=1)

            except Exception as e:
                self.logger.error(f"Error fetching documents for {date_to_check}: {e}")
                # Continue to previous day even if one date fails

        self.logger.warning(
            f"No documents found in the last {days_back} days matching criteria."
        )
        return [], None

    # def get_structured_data_directly_from_api(
    #     self,
    #     doc_id: str,
    #     doc_type_code: str,
    # ) -> dict[str, Any] | None:
    #     """
    #     Fetch a document from the API and process it directly in memory without saving temporary files.

    #     Args:
    #         doc_id: EDINET document ID.
    #         doc_type_code: EDINET document type code.

    #     Returns:
    #         Structured dictionary of the document's data, or None if processing failed.
    #     """
    #     from src.processors.base_processor import BaseProcessor

    #     try:
    #         # Fetch document bytes from API
    #         doc_bytes = self.get_doc(doc_id)

    #         # Process directly in memory
    #         return BaseProcessor.zip_bytes_to_filename_records(doc_bytes, doc_id)

    #     except Exception as e:
    #         self.logger.error(f"Error fetching and processing document {doc_id}: {e}")
    #         return None

    # def get_structured_data_for_company_date_range(
    #     self,
    #     edinet_code: str,
    #     start_date: datetime.date | str,
    #     end_date: datetime.date | str,
    #     doc_type_codes: list[str] | None = None,
    #     excluded_doc_type_codes: list[str] | None = None,
    #     require_sec_code: bool = True,
    #     download_dir: str | None = None,
    # ) -> list[dict[str, Any]]:
    #     """Return structured data for filings by one company within a date range.

    #     Validates dates (YYYY-MM-DD if str), ensures start_date <= end_date,
    #     fetches documents via list_docs filtered by the given edinet_code,
    #     downloads ZIPs to a target directory (create a subdir if download_dir is None),
    #     and converts ZIPs to structured dicts using BaseProcessor.process_zip_directory.

    #     Args:
    #         edinet_code: EDINET code for the company to fetch documents for
    #         start_date: Start date for the date range (datetime.date or YYYY-MM-DD string)
    #         end_date: End date for the date range (datetime.date or YYYY-MM-DD string)
    #         doc_type_codes: Optional list of document type codes to include
    #         excluded_doc_type_codes: Optional list of document type codes to exclude
    #         require_sec_code: Whether to require a security code (default: True)
    #         download_dir: Directory to download files to (auto-generated if None)

    #     Returns:
    #         List of structured dictionaries (one per processed document).
    #     """
    #     from src.processors.base_processor import BaseProcessor

    #     # Parse and validate dates
    #     if isinstance(start_date, str):
    #         try:
    #             start_date_parsed = datetime.datetime.strptime(
    #                 start_date, "%Y-%m-%d"
    #             ).date()
    #         except ValueError as e:
    #             raise ValueError(
    #                 f"Invalid start_date format. Use 'YYYY-MM-DD'. Got: {start_date}"
    #             ) from e
    #     else:
    #         start_date_parsed = start_date

    #     if isinstance(end_date, str):
    #         try:
    #             end_date_parsed = datetime.datetime.strptime(
    #                 end_date, "%Y-%m-%d"
    #             ).date()
    #         except ValueError as e:
    #             raise ValueError(
    #                 f"Invalid end_date format. Use 'YYYY-MM-DD'. Got: {end_date}"
    #             ) from e
    #     else:
    #         end_date_parsed = end_date

    #     # Validate date range
    #     if start_date_parsed > end_date_parsed:
    #         raise ValueError(
    #             f"start_date ({start_date_parsed}) must be <= end_date ({end_date_parsed})"
    #         )

    #     self.logger.info(
    #         f"Fetching documents for EDINET code {edinet_code} from {start_date_parsed} to {end_date_parsed}"
    #     )

    #     # Create download directory if not provided
    #     if download_dir is None:
    #         download_dir = (
    #             f"downloads/company-{edinet_code}-{start_date_parsed}_{end_date_parsed}"
    #         )

    #     os.makedirs(download_dir, exist_ok=True)
    #     self.logger.info(f"Using download directory: {download_dir}")

    #     # Fetch documents for the company within the date range
    #     docs_metadata = self.list_docs(
    #         start_date=start_date_parsed,
    #         end_date=end_date_parsed,
    #         edinet_codes=[edinet_code],  # Filter by single EDINET code
    #         doc_type_codes=doc_type_codes,
    #         excluded_doc_type_codes=excluded_doc_type_codes,
    #         require_sec_code=require_sec_code,
    #     )

    #     if not docs_metadata:
    #         self.logger.info(
    #             f"No documents found for EDINET code {edinet_code} in the specified date range"
    #         )
    #         return []

    #     self.logger.info(f"Found {len(docs_metadata)} documents for {edinet_code}")

    #     # Download the documents
    #     self.download_documents(docs_metadata, download_dir)

    #     # Process the downloaded zip files into structured data
    #     # Use all supported document types for processing
    #     structured_document_data_list = BaseProcessor.process_zip_directory(
    #         download_dir, doc_type_codes=list(SUPPORTED_DOC_TYPES.keys())
    #     )

    #     self.logger.info(
    #         f"Successfully processed {len(structured_document_data_list)} documents for {edinet_code}"
    #     )

    #     return structured_document_data_list

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
        except Exception as e:
            self.logger.error(f"Error saving file {filepath}: {e}")
            raise

    # PRIVATE METHODS

    @handle_api_errors
    def _fetch_documents_for_date(
        self,
        date: str | datetime.date,
        api_type: int = int(API_TYPE_METADATA_AND_RESULTS),
    ) -> EdinetSuccessResponse | EdinetErrorResponse:
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

        response = self._make_request_with_retry(url, params, operation_name)

        if "results" not in response.keys():
            return EdinetErrorResponse.model_validate(response)

        return EdinetSuccessResponse.model_validate(response)

    def _filter_documents(
        self,
        docs: list[FilingMetadata],
        edinet_codes: list[str],
        doc_type_codes: list[str],
        excluded_doc_type_codes: list[str],
        require_sec_code: bool,
    ) -> list[FilingMetadata]:
        """
        Internal method to filter documents by criteria.
        """
        filtered_list = []
        for doc in docs:
            # Validate required fields
            if not all(
                key in doc.model_dump() for key in ["docID", "docTypeCode", "filerName"]
            ):
                self.logger.warning("Skipping document with incomplete metadata")
                continue

            # Check supported document types
            if doc.docTypeCode not in SUPPORTED_DOC_TYPES:
                continue

            # Apply filters
            if edinet_codes and doc.edinetCode not in edinet_codes:
                continue
            if doc_type_codes and doc.docTypeCode not in doc_type_codes:
                continue
            if doc.docTypeCode in excluded_doc_type_codes:
                continue
            if require_sec_code and doc.secCode is None:
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
