# Custom exception classes
import logging


class EdinetAPIError(Exception):
    """Base exception for EDINET API related errors."""

    pass


class EdinetConnectionError(EdinetAPIError):
    """Raised when connection to EDINET API fails."""

    pass


class EdinetDocumentFetchError(EdinetAPIError):
    """Raised when document fetching from EDINET API fails."""

    pass


class EdinetRetryExceededError(EdinetAPIError):
    """Raised when maximum retry attempts are exceeded."""

    pass


class ValidationError(Exception):
    """Raised when data validation fails."""

    pass


# Simplified error handling utilities
class ErrorContext:
    """Context manager for consistent error handling."""

    def __init__(
        self,
        operation_name: str,
        logger_instance: logging.Logger,
        reraise: bool = True,
    ):
        self.operation_name = operation_name
        self.logger = logger_instance
        self.reraise = reraise

    def __enter__(self):
        self.logger.debug(f"Starting operation: {self.operation_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.logger.error(
                f"Operation '{self.operation_name}' failed: {exc_val}",
                exc_info=(exc_type, exc_val, exc_tb),
            )
            if not self.reraise:
                return True  # Suppress exception
        else:
            self.logger.debug(
                f"Operation completed successfully: {self.operation_name}"
            )
        return False  # Don't suppress exception
