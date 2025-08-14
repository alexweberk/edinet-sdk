"""EDINET API schemas and exception classes."""

import logging
from collections.abc import Hashable
from typing import Any

from pydantic import BaseModel, field_validator

from src.utils import clean_text

StructuredDocData = dict[str, Any]

# Example record:
# {
#     "要素ID": "jppfs_cor:SalariesAndAllowancesSGA",
#     "項目名": "給料及び手当、販売費及び一般管理費",
#     "コンテキストID": "CurrentYTDDuration",
#     "相対年度": "当四半期累計期間",
#     "連結・個別": "連結",
#     "期間・時点": "期間",
#     "ユニットID": "JPY",
#     "単位": "円",
#     "値": "1044176000",
# }
Record = dict[Hashable, Any]
CsvFileAsRecords = list[Record]

# TODO: Remove FilenameRecords and replace with Filing
# Instead of having a FilenameRecord which lacks the metadata for the filing,
# We will define methods in terms of the Filing class.
FilenameRecords = dict[str, CsvFileAsRecords]


class File(BaseModel):
    """A single document within a filing."""

    filename: str
    records: CsvFileAsRecords


class FilingMetadata(BaseModel):
    """
    Metadata structure for EDINET API responses for documents.
    Note that a "document" is a zip file that could contain multiple files.
    """

    seqNumber: int  # noqa: N815
    docID: str  # noqa: N815
    edinetCode: str | None  # noqa: N815
    secCode: str | None  # noqa: N815
    JCN: str | None
    filerName: str | None  # noqa: N815
    fundCode: str | None  # noqa: N815
    ordinanceCode: str | None  # noqa: N815
    formCode: str | None  # noqa: N815
    docTypeCode: str | None  # noqa: N815
    periodStart: str | None  # noqa: N815
    periodEnd: str | None  # noqa: N815
    submitDateTime: str | None  # noqa: N815
    docDescription: str | None  # noqa: N815
    issuerEdinetCode: str | None  # noqa: N815
    subjectEdinetCode: str | None  # noqa: N815
    subsidiaryEdinetCode: str | None  # noqa: N815
    currentReportReason: str | None  # noqa: N815
    parentDocID: str | None  # noqa: N815
    opeDateTime: str | None  # noqa: N815
    withdrawalStatus: str  # noqa: N815
    docInfoEditStatus: str  # noqa: N815
    disclosureStatus: str  # noqa: N815
    xbrlFlag: str  # noqa: N815
    pdfFlag: str  # noqa: N815
    attachDocFlag: str  # noqa: N815
    englishDocFlag: str  # noqa: N815
    csvFlag: str  # noqa: N815
    legalStatus: str  # noqa: N815

    @field_validator(
        "filerName", "docDescription", "currentReportReason", mode="before"
    )
    @classmethod
    def clean_text_fields(cls, v):
        """Clean text fields that may contain full-width spaces."""
        return clean_text(v)


class Filing(BaseModel):
    """
    A filing  for EDINET API responses.
    A filing is a zip file that could contain multiple files.
    """

    metadata: FilingMetadata
    files: list[File]

    def get_filenames(self) -> list[str]:
        """Get the filenames of the files in the document."""
        return [file.filename for file in self.files]

    def get_data(self, filename: str) -> CsvFileAsRecords:
        """Get the data for a given filename."""
        for file in self.files:
            if file.filename == filename:
                return file.records
        raise ValueError(f"File {filename} not found in filing.")


# Response models


# TypedDict definitions based on actual API responses
class EdinetMetadata(BaseModel):
    """
    Metadata structure for EDINET API responses.
    This is the metadata for the response itself, separate from the metadata for the filing.
    """

    title: str
    parameter: dict[str, Any]  # Contains date, type, etc.
    resultset: dict[str, int]  # Contains count
    processDateTime: str  # noqa: N815
    status: str
    message: str


class EdinetSuccessResponse(BaseModel):
    """Successful response structure from EDINET API."""

    metadata: EdinetMetadata
    results: list[FilingMetadata]  # List of document results


class EdinetErrorResponse(BaseModel):
    """Error response structure from EDINET API."""

    statusCode: int  # noqa: N815
    message: str


# Type alias for any EDINET API response
EdinetResponse = EdinetSuccessResponse | EdinetErrorResponse


# Exception classes


class EdinetAPIError(Exception):
    """Base exception for EDINET API related errors."""

    pass


class EdinetAuthenticationError(EdinetAPIError):
    """Raised when authentication to EDINET API fails."""

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
