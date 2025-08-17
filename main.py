import argparse
import logging

from src.edinet.client import EdinetClient
from src.utils import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="EDINET SDK - Fetch and process Japanese financial disclosure documents"
    )

    # Company date range query flags
    parser.add_argument(
        "--company-name",
        type=str,
        help="Name of the company to filter filings for",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=7,
        help="Number of days to look back for recent filings",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    edinet_client = EdinetClient()

    all_filings = edinet_client.list_recent_filings(
        lookback_days=args.lookback_days,
        filer_names=[args.company_name],
    )

    print("Here are the target filings:")
    print(all_filings)
