# document_processors.py
import logging
from typing import Any

from src.processors.base_processor import BaseProcessor, StructuredDocData

logger = logging.getLogger(__name__)


class GenericReportProcessor(BaseProcessor):
    """Processor for other document types (default)."""

    doc_type_code = None

    @staticmethod
    def process(
        all_records: list[dict[str, Any]],
        doc_id: str,
        doc_type_code: str,
    ) -> StructuredDocData | None:
        """Extract common metadata and all text blocks for generic reports."""

        logger.debug(
            f"Processing Generic Report (doc_id: {doc_id}, type: {doc_type_code})"
        )
        structured_data = GenericReportProcessor._get_common_metadata(
            all_records, doc_id, doc_type_code
        )
        structured_data[
            "key_facts"
        ] = {}  # Generic reports might not have standardized facts
        structured_data["financial_tables"] = []  # Or standardized tables

        # For generic reports, primarily extract all text blocks
        structured_data["text_blocks"] = GenericReportProcessor.get_all_text_blocks(
            all_records
        )

        logger.debug(
            f"Finished processing Generic Report {doc_id}."
            f"Extracted {len(structured_data['text_blocks'])} text blocks."
        )
        return structured_data if structured_data else None
