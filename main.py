import argparse
import json
import logging
import sys
from datetime import datetime, timedelta

from src.config import DAYS_BACK, DEFAULT_DOWNLOAD_DIR, SUPPORTED_DOC_TYPES
from src.edinet.client import EdinetClient
from src.edinet.utils import setup_logging
from src.processors.base_processor import BaseDocumentProcessor

setup_logging()
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="EDINET SDK - Fetch and process Japanese financial disclosure documents"
    )

    # Company date range query flags
    parser.add_argument(
        "--edinet-code",
        type=str,
        help="EDINET code for the company to fetch documents for",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date for the date range (YYYY-MM-DD format)",
    )
    parser.add_argument(
        "--end-date", type=str, help="End date for the date range (YYYY-MM-DD format)"
    )
    parser.add_argument(
        "--doc-types",
        type=str,
        help="Comma-separated list of document type codes to include (e.g., 160,180)",
    )
    parser.add_argument(
        "--output", type=str, help="Optional output file path to write JSON results"
    )

    return parser.parse_args()


def run_company_date_range_query(args):
    """Run the company date range query based on CLI arguments."""
    # Parse doc types if provided
    doc_type_codes = None
    if args.doc_types:
        doc_type_codes = [code.strip() for code in args.doc_types.split(",")]
        logger.info(f"Filtering for document types: {doc_type_codes}")

    try:
        edinet_client = EdinetClient()
        # Call the new function
        structured_data = edinet_client.get_structured_data_for_company_date_range(
            edinet_code=args.edinet_code,
            start_date=args.start_date,
            end_date=args.end_date,
        )

        # Convert to JSON
        json_output = json.dumps(structured_data, indent=2, ensure_ascii=False)

        # Print to stdout
        print(json_output)

        # Also write to file if output path is provided
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(json_output)
            logger.info(f"JSON output also written to: {args.output}")

        logger.info(f"Successfully processed {len(structured_data)} documents")

    except Exception as e:
        logger.error(f"Error during company date range query: {e}")
        sys.exit(1)


def run_demo() -> None:
    """Runs the main demo workflow."""
    logger.info("=" * 80)
    logger.info("EDINET API x Structured LLM Analysis Demo")
    logger.info("=" * 80)

    logger.info("Initializing...")

    # Define document types to look for
    # Only fetch document types for which we have specific processors to ensure
    # get_structured_data_from_zip_directory can create meaningful structured data.
    # If you want to fetch other types, ensure GenericReportProcessor is sufficient,
    # or add specific processors in document_processors.py
    doc_type_codes_to_fetch = [
        # "140",  # Quarterly Reports
        "160",  # Semi-Annual Reports
        "180",  # Extraordinary Reports
    ]

    days_back = DAYS_BACK

    edinet_client = EdinetClient()

    # Fetch the most recent documents of the specified types
    docs_metadata = edinet_client.list_docs(
        start_date=datetime.now() - timedelta(days=days_back),
        end_date=datetime.now(),
        doc_type_codes=doc_type_codes_to_fetch,
    )

    if not docs_metadata:
        logger.error(
            f"No documents found meeting criteria in the last {days_back} days. Exiting demo."
        )
        return

    download_dir = DEFAULT_DOWNLOAD_DIR

    # download_documents function handles creating the directory
    edinet_client.download_documents(docs_metadata, download_dir)

    # Process the downloaded zip files into structured data
    # We pass the keys of SUPPORTED_DOC_TYPES because process_zip_directory
    # uses process_structured_data_from_raw_csv which dispatches based on these codes.
    structured_document_data_list = BaseDocumentProcessor.process_zip_directory(
        download_dir, doc_type_codes=list(SUPPORTED_DOC_TYPES.keys())
    )

    # Filter out metadata for documents that failed processing
    processed_doc_ids = {
        data.get("doc_id")
        for data in structured_document_data_list
        if data.get("doc_id")
    }
    docs_metadata_for_processed = [
        doc for doc in docs_metadata if doc.docID in processed_doc_ids
    ]

    if not docs_metadata_for_processed:
        logger.error(
            "No documents were successfully processed into structured data. Exiting demo."
        )
        return

    logger.info(f"\n{'*' * 80}")
    logger.info("Document Processing Summary")
    logger.info(f"{'*' * 80}")

    # Display summary of processed documents
    for i, doc_meta in enumerate(docs_metadata_for_processed, 1):
        doc_id = doc_meta.docID
        doc_type_code = doc_meta.docTypeCode
        company_name = doc_meta.filerName or "Unknown Company"
        doc_type_name = SUPPORTED_DOC_TYPES.get(
            str(doc_type_code) if doc_type_code else "",
            str(doc_type_code) if doc_type_code else "Unknown",
        )
        submit_date_time_str = doc_meta.submitDateTime or "Date N/A"

        print(f"{i}. {company_name} - {doc_type_name} (ID: {doc_id})")
        print(f"   Submitted: {submit_date_time_str}")

    print(f"\n{'=' * 80}")
    logger.info(
        f"Demo run complete. Successfully processed {len(docs_metadata_for_processed)} documents."
    )


if __name__ == "__main__":
    args = parse_args()

    # Check if any company date range query flags are provided
    company_query_flags = [args.edinet_code, args.start_date, args.end_date]
    if any(company_query_flags):
        # Validate that all required flags are provided
        if not all([args.edinet_code, args.start_date, args.end_date]):
            logger.error(
                "When using company date range query mode, --edinet-code, --start-date, and --end-date are all required"
            )
            sys.exit(1)

        logger.info("Running company date range query mode...")
        run_company_date_range_query(args)
    else:
        # No flags provided, run the existing demo
        logger.info("No CLI flags provided, running demo mode...")
        run_demo()
