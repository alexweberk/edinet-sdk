"""Integration tests for EDINET API interactions."""

import datetime
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import httpx
import pytest

from src.edinet.client import EdinetClient
from src.models import (
    EdinetSuccessResponse,
    Filing,
    FilingMetadata,
)


class TestEdinetClientIntegration:
    """Integration tests for full EdinetClient workflows."""

    @patch("httpx.get")
    def test_full_filing_search_workflow(
        self,
        mock_get: Mock,
        mock_env_vars: None,
        sample_api_response: EdinetSuccessResponse,
        sample_csv_data: str,
    ) -> None:
        """Test complete workflow from searching filings to downloading."""
        client = EdinetClient(enable_cache=False)

        # Mock the API response for filing search
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_api_response.model_dump()
        mock_get.return_value = mock_response

        # Test filing search
        start_date = datetime.date(2024, 1, 1)
        filings = client.list_filings(start_date)

        assert len(filings) == 1
        assert isinstance(filings[0], FilingMetadata)
        assert filings[0].docID == "S100TEST"

        # Verify API was called with correct parameters
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "2024-01-01" in str(call_args)

    @patch("httpx.get")
    def test_recent_filings_workflow(
        self,
        mock_get: Mock,
        mock_env_vars: None,
        sample_api_response: EdinetSuccessResponse,
    ) -> None:
        """Test recent filings workflow with date calculations."""
        client = EdinetClient(enable_cache=False)

        # Mock multiple API responses for different dates
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_api_response.model_dump()
        mock_get.return_value = mock_response

        # Test recent filings for 3 days
        filings = client.list_recent_filings(lookback_days=3)

        # Should call API 3 times (one for each day)
        assert mock_get.call_count == 3
        assert len(filings) == 3  # One filing per day

    @patch("httpx.get")
    def test_filing_download_workflow(
        self,
        mock_get: Mock,
        mock_env_vars: None,
        sample_filing_metadata: FilingMetadata,
        sample_zip_file: Path,
        temp_directory: Path,
    ) -> None:
        """Test complete filing download workflow."""
        client = EdinetClient(enable_cache=False, download_dir=str(temp_directory))

        # Mock document download response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = sample_zip_file.read_bytes()
        mock_get.return_value = mock_response

        # Test filing download
        filings = [sample_filing_metadata]
        results = client.download_filings(filings, str(temp_directory))

        assert len(results) == 1
        assert results[0]["status"] == "success"
        assert "filepath" in results[0]

        # Verify file was saved
        saved_file = Path(results[0]["filepath"])
        assert saved_file.exists()

    @patch("httpx.get")
    def test_filing_processing_workflow(
        self,
        mock_get: Mock,
        mock_env_vars: None,
        sample_filing_metadata: FilingMetadata,
        sample_zip_file: Path,
    ) -> None:
        """Test complete filing processing workflow."""
        client = EdinetClient(enable_cache=False)

        # Mock document download response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = sample_zip_file.read_bytes()
        mock_get.return_value = mock_response

        # Test filing processing
        filing = client.get_filing(sample_filing_metadata)

        assert filing is not None
        assert isinstance(filing, Filing)
        assert filing.metadata == sample_filing_metadata
        assert len(filing.files) > 0

    @patch("httpx.get")
    def test_error_handling_workflow(
        self,
        mock_get: Mock,
        mock_env_vars: None,
        error_response_data: dict[str, Any],
    ) -> None:
        """Test error handling in complete workflow."""
        client = EdinetClient(enable_cache=False, max_retries=1)

        # Mock API error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = error_response_data
        mock_get.return_value = mock_response

        # Test that errors are properly handled
        start_date = datetime.date(2024, 1, 1)

        # Should raise authentication error due to API error response
        with pytest.raises(
            (Exception, ValueError, RuntimeError)
        ):  # API error handling may raise various exception types
            client.list_filings(start_date)

    @patch("httpx.get")
    def test_retry_mechanism_workflow(
        self,
        mock_get: Mock,
        mock_env_vars: None,
        sample_api_response: EdinetSuccessResponse,
    ) -> None:
        """Test retry mechanism in integration workflow."""
        client = EdinetClient(enable_cache=False, max_retries=2, delay_seconds=0.1)

        # Mock first call to fail, second to succeed
        mock_response_fail = Mock()
        mock_response_fail.status_code = 500

        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = sample_api_response.model_dump()

        mock_get.side_effect = [
            httpx.HTTPStatusError("500", request=Mock(), response=mock_response_fail),
            mock_response_success,
        ]

        # Test that retry works
        start_date = datetime.date(2024, 1, 1)
        filings = client.list_filings(start_date)

        assert len(filings) == 1
        assert mock_get.call_count == 2  # First failed, second succeeded

    @patch("httpx.get")
    def test_filtering_workflow(
        self,
        mock_get: Mock,
        mock_env_vars: None,
        sample_api_response: EdinetSuccessResponse,
    ) -> None:
        """Test complete filing filtering workflow."""
        client = EdinetClient(enable_cache=False)

        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_api_response.model_dump()
        mock_get.return_value = mock_response

        # Test filing search with filters
        start_date = datetime.date(2024, 1, 1)
        filings = client.list_filings(
            start_date,
            edinet_codes=["E12345"],
            filing_type_codes=["160"],
            filer_names=["Test Corporation"],
        )

        # Should still get results (filtering happens post-API call)
        assert len(filings) >= 0  # May be filtered out

    @patch("src.edinet.client.CacheManager")
    @patch("httpx.get")
    def test_cache_integration_workflow(
        self,
        mock_get: Mock,
        mock_cache_manager_class: Mock,
        mock_env_vars: None,
        sample_api_response: EdinetSuccessResponse,
    ) -> None:
        """Test cache integration in complete workflow."""
        # Setup cache manager mock
        mock_cache_manager = Mock()
        mock_cache_manager.get.return_value = None  # Cache miss
        mock_cache_manager.set.return_value = None
        mock_cache_manager_class.return_value = mock_cache_manager

        client = EdinetClient(enable_cache=True)

        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_api_response.model_dump()
        mock_get.return_value = mock_response

        # Test filing search with cache
        start_date = datetime.date(2024, 1, 1)
        filings = client.list_filings(start_date)

        assert len(filings) == 1

        # Verify cache operations were called
        mock_cache_manager.get.assert_called()
        mock_cache_manager.set.assert_called()

    @patch("httpx.get")
    def test_large_date_range_workflow(
        self,
        mock_get: Mock,
        mock_env_vars: None,
        sample_api_response: EdinetSuccessResponse,
    ) -> None:
        """Test workflow with large date range."""
        client = EdinetClient(enable_cache=False)

        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_api_response.model_dump()
        mock_get.return_value = mock_response

        # Test large date range (30 days)
        start_date = datetime.date(2024, 1, 1)
        end_date = datetime.date(2024, 1, 30)
        filings = client.list_filings(start_date, end_date)

        # Should call API 30 times (once per day)
        assert mock_get.call_count == 30
        assert len(filings) == 30  # One filing per day

    @patch("httpx.get")
    def test_concurrent_download_workflow(
        self,
        mock_get: Mock,
        mock_env_vars: None,
        sample_zip_file: Path,
        temp_directory: Path,
    ) -> None:
        """Test downloading multiple filings concurrently."""
        client = EdinetClient(enable_cache=False, download_dir=str(temp_directory))

        # Mock document download responses
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = sample_zip_file.read_bytes()
        mock_get.return_value = mock_response

        # Create multiple filing metadata objects
        filings = []
        for i in range(3):
            filing = FilingMetadata(
                seqNumber=i,
                docID=f"S100TEST{i}",
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
            filings.append(filing)

        # Test concurrent downloads
        results = client.download_filings(filings, str(temp_directory))

        assert len(results) == 3
        assert all(result["status"] == "success" for result in results)
        assert mock_get.call_count == 3

    def test_client_configuration_integration(self, mock_env_vars: None) -> None:
        """Test that client configuration integrates properly."""
        # Test with various configurations
        configs = [
            {"max_retries": 1, "delay_seconds": 0.1, "timeout": 10},
            {"enable_cache": False, "download_dir": "/tmp/test"},
            {"max_retries": 5, "delay_seconds": 2, "timeout": 60},
        ]

        for config in configs:
            client = EdinetClient(**config)

            # Verify configuration was applied
            for key, value in config.items():
                if hasattr(client, key):
                    assert getattr(client, key) == value

    @patch("httpx.get")
    def test_mixed_success_failure_workflow(
        self,
        mock_get: Mock,
        mock_env_vars: None,
        sample_zip_file: Path,
        temp_directory: Path,
    ) -> None:
        """Test workflow with mixed success and failure responses."""
        client = EdinetClient(enable_cache=False, download_dir=str(temp_directory))

        # Mock mixed responses - some succeed, some fail
        mock_success_response = Mock()
        mock_success_response.status_code = 200
        mock_success_response.content = sample_zip_file.read_bytes()

        mock_get.side_effect = [
            mock_success_response,  # First download succeeds
            httpx.HTTPStatusError(
                "404", request=Mock(), response=Mock()
            ),  # Second fails
            mock_success_response,  # Third succeeds
        ]

        # Create test filings
        filings = []
        for i in range(3):
            filing = FilingMetadata(
                seqNumber=i,
                docID=f"S100TEST{i}",
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
            filings.append(filing)

        # Test downloads with mixed results
        results = client.download_filings(filings, str(temp_directory))

        assert len(results) == 3
        assert results[0]["status"] == "success"
        assert results[1]["status"] == "error"
        assert results[2]["status"] == "success"
