import logging
from typing import Any

from src.config import EXTRAORDINARY_REPORT_ELEMENT_IDS
from src.processors.base_processor import BaseProcessor, StructuredDocData

logger = logging.getLogger(__name__)


class ExtraordinaryReportProcessor(BaseProcessor):
    """Processor for Extraordinary Reports (doc_type_code '180')."""

    doc_type_code = "180"

    @staticmethod
    def process(
        all_records: list[dict[str, Any]],
        doc_id: str,
        doc_type_code: str,
    ) -> StructuredDocData | None:
        """Extract key data points and text blocks for Extraordinary Reports."""

        logger.debug(f"Processing Extraordinary Report (doc_id: {doc_id})")
        structured_data = ExtraordinaryReportProcessor._get_common_metadata(
            all_records, doc_id, doc_type_code
        )

        # Extract specific facts often found in Extraordinary Reports
        key_facts = {}
        # Look for elements related to decisions, resolutions, changes, M&A
        for element_id in EXTRAORDINARY_REPORT_ELEMENT_IDS:
            value = ExtraordinaryReportProcessor.get_value_by_id(
                all_records, element_id
            )
            if value is not None:
                # Use a cleaner key name for the fact
                fact_key = (
                    element_id.split(":")[-1]
                    .replace("Description", "")
                    .replace("SummaryOf", "")
                    .replace("DetailsOf", "")
                    .replace("RationaleFor", "")
                    .replace("ImpactOnBusinessResults", "ImpactOnResults")
                )
                key_facts[fact_key] = value

        structured_data["key_facts"] = key_facts
        structured_data["text_blocks"] = (
            ExtraordinaryReportProcessor.get_all_text_blocks(all_records)
        )  # Include all text blocks as well

        logger.debug(
            f"Finished processing Extraordinary Report {doc_id}."
            f"Extracted {len(key_facts)} key facts and {len(structured_data['text_blocks'])} text blocks."
        )
        return structured_data if structured_data else None
