"""Unit tests for the processors module."""

import zipfile
from pathlib import Path

import pytest

from src.models import File, Filing, FilingMetadata
from src.processors.base_processor import BaseProcessor


class TestBaseProcessor:
    """Test BaseProcessor functionality."""

    def test_common_encodings_defined(self) -> None:
        """Test that common encodings are properly defined."""
        encodings = BaseProcessor.COMMON_ENCODINGS
        assert isinstance(encodings, list)
        assert "utf-8" in encodings
        assert "shift-jis" in encodings
        assert "utf-16" in encodings

    def test_doc_type_code_default(self) -> None:
        """Test that doc_type_code defaults to None."""
        assert BaseProcessor.doc_type_code is None


class TestZipBytesToFiling:
    """Test zip_bytes_to_filing method."""

    def test_zip_bytes_to_filing_success(
        self, sample_zip_file: Path, sample_filing_metadata: FilingMetadata
    ) -> None:
        """Test successful processing of ZIP bytes to Filing."""
        # Read the sample ZIP file
        zip_bytes = sample_zip_file.read_bytes()

        result = BaseProcessor.zip_bytes_to_filing(zip_bytes, sample_filing_metadata)

        assert isinstance(result, Filing)
        assert result.metadata == sample_filing_metadata
        assert len(result.files) > 0

        # Check that at least one file was processed
        file_obj = result.files[0]
        assert isinstance(file_obj, File)
        assert file_obj.filename.endswith(".csv")
        assert len(file_obj.records) > 0

    def test_zip_bytes_to_filing_empty_zip(
        self, temp_directory: Path, sample_filing_metadata: FilingMetadata
    ) -> None:
        """Test processing of empty ZIP file."""
        # Create empty ZIP file
        empty_zip_path = temp_directory / "empty.zip"
        with zipfile.ZipFile(empty_zip_path, "w"):
            pass  # Create empty ZIP

        zip_bytes = empty_zip_path.read_bytes()
        result = BaseProcessor.zip_bytes_to_filing(zip_bytes, sample_filing_metadata)

        assert isinstance(result, Filing)
        assert result.metadata == sample_filing_metadata
        assert len(result.files) == 0

    def test_zip_bytes_to_filing_with_auditor_files(
        self,
        temp_directory: Path,
        sample_filing_metadata: FilingMetadata,
        sample_csv_data: str,
    ) -> None:
        """Test that auditor files are properly filtered out."""
        zip_path = temp_directory / "test_with_auditor.zip"

        with zipfile.ZipFile(zip_path, "w") as zip_file:
            # Add regular CSV file
            zip_file.writestr("XBRL_TO_CSV/regular_data.csv", sample_csv_data)
            # Add auditor report that should be skipped
            zip_file.writestr(
                "XBRL_TO_CSV/jpaud01_audit_report.csv", "Audit,Report,Data"
            )
            zip_file.writestr("XBRL_TO_CSV/jpaud02_audit_report.csv", "More,Audit,Data")

        zip_bytes = zip_path.read_bytes()
        result = BaseProcessor.zip_bytes_to_filing(zip_bytes, sample_filing_metadata)

        assert len(result.files) == 1  # Only the regular file should be included
        assert "jpaud" not in result.files[0].filename

    def test_zip_bytes_to_filing_invalid_zip(
        self, sample_filing_metadata: FilingMetadata
    ) -> None:
        """Test processing of invalid ZIP data."""
        invalid_zip_bytes = b"not a zip file"

        with pytest.raises(zipfile.BadZipFile):
            BaseProcessor.zip_bytes_to_filing(invalid_zip_bytes, sample_filing_metadata)


class TestCsvBytesToRecords:
    """Test csv_bytes_to_records method."""

    def test_csv_bytes_to_records_utf8(self, sample_csv_data: str) -> None:
        """Test CSV parsing with UTF-8 encoding."""
        csv_bytes = sample_csv_data.encode("utf-8")

        result = BaseProcessor.csv_bytes_to_records(csv_bytes)

        assert isinstance(result, list)
        assert len(result) == 2  # Based on sample data
        # Use Unicode escape for Japanese characters to avoid encoding issues
        assert "\u8981\u7d20ID" in result[0]  # 要素ID
        assert "\u9805\u76eeName" in result[0]  # 項目名 (note: this might be different)

    def test_csv_bytes_to_records_shift_jis(self, sample_csv_data: str) -> None:
        """Test CSV parsing with Shift-JIS encoding."""
        csv_bytes = sample_csv_data.encode("shift-jis")

        result = BaseProcessor.csv_bytes_to_records(csv_bytes)

        assert isinstance(result, list)
        assert len(result) == 2

    def test_csv_bytes_to_records_empty(self) -> None:
        """Test CSV parsing with empty data."""
        csv_bytes = b""

        result = BaseProcessor.csv_bytes_to_records(csv_bytes)

        assert result == []

    def test_csv_bytes_to_records_malformed(self) -> None:
        """Test CSV parsing with malformed data."""
        csv_bytes = b"malformed\tcsv\tdata\nwith\tmissing\ncolumns"

        # Should not raise an exception, but may return unexpected results
        result = BaseProcessor.csv_bytes_to_records(csv_bytes)
        assert isinstance(result, list)


class TestCsvBytesToRecordsWithEncoding:
    """Test _csv_bytes_to_records_with_encoding method."""

    def test_csv_bytes_to_records_with_utf8(self, sample_csv_data: str) -> None:
        """Test CSV parsing with specified UTF-8 encoding."""
        csv_bytes = sample_csv_data.encode("utf-8")

        result = BaseProcessor._csv_bytes_to_records_with_encoding(csv_bytes, "utf-8")

        assert isinstance(result, list)
        assert len(result) == 2

    def test_csv_bytes_to_records_with_wrong_encoding(
        self, sample_csv_data: str
    ) -> None:
        """Test CSV parsing with wrong encoding raises exception."""
        csv_bytes = sample_csv_data.encode("utf-8")

        with pytest.raises(UnicodeDecodeError):
            BaseProcessor._csv_bytes_to_records_with_encoding(csv_bytes, "ascii")


class TestZipFileToFiling:
    """Test zip_file_to_filing method."""

    def test_zip_file_to_filing_success(
        self, sample_zip_file: Path, sample_filing_metadata: FilingMetadata
    ) -> None:
        """Test successful processing of ZIP file to Filing."""
        result = BaseProcessor.zip_file_to_filing(
            str(sample_zip_file), sample_filing_metadata
        )

        assert isinstance(result, Filing)
        assert result.metadata == sample_filing_metadata
        assert len(result.files) > 0

    def test_zip_file_to_filing_nonexistent_file(
        self, sample_filing_metadata: FilingMetadata
    ) -> None:
        """Test processing of non-existent ZIP file."""
        with pytest.raises(FileNotFoundError):
            BaseProcessor.zip_file_to_filing(
                "/nonexistent/file.zip", sample_filing_metadata
            )


class TestZipDirectoryToFilings:
    """Test zip_directory_to_filings method."""

    def test_zip_directory_to_filings_success(
        self, temp_directory: Path, sample_csv_data: str
    ) -> None:
        """Test successful processing of ZIP files in directory."""
        # Create test ZIP files
        zip1_path = temp_directory / "test1.zip"
        zip2_path = temp_directory / "test2.zip"

        for zip_path in [zip1_path, zip2_path]:
            with zipfile.ZipFile(zip_path, "w") as zip_file:
                zip_file.writestr("XBRL_TO_CSV/data.csv", sample_csv_data)

        # Create sample metadata list
        metadata_list = [
            FilingMetadata(
                seqNumber=1,
                docID="TEST1",
                withdrawalStatus="0",
                docInfoEditStatus="0",
                disclosureStatus="0",
                xbrlFlag="1",
                pdfFlag="1",
                attachDocFlag="0",
                englishDocFlag="0",
                csvFlag="1",
                legalStatus="1",
            ),
            FilingMetadata(
                seqNumber=2,
                docID="TEST2",
                withdrawalStatus="0",
                docInfoEditStatus="0",
                disclosureStatus="0",
                xbrlFlag="1",
                pdfFlag="1",
                attachDocFlag="0",
                englishDocFlag="0",
                csvFlag="1",
                legalStatus="1",
            ),
        ]

        result = BaseProcessor.zip_directory_to_filings(
            str(temp_directory), metadata_list
        )

        assert isinstance(result, list)
        assert len(result) == 2
        for filing in result:
            assert isinstance(filing, Filing)

    def test_zip_directory_to_filings_empty_directory(
        self, temp_directory: Path
    ) -> None:
        """Test processing of empty directory."""
        result = BaseProcessor.zip_directory_to_filings(str(temp_directory), [])

        assert result == []

    def test_zip_directory_to_filings_nonexistent_directory(self) -> None:
        """Test processing of non-existent directory."""
        with pytest.raises(FileNotFoundError):
            BaseProcessor.zip_directory_to_filings("/nonexistent/directory", [])


class TestFilterCsvFiles:
    """Test _filter_csv_files method."""

    def test_filter_csv_files_basic(self) -> None:
        """Test basic CSV file filtering."""
        file_list = [
            "data.csv",
            "report.txt",
            "analysis.csv",
            "image.png",
            "summary.csv",
        ]

        result = BaseProcessor._filter_csv_files(file_list)

        expected = ["data.csv", "analysis.csv", "summary.csv"]
        assert result == expected

    def test_filter_csv_files_mixed_case(self) -> None:
        """Test CSV file filtering with mixed case extensions."""
        file_list = ["data.csv", "report.CSV", "analysis.Csv", "other.txt"]

        result = BaseProcessor._filter_csv_files(file_list)

        # Should only match lowercase .csv extension
        assert result == ["data.csv"]

    def test_filter_csv_files_empty_list(self) -> None:
        """Test CSV file filtering with empty list."""
        result = BaseProcessor._filter_csv_files([])
        assert result == []

    def test_filter_csv_files_no_csv_files(self) -> None:
        """Test CSV file filtering with no CSV files."""
        file_list = ["data.txt", "report.pdf", "image.png"]

        result = BaseProcessor._filter_csv_files(file_list)
        assert result == []


class TestShouldSkipAuditorFile:
    """Test _should_skip_auditor_file method."""

    def test_should_skip_auditor_file_with_jpaud_prefix(self) -> None:
        """Test that files with jpaud prefix are skipped."""
        assert BaseProcessor._should_skip_auditor_file("jpaud01_report.csv") is True
        assert BaseProcessor._should_skip_auditor_file("jpaud02_analysis.csv") is True
        assert BaseProcessor._should_skip_auditor_file("jpauditor_summary.csv") is True

    def test_should_skip_auditor_file_without_jpaud_prefix(self) -> None:
        """Test that files without jpaud prefix are not skipped."""
        assert BaseProcessor._should_skip_auditor_file("regular_data.csv") is False
        assert BaseProcessor._should_skip_auditor_file("financial_report.csv") is False
        assert BaseProcessor._should_skip_auditor_file("jpn_data.csv") is False

    def test_should_skip_auditor_file_edge_cases(self) -> None:
        """Test edge cases for auditor file detection."""
        assert BaseProcessor._should_skip_auditor_file("jpaud.csv") is True
        assert (
            BaseProcessor._should_skip_auditor_file("JPaud01.csv") is False
        )  # Case sensitive
        assert BaseProcessor._should_skip_auditor_file("") is False


class TestFindCsvFiles:
    """Test _find_csv_files method."""

    def test_find_csv_files_success(self, temp_directory: Path) -> None:
        """Test successful finding of CSV files in directory."""
        # Create test files
        csv_dir = temp_directory / "XBRL_TO_CSV"
        csv_dir.mkdir()

        (csv_dir / "data1.csv").write_text("test,data")
        (csv_dir / "data2.csv").write_text("more,test,data")
        (csv_dir / "jpaud01.csv").write_text("audit,data")  # Should be filtered out
        (csv_dir / "report.txt").write_text("not csv")  # Should be filtered out

        result = BaseProcessor._find_csv_files(str(temp_directory))

        # Should find 2 CSV files (excluding auditor file and non-CSV file)
        assert len(result) == 2
        assert any("data1.csv" in path for path in result)
        assert any("data2.csv" in path for path in result)
        assert not any("jpaud01.csv" in path for path in result)
        assert not any("report.txt" in path for path in result)

    def test_find_csv_files_no_xbrl_directory(self, temp_directory: Path) -> None:
        """Test finding CSV files when XBRL_TO_CSV directory doesn't exist."""
        result = BaseProcessor._find_csv_files(str(temp_directory))
        assert result == []

    def test_find_csv_files_empty_directory(self, temp_directory: Path) -> None:
        """Test finding CSV files in empty XBRL_TO_CSV directory."""
        csv_dir = temp_directory / "XBRL_TO_CSV"
        csv_dir.mkdir()

        result = BaseProcessor._find_csv_files(str(temp_directory))
        assert result == []

    def test_find_csv_files_nonexistent_directory(self) -> None:
        """Test finding CSV files in non-existent directory."""
        result = BaseProcessor._find_csv_files("/nonexistent/directory")
        assert result == []
