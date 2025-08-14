# document_processors.py
import io
import logging
import os
import zipfile

import chardet
import pandas as pd

from src.config import (
    AUDITOR_REPORT_PREFIX,
    CSV_EXTENSION,
    CSV_SEPARATOR,
    MACOS_METADATA_DIR,
)
from src.models import CsvFileAsRecords, File, Filing, FilingMetadata

logger = logging.getLogger(__name__)


class BaseProcessor:
    """
    Base class for document specific data extraction.

    All methods are static/class methods as there's no need to maintain instance state.
    Processes ZIP files or bytes data directly into structured data.

    zip_bytes_to_filename_records: zip bytes -> Filing
    zip_file_to_filename_records: zip file -> Filing
    zip_directory_to_filename_records: zip directory -> Filing

    process: Filing -> StructuredDocData
    """

    COMMON_ENCODINGS = [
        "utf-16",
        "utf-16le",
        "utf-16be",
        "utf-8",
        "shift-jis",
        "euc-jp",
        "iso-8859-1",
        "windows-1252",
    ]

    # The doc_type_code this processor is designed for
    doc_type_code: str | None = None

    @classmethod
    def zip_bytes_to_filing(
        cls,
        zip_bytes: bytes,
        filing_metadata: FilingMetadata,
    ) -> Filing | None:
        """
        Extract CSVs from ZIP bytes in memory and return as list of records.

        Args:
            zip_bytes: The ZIP file content as bytes.
            filing_metadata: The metadata of the filing.

        Returns:
            List of records, or None if processing failed.
        """
        doc_id = filing_metadata.docID
        files: list[File] = []

        try:
            # Create a BytesIO object from the zip bytes
            zip_buffer = io.BytesIO(zip_bytes)

            with zipfile.ZipFile(zip_buffer, "r") as zip_ref:
                # Get list of all files in the zip
                file_list = zip_ref.namelist()
                file_list_filtered = cls._filter_csv_files(file_list)

                if not file_list_filtered:
                    logger.warning(f"No CSV files found in ZIP for doc {doc_id}")
                    return None

                for csv_filename in file_list_filtered:
                    basename = os.path.basename(csv_filename)
                    if cls._should_skip_auditor_file(basename):
                        continue

                    csv_bytes_undecoded = zip_ref.read(csv_filename)
                    records = cls.csv_bytes_to_records(
                        csv_bytes_undecoded,
                        basename,
                    )
                    if records is not None:
                        file = File(filename=basename, records=records)
                        files.append(file)

                return Filing(metadata=filing_metadata, files=files)

        except Exception as e:
            logger.error(f"Critical error processing ZIP bytes for doc {doc_id}: {e}")
            return None

    @classmethod
    def csv_bytes_to_records(
        cls,
        csv_bytes: bytes,
        filename: str = "zip bytes data",
    ) -> CsvFileAsRecords | None:
        """Read a tab-separated CSV from csv bytes trying multiple encodings."""
        try:
            encoding = chardet.detect(csv_bytes)["encoding"]
            if encoding:
                return cls._csv_bytes_to_records_with_encoding(csv_bytes, encoding)
            else:
                # Try common encodings if no encoding is detected
                for encoding in cls.COMMON_ENCODINGS:
                    try:
                        return cls._csv_bytes_to_records_with_encoding(
                            csv_bytes, encoding
                        )
                    except Exception as e:
                        logger.debug(
                            f"Failed to read {filename} with encoding {encoding}: {e}"
                        )
                        continue

                logger.error(
                    f"Failed to read {filename}. Unable to determine correct encoding or format."
                )
        except Exception as e:
            logger.error(f"Error reading CSV file {filename}: {e}")
        return None

    @classmethod
    def _csv_bytes_to_records_with_encoding(
        cls,
        csv_bytes: bytes,
        encoding: str = "utf-8",
    ) -> CsvFileAsRecords | None:
        """Convert bytes to a pandas DataFrame using encoding if provided."""
        io_data = csv_bytes.decode(encoding)
        df = pd.read_csv(
            io.StringIO(io_data),
            sep=CSV_SEPARATOR,
            dtype=str,
            low_memory=False,
        )
        df = df.replace({float("nan"): None, "": None})
        return df.to_dict(orient="records")

    @classmethod
    def zip_file_to_filing(
        cls,
        zip_file_path: str,
        filing_metadata: FilingMetadata,
    ) -> Filing | None:
        """Read a zipfile and return a dictionary of filename to records."""
        try:
            with open(zip_file_path, "rb") as f:
                zip_bytes = f.read()

            return cls.zip_bytes_to_filing(
                zip_bytes=zip_bytes,
                filing_metadata=filing_metadata,
            )

        except Exception as e:
            logger.error(f"Error reading ZIP file {zip_file_path}: {e}")
            return None

    @classmethod
    def zip_directory_to_filings(
        cls,
        zip_directory_path: str,
        filing_metadata: FilingMetadata,
    ) -> list[Filing] | None:
        """Read zip files from a directory and return a dictionary of filename to records."""
        all_filings: list[Filing] = []
        for zip_file_path in os.listdir(zip_directory_path):
            filing = cls.zip_file_to_filing(
                zip_file_path=os.path.join(zip_directory_path, zip_file_path),
                filing_metadata=filing_metadata,
            )
            if filing:
                all_filings.append(filing)
        return all_filings if all_filings else None

    @staticmethod
    def _filter_csv_files(file_list: list[str]) -> list[str]:
        """Filter for CSV files, excluding system metadata directories."""
        return [
            filename
            for filename in file_list
            if filename.endswith(CSV_EXTENSION)
            and not filename.startswith(f"{MACOS_METADATA_DIR}/")
            and not filename.startswith("__MACOSX/")
        ]

    @staticmethod
    def _should_skip_auditor_file(basename: str) -> bool:
        """Check if file should be skipped (auditor reports)."""
        if basename.startswith(AUDITOR_REPORT_PREFIX):
            logger.debug(f"Skipping auditor report file: {basename}")
            return True
        return False

    @staticmethod
    def _find_csv_files(temp_dir: str) -> list[str]:
        """Find all CSV files within extracted directory structure."""
        csv_file_paths = []
        for root, dirs, files in os.walk(temp_dir):
            # Exclude __MACOSX directory if present
            if MACOS_METADATA_DIR in dirs:
                dirs.remove(MACOS_METADATA_DIR)
            for file in files:
                if file.endswith(CSV_EXTENSION):
                    csv_file_paths.append(os.path.join(root, file))
        return csv_file_paths

    # @staticmethod
    # def get_value_by_id(
    #     all_records: list[dict[str, Any]],
    #     element_id: str,
    #     context_filter: str | None = None,
    # ) -> str | None:
    #     """Helper to find a value for a specific element ID, optionally filtered by context."""
    #     for record in all_records:
    #         if record.get("要素ID") == element_id:
    #             if context_filter is None or (
    #                 record.get("コンテキストID")
    #                 and context_filter in record["コンテキストID"]
    #             ):
    #                 value = record.get("値")
    #                 return clean_text(value)
    #     return None

    # @staticmethod
    # def get_records_by_id(
    #     all_records: list[dict[str, Any]], element_id: str
    # ) -> list[dict[str, Any]]:
    #     """Helper to find all records for a specific element ID."""
    #     return [record for record in all_records if record.get("要素ID") == element_id]

    # @staticmethod
    # def get_all_text_blocks(all_records: list[dict[str, Any]]) -> list[dict[str, str]]:
    #     """Extract all generic TextBlock elements."""
    #     text_blocks = []
    #     for record in all_records:
    #         element_id = record.get("要素ID")
    #         value = record.get("値")
    #         item_name = record.get(
    #             "項目名", element_id
    #         )  # Use 項目名 (item name) as title

    #         if element_id and "TextBlock" in element_id and value:
    #             text_blocks.append(
    #                 {
    #                     "id": element_id,
    #                     "title": item_name,
    #                     "content": value,  # Keep original value before cleaning for LLM to process
    #                 }
    #             )
    #         # Include report submission reason which may not have "TextBlock" in the ID
    #         elif (
    #             element_id
    #             and ("ReasonForFiling" in element_id or "提出理由" in item_name)
    #             and value
    #         ):
    #             text_blocks.append(
    #                 {
    #                     "id": element_id,
    #                     "title": item_name,
    #                     "content": value,  # Keep original value before cleaning for LLM to process
    #                 }
    #             )

    #     return text_blocks
