"""Unit tests for the utils module."""

import logging
from io import StringIO

from src import utils


class TestSetupLogging:
    """Test logging setup functionality."""

    def test_setup_logging_configuration(self) -> None:
        """Test that logging is configured correctly."""
        # Clear any existing handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Setup logging
        utils.setup_logging()

        # Verify configuration
        assert root_logger.level == logging.INFO
        assert len(root_logger.handlers) == 1
        assert isinstance(root_logger.handlers[0], logging.StreamHandler)

    def test_setup_logging_format(self) -> None:
        """Test that log messages are formatted correctly."""
        # Capture log output
        log_stream = StringIO()

        # Clear existing handlers and add our test handler
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        test_handler = logging.StreamHandler(log_stream)
        from src.config import LOG_FORMAT

        test_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        root_logger.addHandler(test_handler)
        root_logger.setLevel(logging.INFO)

        # Log a test message
        logging.info("Test message")

        # Check that the output contains expected format components
        log_output = log_stream.getvalue()
        assert "Test message" in log_output
        assert "INFO" in log_output


class TestCleanText:
    """Test text cleaning functionality."""

    def test_clean_text_none_input(self) -> None:
        """Test clean_text with None input."""
        result = utils.clean_text(None)
        assert result is None

    def test_clean_text_empty_string(self) -> None:
        """Test clean_text with empty string."""
        result = utils.clean_text("")
        assert result == ""

    def test_clean_text_normal_string(self) -> None:
        """Test clean_text with normal string."""
        result = utils.clean_text("Normal text")
        assert result == "Normal text"

    def test_clean_text_full_width_space(self) -> None:
        """Test clean_text replaces full-width spaces with regular spaces."""
        # Use proper Unicode escape sequence for full-width space
        full_width_space = "\u3000"
        text_with_full_width = f"Text{full_width_space}with{full_width_space}full{full_width_space}width{full_width_space}spaces"
        result = utils.clean_text(text_with_full_width)
        assert result == "Text with full width spaces"

    def test_clean_text_mixed_spaces(self) -> None:
        """Test clean_text with mixed space types."""
        full_width_space = "\u3000"
        text_mixed = f"Normal space{full_width_space}full width space regular space"
        result = utils.clean_text(text_mixed)
        assert result == "Normal space full width space regular space"

    def test_clean_text_only_full_width_spaces(self) -> None:
        """Test clean_text with only full-width spaces."""
        full_width_space = "\u3000"
        text_only_fw = full_width_space * 3
        result = utils.clean_text(text_only_fw)
        assert result == "   "

    def test_clean_text_japanese_text(self) -> None:
        """Test clean_text with Japanese text containing full-width spaces."""
        full_width_space = "\u3000"
        japanese_text = (
            f"株式会社{full_width_space}テスト{full_width_space}コーポレーション"
        )
        result = utils.clean_text(japanese_text)
        assert result == "株式会社 テスト コーポレーション"

    def test_clean_text_preserves_other_unicode(self) -> None:
        """Test that clean_text preserves other Unicode characters."""
        unicode_text = "Text with emojis 🚀 and àccénts"
        result = utils.clean_text(unicode_text)
        assert result == unicode_text  # Should be unchanged


class TestSnakeToCamel:
    """Test snake_case to camelCase conversion functionality."""

    def test_snake_to_camel_simple(self) -> None:
        """Test simple snake_case to camelCase conversion."""
        result = utils.snake_to_camel("hello_world")
        assert result == "helloWorld"

    def test_snake_to_camel_single_word(self) -> None:
        """Test single word conversion."""
        result = utils.snake_to_camel("hello")
        assert result == "hello"

    def test_snake_to_camel_multiple_underscores(self) -> None:
        """Test conversion with multiple underscores."""
        result = utils.snake_to_camel("this_is_a_long_variable_name")
        assert result == "thisIsALongVariableName"

    def test_snake_to_camel_with_trailing_s_default(self) -> None:
        """Test conversion with trailing 's' using default behavior."""
        result = utils.snake_to_camel("user_accounts")
        assert result == "userAccount"  # 's' removed by default

    def test_snake_to_camel_with_trailing_s_keep(self) -> None:
        """Test conversion with trailing 's' when explicitly keeping it."""
        result = utils.snake_to_camel("user_accounts", remove_trailing_s=False)
        assert result == "userAccounts"

    def test_snake_to_camel_with_trailing_s_remove(self) -> None:
        """Test conversion with trailing 's' when explicitly removing it."""
        result = utils.snake_to_camel("user_accounts", remove_trailing_s=True)
        assert result == "userAccount"

    def test_snake_to_camel_no_trailing_s(self) -> None:
        """Test conversion without trailing 's'."""
        result = utils.snake_to_camel("user_account")
        assert result == "userAccount"

    def test_snake_to_camel_no_trailing_s_keep_flag(self) -> None:
        """Test conversion without trailing 's' with keep flag."""
        result = utils.snake_to_camel("user_account", remove_trailing_s=False)
        assert result == "userAccount"

    def test_snake_to_camel_empty_string(self) -> None:
        """Test conversion with empty string."""
        result = utils.snake_to_camel("")
        assert result == ""

    def test_snake_to_camel_only_underscores(self) -> None:
        """Test conversion with only underscores."""
        result = utils.snake_to_camel("___")
        assert result == ""

    def test_snake_to_camel_leading_underscore(self) -> None:
        """Test conversion with leading underscore."""
        result = utils.snake_to_camel("_hello_world")
        assert (
            result == "HelloWorld"
        )  # First part becomes empty, so second part is first

    def test_snake_to_camel_trailing_underscore(self) -> None:
        """Test conversion with trailing underscore."""
        result = utils.snake_to_camel("hello_world_")
        assert result == "helloWorld"  # Last part becomes empty

    def test_snake_to_camel_consecutive_underscores(self) -> None:
        """Test conversion with consecutive underscores."""
        result = utils.snake_to_camel("hello__world")
        assert result == "helloWorld"  # Empty parts are handled gracefully

    def test_snake_to_camel_numbers(self) -> None:
        """Test conversion with numbers."""
        result = utils.snake_to_camel("test_123_value")
        assert result == "test123Value"

    def test_snake_to_camel_mixed_case_input(self) -> None:
        """Test conversion with mixed case input."""
        result = utils.snake_to_camel("Hello_WORLD_test")
        assert result == "helloWorldTest"

    def test_snake_to_camel_special_characters(self) -> None:
        """Test conversion with special characters in words."""
        result = utils.snake_to_camel("test_value@123_end")
        assert result == "testValue@123End"
