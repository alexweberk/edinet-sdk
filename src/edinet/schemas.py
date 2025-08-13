"""EDINET API schemas and exception classes."""

import logging
from typing import Any

from pydantic import BaseModel

# successful_response = {
#     "metadata": {
#         "title": "提出された書類を把握するためのAPI",
#         "parameter": {"date": "2025-08-11", "type": "2"},
#         "resultset": {"count": 0},
#         "processDateTime": "2025-08-13 00:32",
#         "status": "200",
#         "message": "OK",
#     },
#     "results": [],
# }


# error_response = {
#     "statusCode": 401,
#     "message": "Access denied due to invalid subscription key.Make sure to provide a valid key for an active subscription.",
# }


class DocMetadata(BaseModel):
    """Metadata structure for EDINET API responses."""

    # {
    #     "seqNumber": 1,
    #     "docID": "S100WGLE",
    #     "edinetCode": "E40761",
    #     "secCode": None,
    #     "JCN": "7010401190011",
    #     "filerName": "ＯＰＩ・１８株式会社",
    #     "fundCode": None,
    #     "ordinanceCode": "040",
    #     "formCode": "060007",
    #     "docTypeCode": "270",
    #     "periodStart": None,
    #     "periodEnd": None,
    #     "submitDateTime": "2025-08-05 09:00",
    #     "docDescription": "公開買付報告書",
    #     "issuerEdinetCode": None,
    #     "subjectEdinetCode": "E33109",
    #     "subsidiaryEdinetCode": None,
    #     "currentReportReason": None,
    #     "parentDocID": "S100VYQI",
    #     "opeDateTime": None,
    #     "withdrawalStatus": "0",
    #     "docInfoEditStatus": "0",
    #     "disclosureStatus": "0",
    #     "xbrlFlag": "1",
    #     "pdfFlag": "1",
    #     "attachDocFlag": "0",
    #     "englishDocFlag": "0",
    #     "csvFlag": "1",
    #     "legalStatus": "1",
    # }

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


class Doc(BaseModel):
    """Document structure for EDINET API responses."""

    # TODO: Implement
    pass


# TypedDict definitions based on actual API responses
class EdinetMetadata(BaseModel):
    """Metadata structure for EDINET API responses."""

    title: str
    parameter: dict[str, Any]  # Contains date, type, etc.
    resultset: dict[str, int]  # Contains count
    processDateTime: str  # noqa: N815
    status: str
    message: str


class EdinetSuccessResponse(BaseModel):
    """Successful response structure from EDINET API."""

    metadata: EdinetMetadata
    results: list[DocMetadata]  # List of document results


class EdinetErrorResponse(BaseModel):
    """Error response structure from EDINET API."""

    statusCode: int  # noqa: N815
    message: str


# Type alias for any EDINET API response
EdinetResponse = EdinetSuccessResponse | EdinetErrorResponse


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
