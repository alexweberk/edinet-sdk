# document_processors.py
import io
import logging
import os
import re
import tempfile
import zipfile
from typing import Any

import chardet
import pandas as pd

from src.config import (
    AUDITOR_REPORT_PREFIX,
    CSV_ENCODING_DETECTION_BYTES,
    CSV_EXTENSION,
    CSV_SEPARATOR,
    MACOS_METADATA_DIR,
    TEXT_REPLACEMENTS,
    XBRL_ELEMENT_IDS,
    ZIP_EXTENSION,
)
from src.edinet.schemas import ErrorContext
from src.processors.schemas import StructuredDocData

logger = logging.getLogger(__name__)


def clean_text(text: str | None) -> str | None:
    """Clean and normalize text from disclosures."""
    if text is None:
        return None
    # replace full-width space with regular space
    text = text.replace(
        TEXT_REPLACEMENTS["FULL_WIDTH_SPACE"], TEXT_REPLACEMENTS["REGULAR_SPACE"]
    )
    # remove excessive whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # replace specific Japanese punctuation with Western equivalents for consistency
    # return text.replace('。', '. ').replace('、', ', ')
    return text


class BaseDocumentProcessor:
    """Base class for document specific data extraction."""

    def __init__(
        self,
        raw_csv_data: list[dict[str, Any]],
        doc_id: str,
        doc_type_code: str,
    ) -> None:
        """
        Initialize with raw data from CSV files and document metadata.

        Args:
            raw_csv_data: List of dictionaries, each containing 'filename' and 'data' (list of rows/dicts).
            doc_id: EDINET document ID.
            doc_type_code: EDINET document type code.
        """
        self.raw_csv_data = raw_csv_data
        self.doc_id = doc_id
        self.doc_type_code = doc_type_code
        # Combine all rows from all CSVs for easier querying
        self.all_records = self._combine_raw_data()

    @staticmethod
    def read_csv_file(file_path: str) -> list[dict[str, str | None]] | None:
        """Read a tab-separated CSV file trying multiple encodings."""
        try:
            # Detect encoding
            with open(file_path, "rb") as file:
                raw_data = file.read(CSV_ENCODING_DETECTION_BYTES)
            result = chardet.detect(raw_data)
            detected_encoding = result["encoding"]
        except OSError:
            detected_encoding = None

        # Try different encodings
        encodings = [detected_encoding] if detected_encoding else []
        encodings.extend(
            [
                "utf-16",
                "utf-16le",
                "utf-16be",
                "utf-8",
                "shift-jis",
                "euc-jp",
                "iso-8859-1",
                "windows-1252",
            ]
        )

        for encoding in list(dict.fromkeys(encodings)):  # Remove duplicates
            if not encoding:
                continue
            try:
                df = pd.read_csv(
                    file_path,
                    encoding=encoding,
                    sep=CSV_SEPARATOR,
                    dtype=str,
                    low_memory=False,
                )
                # Replace NaN with None
                df = df.replace({float("nan"): None, "": None})
                return df.to_dict(orient="records")  # type: ignore[return-value]
            except (
                UnicodeDecodeError,
                pd.errors.EmptyDataError,
                pd.errors.ParserError,
            ):
                continue
            except Exception:
                continue

        logger.error(
            f"Failed to read {file_path}. Unable to determine correct encoding."
        )
        return None

    @staticmethod
    def read_csv_from_bytes(
        csv_bytes: bytes, filename: str
    ) -> list[dict[str, str | None]] | None:
        """Read a tab-separated CSV from bytes trying multiple encodings."""

        # Common encodings for EDINET files
        encodings = [
            "utf-16",
            "utf-16le",
            "utf-16be",
            "utf-8",
            "shift-jis",
            "euc-jp",
            "iso-8859-1",
            "windows-1252",
        ]

        for encoding in encodings:
            try:
                # Create StringIO from decoded bytes
                csv_text = csv_bytes.decode(encoding)
                csv_io = io.StringIO(csv_text)

                # Use low_memory=False to avoid DtypeWarning on mixed types
                df = pd.read_csv(
                    csv_io,
                    sep=CSV_SEPARATOR,
                    dtype=str,
                    low_memory=False,
                )
                logger.debug(f"Successfully read {filename} with encoding {encoding}")

                # Replace NaN with None to handle missing values consistently
                df = df.replace({float("nan"): None, "": None})
                return df.to_dict(orient="records")  # type: ignore[return-value]

            except (
                UnicodeDecodeError,
                pd.errors.EmptyDataError,
                pd.errors.ParserError,
            ) as e:
                logger.debug(f"Failed to read {filename} with encoding {encoding}: {e}")
                continue
            except Exception as e:
                logger.error(
                    f"Unexpected error reading {filename} with encoding {encoding}: {e}"
                )
                continue

        logger.error(
            f"Failed to read {filename}. Unable to determine correct encoding or format."
        )
        return None

    def _combine_raw_data(self) -> list[dict[str, Any]]:
        """Combine all rows from all CSV files into a single list."""
        combined = []
        for csv_file in self.raw_csv_data:
            # Add filename source to each row for debugging/context if needed
            # for row in csv_file.get('data', []):
            #     row['_source_file'] = csv_file.get('filename')
            combined.extend(csv_file.get("data", []))
        return combined

    def get_value_by_id(
        self,
        element_id: str,
        context_filter: str | None = None,
    ) -> str | None:
        """Helper to find a value for a specific element ID, optionally filtered by context."""
        for record in self.all_records:
            if record.get("要素ID") == element_id:
                if context_filter is None or (
                    record.get("コンテキストID")
                    and context_filter in record["コンテキストID"]
                ):
                    value = record.get("値")
                    return clean_text(value)
        return None

    def get_records_by_id(self, element_id: str) -> list[dict[str, Any]]:
        """Helper to find all records for a specific element ID."""
        return [
            record for record in self.all_records if record.get("要素ID") == element_id
        ]

    def get_all_text_blocks(self) -> list[dict[str, str]]:
        """Extract all generic TextBlock elements."""
        text_blocks = []
        for record in self.all_records:
            element_id = record.get("要素ID")
            value = record.get("値")
            item_name = record.get(
                "項目名", element_id
            )  # Use 項目名 (item name) as title

            if element_id and "TextBlock" in element_id and value:
                text_blocks.append(
                    {
                        "id": element_id,
                        "title": item_name,
                        "content": value,  # Keep original value before cleaning for LLM to process
                    }
                )
            # Include report submission reason which may not have "TextBlock" in the ID
            elif (
                element_id
                and ("ReasonForFiling" in element_id or "提出理由" in item_name)
                and value
            ):
                text_blocks.append(
                    {
                        "id": element_id,
                        "title": item_name,
                        "content": value,  # Keep original value before cleaning for LLM to process
                    }
                )

        return text_blocks

    def process(self) -> StructuredDocData | None:
        """
        Process the raw CSV data into a structured dictionary.
        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement the 'process' method")

    @classmethod
    def process_structured_data_from_raw_csv(
        cls,
        raw_csv_data: list[dict[str, Any]],
        doc_id: str,
        doc_type_code: str,
    ) -> StructuredDocData | None:
        """
        Dispatches raw CSV data to the appropriate document processor.

        Args:
            raw_csv_data: List of dictionaries from reading CSV files.
            doc_id: EDINET document ID.
            doc_type_code: EDINET document type code.

        Returns:
            Structured dictionary of the document's data, or None if processing failed.
        """
        # Import here to avoid circular imports
        from src.processors.extraordinary_processor import ExtraordinaryReportProcessor
        from src.processors.generic_processor import GenericReportProcessor
        from src.processors.semiannual_processor import SemiAnnualReportProcessor

        processor_map = {
            "180": ExtraordinaryReportProcessor,
            "160": SemiAnnualReportProcessor,
            # Add other specific processors here
            # "140": QuarterlyReportProcessor,
        }
        default_processor = GenericReportProcessor

        processor_class = processor_map.get(doc_type_code, default_processor)
        logger.debug(
            f"Using processor {processor_class.__name__} for document type {doc_type_code} (doc_id: {doc_id})"
        )

        with ErrorContext(
            f"Processing document {doc_id} with {processor_class.__name__}",
            logger,
            reraise=False,
        ):
            processor = processor_class(raw_csv_data, doc_id, doc_type_code)
            return processor.process()

    @classmethod
    def process_zip_bytes(
        cls,
        zip_bytes: bytes,
        doc_id: str,
        doc_type_code: str,
    ) -> StructuredDocData | None:
        """
        Extract CSVs from ZIP bytes in memory and process into structured data
        using the appropriate document processor.

        Args:
            zip_bytes: The ZIP file content as bytes.
            doc_id: EDINET document ID.
            doc_type_code: EDINET document type code.

        Returns:
            Structured dictionary of the document's data, or None if processing failed.
        """
        raw_csv_data = []

        try:
            # Create a BytesIO object from the zip bytes
            zip_buffer = io.BytesIO(zip_bytes)

            try:
                with zipfile.ZipFile(zip_buffer, "r") as zip_ref:
                    # Get list of all files in the zip
                    file_list = zip_ref.namelist()
                    logger.debug(
                        f"Found {len(file_list)} files in ZIP for doc {doc_id}"
                    )

                    # Filter for CSV files, excluding __MACOSX directory
                    csv_files = [
                        filename
                        for filename in file_list
                        if filename.endswith(CSV_EXTENSION)
                        and not filename.startswith(f"{MACOS_METADATA_DIR}/")
                        and not filename.startswith("__MACOSX/")
                    ]

                    if not csv_files:
                        logger.warning(f"No CSV files found in ZIP for doc {doc_id}")
                        return None

                    for csv_filename in csv_files:
                        # Skip auditor report files (start with 'jpaud')
                        basename = os.path.basename(csv_filename)
                        if basename.startswith(AUDITOR_REPORT_PREFIX):
                            logger.debug(f"Skipping auditor report file: {basename}")
                            continue

                        try:
                            # Read the CSV file content as bytes
                            csv_bytes = zip_ref.read(csv_filename)
                            csv_records = cls.read_csv_from_bytes(csv_bytes, basename)

                            if csv_records is not None:
                                raw_csv_data.append(
                                    {"filename": basename, "data": csv_records}
                                )
                        except Exception as e:
                            logger.error(f"Error reading CSV file {csv_filename}: {e}")
                            continue

            except zipfile.BadZipFile as e:
                logger.error(f"Bad ZIP file for doc {doc_id}. Error: {e}")
                return None
            except Exception as e:
                logger.error(f"Error processing ZIP for doc {doc_id}: {e}")
                return None

            if not raw_csv_data:
                logger.warning(f"No valid data extracted from CSVs for doc {doc_id}")
                return None

            # Dispatch raw data to appropriate document processor
            structured_data = cls.process_structured_data_from_raw_csv(
                raw_csv_data,
                doc_id,
                doc_type_code,
            )

            if structured_data:
                logger.info(f"Successfully processed structured data for doc {doc_id}")
                return structured_data
            else:
                logger.warning(f"Document processor returned no data for doc {doc_id}")
                return None

        except Exception as e:
            logger.error(f"Critical error processing ZIP bytes for doc {doc_id}: {e}")
            return None

    @classmethod
    def process_zip_file(
        cls,
        path_to_zip_file: str,
        doc_id: str,
        doc_type_code: str,
    ) -> dict[str, Any] | None:
        """
        Extract CSVs from a ZIP file, read them, and process into structured data
        using the appropriate document processor.

        Args:
            path_to_zip_file: Path to the downloaded ZIP file.
            doc_id: EDINET document ID.
            doc_type_code: EDINET document type code.

        Returns:
            Structured dictionary of the document's data, or None if processing failed.
        """
        raw_csv_data = []
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                try:
                    with zipfile.ZipFile(path_to_zip_file, "r") as zip_ref:
                        zip_ref.extractall(temp_dir)
                    logger.debug(
                        f"Extracted {os.path.basename(path_to_zip_file)} to {temp_dir}"
                    )
                except zipfile.BadZipFile as e:
                    logger.error(f"Bad ZIP file: {path_to_zip_file}. Error: {e}")
                    return None
                except Exception as e:
                    logger.error(
                        f"Error extracting {os.path.basename(path_to_zip_file)}: {e}"
                    )
                    return None

                # Find and read all CSV files within the extracted structure
                csv_file_paths = []
                for root, dirs, files in os.walk(temp_dir):
                    # Exclude __MACOSX directory if present
                    if MACOS_METADATA_DIR in dirs:
                        dirs.remove(MACOS_METADATA_DIR)
                    for file in files:
                        if file.endswith(CSV_EXTENSION):
                            csv_file_paths.append(os.path.join(root, file))

                if not csv_file_paths:
                    logger.warning(
                        f"No CSV files found in extracted zip: {os.path.basename(path_to_zip_file)}"
                    )
                    return None

                for file_path in csv_file_paths:
                    # Skip auditor report files (start with 'jpaud')
                    if os.path.basename(file_path).startswith(AUDITOR_REPORT_PREFIX):
                        logger.debug(
                            f"Skipping auditor report file: {os.path.basename(file_path)}"
                        )
                        continue

                    csv_records = cls.read_csv_file(file_path)
                    if csv_records is not None:
                        raw_csv_data.append(
                            {
                                "filename": os.path.basename(file_path),
                                "data": csv_records,
                            }
                        )

                if not raw_csv_data:
                    logger.warning(
                        f"No valid data extracted from CSVs in {os.path.basename(path_to_zip_file)}"
                    )
                    return None

                # Dispatch raw data to appropriate document processor
                structured_data = cls.process_structured_data_from_raw_csv(
                    raw_csv_data,
                    doc_id,
                    doc_type_code,
                )

                if structured_data:
                    logger.info(
                        f"Successfully processed structured data for {os.path.basename(path_to_zip_file)}"
                    )
                    return structured_data
                else:
                    logger.warning(
                        f"Document processor returned no data for {os.path.basename(path_to_zip_file)}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Critical error processing zip file {path_to_zip_file}: {e}")
            return None

    @classmethod
    def process_zip_directory(
        cls,
        directory_path: str,
        doc_type_codes: list[str] | None = None,
        doc_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Process all ZIP files in a directory containing EDINET documents.

        Args:
            directory_path: Path to the directory containing ZIP files.
            doc_type_codes: Optional list of doc type codes to process.
            doc_ids: Optional list of doc IDs to process.

        Returns:
            List of structured data dictionaries for each successfully processed document.
        """
        all_structured_data = []
        if not os.path.isdir(directory_path):
            logger.error(f"Directory not found: {directory_path}")
            return []

        zip_files = [
            f
            for f in os.listdir(directory_path)
            if f.endswith(ZIP_EXTENSION)
            and (doc_ids is None or f.split("-")[0] in doc_ids)
        ]
        total_files = len(zip_files)
        logger.info(f"Found {total_files} zip files in {directory_path} to process.")

        for i, filename in enumerate(zip_files, 1):
            file_path = os.path.join(directory_path, filename)
            try:
                # Filename format: docID-docTypeCode-filerName.zip
                parts = filename.split("-", 2)
                if len(parts) < 3:
                    logger.warning(f"Skipping improperly named zip file: {filename}")
                    continue
                doc_id = parts[0]
                doc_type_code = parts[1]
                # filer_name = parts[2].rsplit('.', 1)[0] # Not strictly needed here

                if doc_type_codes is not None and doc_type_code not in doc_type_codes:
                    # logger.debug(f"Skipping {filename} (doc type {doc_type_code} not in target list)")
                    continue

                logger.info(f"Processing {i}/{total_files}: `{filename}`")
                structured_data = cls.process_zip_file(file_path, doc_id, doc_type_code)

                if structured_data:
                    all_structured_data.append(structured_data)

            except Exception as e:
                logger.error(f"Error processing zip file {filename}: {e}")
                # traceback.print_exc() # Uncomment for detailed traceback during debugging

        logger.info(
            f"Finished processing zip directory. Successfully extracted structured data for {len(all_structured_data)} documents."
        )
        return all_structured_data

    def _get_common_metadata(self) -> dict[str, Any]:
        """Extract common metadata available in many filings."""
        metadata = {}
        id_to_key = {
            XBRL_ELEMENT_IDS["EDINET_CODE"]: "edinet_code",
            XBRL_ELEMENT_IDS["COMPANY_NAME_JA"]: "company_name_ja",
            XBRL_ELEMENT_IDS["COMPANY_NAME_EN"]: "company_name_en",
            XBRL_ELEMENT_IDS["DOCUMENT_TYPE"]: "document_type",
            XBRL_ELEMENT_IDS[
                "DOCUMENT_TITLE_COVER"
            ]: "document_title",  # Common in some reports
            XBRL_ELEMENT_IDS["DOCUMENT_TITLE"]: "document_title",  # Common in others
        }
        for key, element_id in id_to_key.items():
            value = self.get_value_by_id(key)
            if value is not None:
                metadata[element_id] = clean_text(value)

        # Add doc_id and doc_type_code from the zip filename metadata
        metadata["doc_id"] = self.doc_id
        metadata["doc_type_code"] = self.doc_type_code

        return metadata
