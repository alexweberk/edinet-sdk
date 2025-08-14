# EDINET SDK

A Python SDK for fetching and processing Japanese corporate financial disclosure documents from the EDINET API.

## Setup

1. Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. Install dependencies: `uv sync`
3. Create a `.env` file and set your `EDINET_API_KEY`
4. Run the CLI: `uv run python main.py`

## CLI Usage

**Default mode (lists recent filings):**
```bash
uv run python main.py
```

**Company filtering mode:**
```bash
uv run python main.py --company-name "Toyota Motor Corporation"
```

**Optional flags:**
- `--lookback-days`: Number of days to look back (default: 7)
- `--filing-types`: Comma-separated filing type codes (e.g., "160,180")

## Development

```bash
uv run ruff check .      # Linting
uv run ruff format .     # Formatting
```

## SDK Usage

```python
from src.edinet.client import EdinetClient

# Initialize client
client = EdinetClient()

# Get recent filings
recent_filings = client.list_recent_filings(lookback_days=7)

# Filter by company
company_filings = client.filter_filings(
    recent_filings,
    filer_names=["Toyota Motor Corporation"]
)

# Download filings
client.download_filings(company_filings, "downloads/")
```

## Architecture

This SDK provides a simplified interface to Japan's EDINET API v2:

- **`EdinetClient`**: Main API client with methods for listing, filtering, and downloading filings
- **Filtering**: Built-in support for filtering by company name, document type, date ranges
- **Processing**: Consolidated document processor for extracting structured data from CSV files
- **Error Handling**: Comprehensive retry logic and error handling throughout

## Disclaimer

This project is an independent tool and is not affiliated with, endorsed by, or in any way officially connected with the Financial Services Agency (FSA) of Japan or any of its subsidiaries or affiliates.

We are grateful to the Financial Services Agency for creating and maintaining the EDINET v2 API.

The official EDINET website: [https://disclosure2.edinet-fsa.go.jp/](https://disclosure2.edinet-fsa.go.jp/).

This software is provided "as is" for informational purposes only. The creator assumes no liability for errors, omissions, or any consequences of using this software. This tool does not provide financial advice. Users are solely responsible for verifying information and for any decisions made based on it. Use at your own risk.

## License

This project is licensed under the MIT License.
