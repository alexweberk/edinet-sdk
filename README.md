# EDINET SDK

A Python SDK for fetching and processing Japanese corporate financial disclosure documents from the EDINET API.

## Setup

1. Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. Install dependencies: `uv sync`
3. Create a `.env` file and set your `EDINET_API_KEY`
4. Run the CLI: `uv run python main.py`

## CLI Usage

**Demo mode (fetches recent documents):**
```bash
uv run python main.py
```

**Company date range query:**
```bash
uv run python main.py --edinet-code <EDINET_CODE> --start-date <YYYY-MM-DD> --end-date <YYYY-MM-DD>
```

**Optional flags:**
- `--doc-types`: Comma-separated document type codes (e.g., "160,180")
- `--output`: Output file path for JSON results

## Development

```bash
uv run ruff check .      # Linting
uv run ruff format .     # Formatting
```


## Disclaimer

This project is an independent tool and is not affiliated with, endorsed by, or in any way officially connected with the Financial Services Agency (FSA) of Japan or any of its subsidiaries or affiliates.

We are grateful to the Financial Services Agency for creating and maintaining the EDINET v2 API.

The official EDINET website: [https://disclosure2.edinet-fsa.go.jp/](https://disclosure2.edinet-fsa.go.jp/).

This software is provided "as is" for informational purposes only. The creator assumes no liability for errors, omissions, or any consequences of using this software. This tool does not provide financial advice. Users are solely responsible for verifying information and for any decisions made based on it. Use at your own risk.

## License

This project is licensed under the MIT License.
