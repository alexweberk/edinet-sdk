"""Test configuration and fixtures for EDINET SDK tests."""

import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from httpx import Response

from src.models import (
    EdinetMetadata,
    EdinetSuccessResponse,
    FilingMetadata,
)


@pytest.fixture
def mock_api_key() -> str:
    """Provide a mock API key for testing."""
    return "test_api_key_12345"


@pytest.fixture
def mock_env_vars(monkeypatch: pytest.MonkeyPatch, mock_api_key: str) -> None:
    """Set up mock environment variables for testing."""
    monkeypatch.setenv("EDINET_API_KEY", mock_api_key)
    monkeypatch.setenv("MAX_RETRIES", "3")
    monkeypatch.setenv("DELAY_SECONDS", "1")
    monkeypatch.setenv("CACHE_ENABLED", "false")
    monkeypatch.setenv("CACHE_DIR", ".test_cache")


@pytest.fixture
def sample_filing_metadata() -> FilingMetadata:
    """Provide sample filing metadata for testing."""
    return FilingMetadata(
        seqNumber=1,
        docID="S100TEST",
        edinetCode="E12345",
        secCode="1234",
        JCN="1234567890123",
        filerName="Test Corporation",
        fundCode=None,
        ordinanceCode="010",
        formCode="030000",
        docTypeCode="160",
        periodStart="2024-01-01",
        periodEnd="2024-03-31",
        submitDateTime="2024-04-15 17:00",
        docDescription="Semi-Annual Report Test",
        issuerEdinetCode=None,
        subjectEdinetCode=None,
        subsidiaryEdinetCode=None,
        currentReportReason=None,
        parentDocID=None,
        opeDateTime="2024-04-15 17:30",
        withdrawalStatus="0",
        docInfoEditStatus="0",
        disclosureStatus="0",
        xbrlFlag="1",
        pdfFlag="1",
        attachDocFlag="0",
        englishDocFlag="0",
        csvFlag="1",
        legalStatus="1",
    )


@pytest.fixture
def sample_edinet_metadata() -> EdinetMetadata:
    """Provide sample EDINET API metadata for testing."""
    return EdinetMetadata(
        title="EDINET API Test Response",
        parameter={"date": "2024-01-01", "type": "2"},
        resultset={"count": 1},
        processDateTime="2024-01-01T12:00:00+09:00",
        status="200",
        message="OK",
    )


@pytest.fixture
def sample_api_response(
    sample_edinet_metadata: EdinetMetadata,
    sample_filing_metadata: FilingMetadata,
) -> EdinetSuccessResponse:
    """Provide a complete sample API response for testing."""
    return EdinetSuccessResponse(
        metadata=sample_edinet_metadata,
        results=[sample_filing_metadata],
    )


@pytest.fixture
def mock_httpx_response() -> Mock:
    """Create a mock httpx Response object."""
    mock_response = Mock(spec=Response)
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "application/json"}
    return mock_response


@pytest.fixture
def sample_csv_data() -> str:
    """Provide sample CSV data for testing."""
    return """要素ID\t項目名\tコンテキストID\t相対年度\t連結・個別\t期間・時点\tユニットID\t単位\t値
jppfs_cor:SalariesAndAllowancesSGA\t給料及び手当、販売費及び一般管理費\tCurrentYTDDuration\t当四半期累計期間\t連結\t期間\tJPY\t円\t1044176000
jppfs_cor:RevenuesSGA\t売上高、販売費及び一般管理費\tCurrentYTDDuration\t当四半期累計期間\t連結\t期間\tJPY\t円\t5500000000"""


@pytest.fixture
def sample_csv_records() -> list[dict[str, Any]]:
    """Provide sample CSV records as Python objects for testing."""
    return [
        {
            "要素ID": "jppfs_cor:SalariesAndAllowancesSGA",
            "項目名": "給料及び手当、販売費及び一般管理費",
            "コンテキストID": "CurrentYTDDuration",
            "相対年度": "当四半期累計期間",
            "連結・個別": "連結",
            "期間・時点": "期間",
            "ユニットID": "JPY",
            "単位": "円",
            "値": "1044176000",
        },
        {
            "要素ID": "jppfs_cor:RevenuesSGA",
            "項目名": "売上高、販売費及び一般管理費",
            "コンテキストID": "CurrentYTDDuration",
            "相対年度": "当四半期累計期間",
            "連結・個別": "連結",
            "期間・時点": "期間",
            "ユニットID": "JPY",
            "単位": "円",
            "値": "5500000000",
        },
    ]


@pytest.fixture
def temp_directory() -> Path:
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_zip_file(temp_directory: Path, sample_csv_data: str) -> Path:
    """Create a sample ZIP file with CSV data for testing."""
    zip_path = temp_directory / "test_document.zip"
    csv_filename = "XBRL_TO_CSV/test_data.csv"

    with zipfile.ZipFile(zip_path, "w") as zip_file:
        zip_file.writestr(csv_filename, sample_csv_data)
        # Add a dummy auditor report that should be skipped
        zip_file.writestr("jpaud01_audit_report.csv", "Audit,Report,Data")

    return zip_path


@pytest.fixture
def mock_current_date() -> datetime:
    """Provide a fixed date for testing date-related functionality."""
    return datetime(2024, 1, 15, 12, 0, 0)


@pytest.fixture
def disable_logging(caplog: pytest.LogCaptureFixture) -> None:
    """Disable logging during tests to reduce noise."""
    caplog.set_level(50)  # CRITICAL level to suppress most logs


@pytest.fixture
def sample_document_types() -> dict[str, str]:
    """Provide sample document types for testing."""
    return {
        "120": "Securities Report",
        "140": "Quarterly Report",
        "160": "Semi-Annual Report",
        "180": "Extraordinary Report",
    }


@pytest.fixture
def sample_xbrl_element_ids() -> dict[str, str]:
    """Provide sample XBRL element IDs for testing."""
    return {
        "EDINET_CODE": "jpdei_cor:EDINETCodeDEI",
        "COMPANY_NAME_JA": "jpdei_cor:FilerNameInJapaneseDEI",
        "COMPANY_NAME_EN": "jpdei_cor:FilerNameInEnglishDEI",
        "DOCUMENT_TYPE": "jpdei_cor:DocumentTypeDEI",
    }


@pytest.fixture
def mock_cache_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable caching for tests that don't need it."""
    monkeypatch.setenv("CACHE_ENABLED", "false")


@pytest.fixture
def mock_api_urls() -> dict[str, str]:
    """Provide mock API URLs for testing."""
    return {
        "base_url": "https://test-api.edinet.go.jp/api/v2",
        "document_url": "https://test-document-api.edinet.go.jp/api/v2",
    }


@pytest.fixture
def sample_json_response_data(sample_api_response: EdinetSuccessResponse) -> str:
    """Provide sample JSON response data as string."""
    return sample_api_response.model_dump_json()


@pytest.fixture
def error_response_data() -> dict[str, Any]:
    """Provide sample error response data for testing."""
    return {
        "statusCode": 400,
        "message": "Invalid request parameters",
    }
