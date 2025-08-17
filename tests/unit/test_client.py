"""Unit tests for the EDINET client module."""

import datetime
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import httpx
import pytest

from src.edinet.client import EdinetClient
from src.models import (
    EdinetAuthenticationError,
    EdinetDocumentFetchError,
    EdinetErrorResponse,
    EdinetRetryExceededError,
    EdinetSuccessResponse,
    FilingMetadata,
)


class TestEdinetClientInitialization:
    """Test EdinetClient initialization and validation."""

    def test_init_with_api_key(self, mock_env_vars: None) -> None:
        """Test initialization with explicit API key."""
        client = EdinetClient(api_key="custom_key")
        assert client.api_key == "custom_key"

    def test_init_without_api_key(self, mock_env_vars: None) -> None:
        """Test initialization without API key uses environment variable."""
        client = EdinetClient()
        assert client.api_key == "test_api_key_12345"

    def test_init_with_custom_parameters(self, mock_env_vars: None) -> None:
        """Test initialization with custom parameters."""
        client = EdinetClient(
            max_retries=5,
            delay_seconds=10,
            download_dir="/tmp/test",
            timeout=60,
            enable_cache=False,
        )
        assert client.max_retries == 5
        assert client.delay_seconds == 10
        assert client.download_dir == "/tmp/test"
        assert client.timeout == 60
        assert client.enable_cache is False
        assert client.cache_manager is None

    def test_init_with_cache_enabled(self, mock_env_vars: None) -> None:
        """Test initialization with cache enabled."""
        with patch("src.edinet.client.CacheManager") as mock_cache_manager:
            client = EdinetClient(enable_cache=True, cache_dir="/tmp/cache")
            assert client.enable_cache is True
            mock_cache_manager.assert_called_once_with("/tmp/cache")

    def test_init_invalid_max_retries(self, mock_env_vars: None) -> None:
        """Test initialization with invalid max_retries."""
        with pytest.raises(ValueError, match="max_retries must be non-negative"):
            EdinetClient(max_retries=-1)

    def test_init_invalid_delay_seconds(self, mock_env_vars: None) -> None:
        """Test initialization with invalid delay_seconds."""
        with pytest.raises(ValueError, match="delay_seconds must be non-negative"):
            EdinetClient(delay_seconds=-1)

    def test_init_invalid_timeout(self, mock_env_vars: None) -> None:
        """Test initialization with invalid timeout."""
        with pytest.raises(ValueError, match="timeout must be positive"):
            EdinetClient(timeout=0)

    @patch("os.makedirs")
    def test_init_creates_download_directory(
        self, mock_makedirs: Mock, mock_env_vars: None
    ) -> None:
        """Test that initialization creates download directory."""
        EdinetClient(download_dir="/tmp/test_downloads")
        mock_makedirs.assert_called_once_with("/tmp/test_downloads", exist_ok=True)


class TestListRecentFilings:
    """Test list_recent_filings method."""

    @patch.object(EdinetClient, "list_filings")
    def test_list_recent_filings_default_days(
        self, mock_list_filings: Mock, mock_env_vars: None
    ) -> None:
        """Test list_recent_filings with default lookback days."""
        client = EdinetClient()
        mock_list_filings.return_value = []

        client.list_recent_filings()

        # Verify it calls list_filings with correct date range
        mock_list_filings.assert_called_once()
        call_kwargs = mock_list_filings.call_args[1]

        # Should have start_date and end_date
        assert "start_date" in call_kwargs
        assert "end_date" in call_kwargs

        # Date range should be 7 days
        start_date = call_kwargs["start_date"]
        end_date = call_kwargs["end_date"]
        assert (end_date - start_date).days == 6  # 7 days inclusive

    @patch.object(EdinetClient, "list_filings")
    def test_list_recent_filings_custom_days(
        self, mock_list_filings: Mock, mock_env_vars: None
    ) -> None:
        """Test list_recent_filings with custom lookback days."""
        client = EdinetClient()
        mock_list_filings.return_value = []

        client.list_recent_filings(lookback_days=14)

        mock_list_filings.assert_called_once()
        call_kwargs = mock_list_filings.call_args[1]

        start_date = call_kwargs["start_date"]
        end_date = call_kwargs["end_date"]
        assert (end_date - start_date).days == 13  # 14 days inclusive

    def test_list_recent_filings_invalid_days(self, mock_env_vars: None) -> None:
        """Test list_recent_filings with invalid lookback days."""
        client = EdinetClient()

        with pytest.raises(ValueError, match="lookback_days must be positive"):
            client.list_recent_filings(lookback_days=0)

        with pytest.raises(ValueError, match="lookback_days must be positive"):
            client.list_recent_filings(lookback_days=-1)

    @patch.object(EdinetClient, "list_filings")
    def test_list_recent_filings_passes_filters(
        self, mock_list_filings: Mock, mock_env_vars: None
    ) -> None:
        """Test that list_recent_filings passes filter parameters correctly."""
        client = EdinetClient()
        mock_list_filings.return_value = []

        client.list_recent_filings(
            edinet_codes=["E12345"],
            filing_type_codes=["160"],
            filer_names=["Test Corp"],
        )

        mock_list_filings.assert_called_once()
        call_kwargs = mock_list_filings.call_args[1]

        assert call_kwargs["edinet_codes"] == ["E12345"]
        assert call_kwargs["filing_type_codes"] == ["160"]
        assert call_kwargs["filer_names"] == ["Test Corp"]


class TestListFilings:
    """Test list_filings method."""

    def test_list_filings_invalid_date_range(self, mock_env_vars: None) -> None:
        """Test list_filings with invalid date range."""
        client = EdinetClient()

        start_date = datetime.date(2024, 2, 1)
        end_date = datetime.date(2024, 1, 1)

        with pytest.raises(ValueError, match="start_date must be <= end_date"):
            client.list_filings(start_date, end_date)

    @patch.object(EdinetClient, "_fetch_filings_for_date")
    def test_list_filings_single_date(
        self,
        mock_fetch: Mock,
        mock_env_vars: None,
        sample_api_response: EdinetSuccessResponse,
    ) -> None:
        """Test list_filings for a single date."""
        client = EdinetClient()
        mock_fetch.return_value = sample_api_response

        start_date = datetime.date(2024, 1, 1)
        result = client.list_filings(start_date)

        mock_fetch.assert_called_once_with(start_date)
        assert len(result) == 1
        assert isinstance(result[0], FilingMetadata)

    @patch.object(EdinetClient, "_fetch_filings_for_date")
    def test_list_filings_date_range(
        self,
        mock_fetch: Mock,
        mock_env_vars: None,
        sample_api_response: EdinetSuccessResponse,
    ) -> None:
        """Test list_filings for a date range."""
        client = EdinetClient()
        mock_fetch.return_value = sample_api_response

        start_date = datetime.date(2024, 1, 1)
        end_date = datetime.date(2024, 1, 3)
        result = client.list_filings(start_date, end_date)

        # Should call fetch for each date in range
        assert mock_fetch.call_count == 3
        assert len(result) == 3  # 3 dates * 1 result per date

    @patch.object(EdinetClient, "_fetch_filings_for_date")
    def test_list_filings_handles_api_error(
        self, mock_fetch: Mock, mock_env_vars: None, error_response_data: dict[str, Any]
    ) -> None:
        """Test list_filings handles API errors correctly."""
        client = EdinetClient()
        error_response = EdinetErrorResponse(**error_response_data)
        mock_fetch.return_value = error_response

        start_date = datetime.date(2024, 1, 1)

        with pytest.raises(EdinetAuthenticationError):
            client.list_filings(start_date)


class TestFilterFilings:
    """Test filter_filings method."""

    def test_filter_filings_basic(
        self, mock_env_vars: None, sample_filing_metadata: FilingMetadata
    ) -> None:
        """Test basic filtering functionality."""
        client = EdinetClient()
        filings = [sample_filing_metadata]

        with patch(
            "src.edinet.client.filter_filings", return_value=filings
        ) as mock_filter:
            result = client.filter_filings(filings, filer_names=["Test Corporation"])

            mock_filter.assert_called_once_with(
                filings, filer_names=["Test Corporation"]
            )
            assert result == filings


class TestGetFiling:
    """Test get_filing method."""

    @patch.object(EdinetClient, "get_zip_bytes")
    @patch("src.edinet.client.BaseProcessor")
    def test_get_filing_success(
        self,
        mock_processor: Mock,
        mock_get_zip: Mock,
        mock_env_vars: None,
        sample_filing_metadata: FilingMetadata,
    ) -> None:
        """Test successful filing retrieval."""
        client = EdinetClient()
        mock_get_zip.return_value = b"test zip data"
        mock_processor.process_zip_bytes.return_value = Mock()

        result = client.get_filing(sample_filing_metadata)

        mock_get_zip.assert_called_once_with(sample_filing_metadata)
        mock_processor.process_zip_bytes.assert_called_once()
        assert result is not None

    @patch.object(EdinetClient, "get_zip_bytes")
    def test_get_filing_download_error(
        self,
        mock_get_zip: Mock,
        mock_env_vars: None,
        sample_filing_metadata: FilingMetadata,
    ) -> None:
        """Test filing retrieval with download error."""
        client = EdinetClient()
        mock_get_zip.side_effect = EdinetDocumentFetchError("Download failed")

        result = client.get_filing(sample_filing_metadata)

        assert result is None


class TestGetZipBytes:
    """Test get_zip_bytes method."""

    @patch.object(EdinetClient, "_fetch_with_retry")
    def test_get_zip_bytes_success(
        self,
        mock_fetch: Mock,
        mock_env_vars: None,
        sample_filing_metadata: FilingMetadata,
    ) -> None:
        """Test successful ZIP bytes retrieval."""
        client = EdinetClient()
        mock_response = Mock()
        mock_response.content = b"test zip content"
        mock_fetch.return_value = mock_response

        result = client.get_zip_bytes(sample_filing_metadata)

        assert result == b"test zip content"
        mock_fetch.assert_called_once()

    @patch.object(EdinetClient, "_fetch_with_retry")
    def test_get_zip_bytes_http_error(
        self,
        mock_fetch: Mock,
        mock_env_vars: None,
        sample_filing_metadata: FilingMetadata,
    ) -> None:
        """Test ZIP bytes retrieval with HTTP error."""
        client = EdinetClient()
        mock_fetch.side_effect = httpx.HTTPStatusError(
            "404", request=Mock(), response=Mock()
        )

        with pytest.raises(EdinetDocumentFetchError):
            client.get_zip_bytes(sample_filing_metadata)


class TestDownloadFilings:
    """Test download_filings method."""

    @patch.object(EdinetClient, "get_zip_bytes")
    @patch.object(EdinetClient, "save_bytes")
    def test_download_filings_success(
        self,
        mock_save: Mock,
        mock_get_zip: Mock,
        mock_env_vars: None,
        sample_filing_metadata: FilingMetadata,
    ) -> None:
        """Test successful filing downloads."""
        client = EdinetClient()
        mock_get_zip.return_value = b"test zip content"

        filings = [sample_filing_metadata]
        result = client.download_filings(filings, "/tmp/downloads")

        mock_get_zip.assert_called_once_with(sample_filing_metadata)
        mock_save.assert_called_once()
        assert len(result) == 1
        assert result[0]["status"] == "success"

    @patch.object(EdinetClient, "get_zip_bytes")
    def test_download_filings_with_errors(
        self,
        mock_get_zip: Mock,
        mock_env_vars: None,
        sample_filing_metadata: FilingMetadata,
    ) -> None:
        """Test filing downloads with errors."""
        client = EdinetClient()
        mock_get_zip.side_effect = EdinetDocumentFetchError("Download failed")

        filings = [sample_filing_metadata]
        result = client.download_filings(filings, "/tmp/downloads")

        assert len(result) == 1
        assert result[0]["status"] == "error"


class TestCacheManagement:
    """Test cache management methods."""

    def test_clear_cache_no_cache_manager(self, mock_env_vars: None) -> None:
        """Test clear_cache when cache is disabled."""
        client = EdinetClient(enable_cache=False)

        result = client.clear_cache()

        assert result["files_removed"] == 0
        assert result["message"] == "Cache is disabled"

    def test_clear_cache_with_cache_manager(self, mock_env_vars: None) -> None:
        """Test clear_cache when cache is enabled."""
        mock_cache_manager = Mock()
        mock_cache_manager.clear_all.return_value = {"files_removed": 5}

        client = EdinetClient(enable_cache=True)
        client.cache_manager = mock_cache_manager

        result = client.clear_cache()

        mock_cache_manager.clear_all.assert_called_once()
        assert result["files_removed"] == 5

    def test_clear_expired_cache_with_cache_manager(self, mock_env_vars: None) -> None:
        """Test clear_expired_cache when cache is enabled."""
        mock_cache_manager = Mock()
        mock_cache_manager.clear_expired.return_value = {"files_removed": 3}

        client = EdinetClient(enable_cache=True)
        client.cache_manager = mock_cache_manager

        result = client.clear_expired_cache()

        mock_cache_manager.clear_expired.assert_called_once()
        assert result["files_removed"] == 3

    def test_get_cache_stats_with_cache_manager(self, mock_env_vars: None) -> None:
        """Test get_cache_stats when cache is enabled."""
        mock_cache_manager = Mock()
        mock_cache_manager.get_stats.return_value = {
            "total_files": 10,
            "total_size_bytes": 1024,
        }

        client = EdinetClient(enable_cache=True)
        client.cache_manager = mock_cache_manager

        result = client.get_cache_stats()

        mock_cache_manager.get_stats.assert_called_once()
        assert result["total_files"] == 10
        assert result["total_size_bytes"] == 1024


class TestSaveBytes:
    """Test save_bytes method."""

    def test_save_bytes_success(
        self, mock_env_vars: None, temp_directory: Path
    ) -> None:
        """Test successful bytes saving."""
        client = EdinetClient()
        test_file = temp_directory / "test.txt"
        test_data = b"test content"

        client.save_bytes(test_data, str(test_file))

        assert test_file.exists()
        assert test_file.read_bytes() == test_data

    def test_save_bytes_creates_directories(
        self, mock_env_vars: None, temp_directory: Path
    ) -> None:
        """Test that save_bytes creates parent directories."""
        client = EdinetClient()
        test_file = temp_directory / "subdir" / "test.txt"
        test_data = b"test content"

        client.save_bytes(test_data, str(test_file))

        assert test_file.exists()
        assert test_file.read_bytes() == test_data


class TestPrivateMethods:
    """Test private/helper methods."""

    def test_validate_date_string(self, mock_env_vars: None) -> None:
        """Test _validate_date with string input."""
        client = EdinetClient()

        result = client._validate_date("2024-01-01")
        assert result == "2024-01-01"

    def test_validate_date_datetime(self, mock_env_vars: None) -> None:
        """Test _validate_date with datetime.date input."""
        client = EdinetClient()
        test_date = datetime.date(2024, 1, 1)

        result = client._validate_date(test_date)
        assert result == "2024-01-01"

    def test_validate_date_invalid(self, mock_env_vars: None) -> None:
        """Test _validate_date with invalid input."""
        client = EdinetClient()

        with pytest.raises(ValueError, match="Date must be a string or datetime.date"):
            client._validate_date(123)  # type: ignore

    @patch("httpx.get")
    def test_fetch_with_retry_success(
        self, mock_get: Mock, mock_env_vars: None
    ) -> None:
        """Test _fetch_with_retry with successful request."""
        client = EdinetClient()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = client._fetch_with_retry("http://test.com")

        assert result == mock_response
        mock_get.assert_called_once()

    @patch("httpx.get")
    @patch("time.sleep")
    def test_fetch_with_retry_with_retries(
        self, mock_sleep: Mock, mock_get: Mock, mock_env_vars: None
    ) -> None:
        """Test _fetch_with_retry with retries on failure."""
        client = EdinetClient(max_retries=2, delay_seconds=1)

        # First call fails, second succeeds
        mock_response_fail = Mock()
        mock_response_fail.status_code = 500
        mock_response_success = Mock()
        mock_response_success.status_code = 200

        mock_get.side_effect = [
            httpx.HTTPStatusError("500", request=Mock(), response=mock_response_fail),
            mock_response_success,
        ]

        result = client._fetch_with_retry("http://test.com")

        assert result == mock_response_success
        assert mock_get.call_count == 2
        mock_sleep.assert_called_once_with(1)

    @patch("httpx.get")
    @patch("time.sleep")
    def test_fetch_with_retry_max_retries_exceeded(
        self, mock_sleep: Mock, mock_get: Mock, mock_env_vars: None
    ) -> None:
        """Test _fetch_with_retry when max retries are exceeded."""
        client = EdinetClient(max_retries=1, delay_seconds=1)

        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.side_effect = httpx.HTTPStatusError(
            "500", request=Mock(), response=mock_response
        )

        with pytest.raises(EdinetRetryExceededError):
            client._fetch_with_retry("http://test.com")

        assert mock_get.call_count == 2  # Initial + 1 retry
        mock_sleep.assert_called_once()
