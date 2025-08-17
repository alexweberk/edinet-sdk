"""Unit tests for the config module."""

import pytest

from src import config


class TestConfigValidation:
    """Test configuration validation functions."""

    def test_validate_api_key_success(self, mock_env_vars: None) -> None:
        """Test successful API key validation."""
        api_key = config.validate_api_key()
        assert api_key == "test_api_key_12345"

    def test_validate_api_key_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test API key validation with missing environment variable."""
        monkeypatch.delenv("EDINET_API_KEY", raising=False)

        with pytest.raises(
            ValueError, match="EDINET_API_KEY environment variable is required"
        ):
            config.validate_api_key()

    def test_validate_api_key_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test API key validation with empty environment variable."""
        monkeypatch.setenv("EDINET_API_KEY", "")

        with pytest.raises(
            ValueError, match="EDINET_API_KEY environment variable is required"
        ):
            config.validate_api_key()


class TestConfigurationConstants:
    """Test configuration constants and default values."""

    def test_api_urls(self) -> None:
        """Test API URL constants."""
        assert (
            config.EDINET_API_BASE_URL == "https://disclosure.edinet-fsa.go.jp/api/v2"
        )
        assert (
            config.EDINET_DOCUMENT_API_BASE_URL == "https://api.edinet-fsa.go.jp/api/v2"
        )

    def test_api_types(self) -> None:
        """Test API type constants."""
        assert config.API_TYPE_METADATA_ONLY == "1"
        assert config.API_TYPE_METADATA_AND_RESULTS == "2"
        assert config.API_CSV_DOCUMENT_TYPE == "5"

    def test_http_status_codes(self) -> None:
        """Test HTTP status code constants."""
        assert config.HTTP_SUCCESS == 200
        assert config.HTTP_CLIENT_ERROR_START == 400
        assert config.HTTP_SERVER_ERROR_END == 600

    def test_file_processing_constants(self) -> None:
        """Test file processing constants."""
        assert config.CSV_SEPARATOR == "\t"
        assert config.ZIP_EXTENSION == ".zip"
        assert config.CSV_EXTENSION == ".csv"
        assert config.MACOS_METADATA_DIR == "__MACOSX"
        assert config.AUDITOR_REPORT_PREFIX == "jpaud"

    def test_default_limits(self) -> None:
        """Test default limit constants."""
        assert config.DEFAULT_ANALYSIS_LIMIT == 5
        assert config.MAX_TEXT_BLOCKS_FOR_ONELINER == 3
        assert config.MAX_PROMPT_CHAR_LIMIT == 8000
        assert config.CSV_ENCODING_DETECTION_BYTES == 1024

    def test_supported_document_types(self) -> None:
        """Test supported document types dictionary."""
        expected_types = {
            "160": "Semi-Annual Report",
            "140": "Quarterly Report",
            "180": "Extraordinary Report",
            "350": "Large Holding Report",
            "030": "Securities Registration Statement",
            "120": "Securities Report",
        }
        assert config.SUPPORTED_DOC_TYPES == expected_types

    def test_xbrl_element_ids(self) -> None:
        """Test XBRL element ID constants."""
        expected_ids = {
            "EDINET_CODE": "jpdei_cor:EDINETCodeDEI",
            "COMPANY_NAME_JA": "jpdei_cor:FilerNameInJapaneseDEI",
            "COMPANY_NAME_EN": "jpdei_cor:FilerNameInEnglishDEI",
            "DOCUMENT_TYPE": "jpdei_cor:DocumentTypeDEI",
            "DOCUMENT_TITLE_COVER": "jpcrp-esr_cor:DocumentTitleCoverPage",
            "DOCUMENT_TITLE": "jpcrp_cor:DocumentTitle",
        }
        assert config.XBRL_ELEMENT_IDS == expected_ids

    def test_extraordinary_report_element_ids(self) -> None:
        """Test extraordinary report specific element IDs."""
        assert isinstance(config.EXTRAORDINARY_REPORT_ELEMENT_IDS, list)
        assert (
            "jpcrp-esr_cor:ResolutionOfBoardOfDirectorsDescription"
            in config.EXTRAORDINARY_REPORT_ELEMENT_IDS
        )
        assert (
            "jpcrp-esr_cor:SummaryOfReasonForSubmissionDescription"
            in config.EXTRAORDINARY_REPORT_ELEMENT_IDS
        )

    def test_text_replacements(self) -> None:
        """Test text replacement constants."""
        expected_replacements = {
            "FULL_WIDTH_SPACE": "\u3000",
            "REGULAR_SPACE": " ",
        }
        assert config.TEXT_REPLACEMENTS == expected_replacements


class TestEnvironmentVariableDefaults:
    """Test environment variable loading with defaults."""

    def test_default_max_retries(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test default MAX_RETRIES value."""
        monkeypatch.delenv("MAX_RETRIES", raising=False)
        # Force reload the module to get fresh env var values
        import importlib

        importlib.reload(config)
        assert config.MAX_RETRIES == 3

    def test_custom_max_retries(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test custom MAX_RETRIES value."""
        monkeypatch.setenv("MAX_RETRIES", "5")
        import importlib

        importlib.reload(config)
        assert config.MAX_RETRIES == 5

    def test_default_delay_seconds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test default DELAY_SECONDS value."""
        monkeypatch.delenv("DELAY_SECONDS", raising=False)
        import importlib

        importlib.reload(config)
        assert config.DELAY_SECONDS == 5

    def test_custom_delay_seconds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test custom DELAY_SECONDS value."""
        monkeypatch.setenv("DELAY_SECONDS", "10")
        import importlib

        importlib.reload(config)
        assert config.DELAY_SECONDS == 10

    def test_default_days_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test default DAYS_BACK value."""
        monkeypatch.delenv("DAYS_BACK", raising=False)
        import importlib

        importlib.reload(config)
        assert config.DAYS_BACK == 7

    def test_custom_days_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test custom DAYS_BACK value."""
        monkeypatch.setenv("DAYS_BACK", "14")
        import importlib

        importlib.reload(config)
        assert config.DAYS_BACK == 14


class TestCacheConfiguration:
    """Test cache-related configuration."""

    def test_default_cache_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test default CACHE_ENABLED value."""
        monkeypatch.delenv("CACHE_ENABLED", raising=False)
        import importlib

        importlib.reload(config)
        assert config.CACHE_ENABLED is True

    def test_cache_enabled_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test CACHE_ENABLED set to false."""
        monkeypatch.setenv("CACHE_ENABLED", "false")
        import importlib

        importlib.reload(config)
        assert config.CACHE_ENABLED is False

    def test_cache_enabled_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test CACHE_ENABLED set to true."""
        monkeypatch.setenv("CACHE_ENABLED", "true")
        import importlib

        importlib.reload(config)
        assert config.CACHE_ENABLED is True

    def test_default_cache_dir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test default CACHE_DIR value."""
        monkeypatch.delenv("CACHE_DIR", raising=False)
        import importlib

        importlib.reload(config)
        assert config.CACHE_DIR == ".cache"

    def test_custom_cache_dir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test custom CACHE_DIR value."""
        monkeypatch.setenv("CACHE_DIR", "/tmp/test_cache")
        import importlib

        importlib.reload(config)
        assert config.CACHE_DIR == "/tmp/test_cache"

    def test_default_cache_ttl_filings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test default CACHE_TTL_FILINGS value."""
        monkeypatch.delenv("CACHE_TTL_FILINGS", raising=False)
        import importlib

        importlib.reload(config)
        assert config.CACHE_TTL_FILINGS == 86400  # 24 hours

    def test_custom_cache_ttl_filings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test custom CACHE_TTL_FILINGS value."""
        monkeypatch.setenv("CACHE_TTL_FILINGS", "43200")  # 12 hours
        import importlib

        importlib.reload(config)
        assert config.CACHE_TTL_FILINGS == 43200

    def test_default_cache_ttl_documents(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test default CACHE_TTL_DOCUMENTS value."""
        monkeypatch.delenv("CACHE_TTL_DOCUMENTS", raising=False)
        import importlib

        importlib.reload(config)
        assert config.CACHE_TTL_DOCUMENTS == 604800  # 7 days

    def test_custom_cache_ttl_documents(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test custom CACHE_TTL_DOCUMENTS value."""
        monkeypatch.setenv("CACHE_TTL_DOCUMENTS", "259200")  # 3 days
        import importlib

        importlib.reload(config)
        assert config.CACHE_TTL_DOCUMENTS == 259200
