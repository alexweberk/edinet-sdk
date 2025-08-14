# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

This is a Python project using UV for package management with pyproject.toml configuration.

**Running main.py:**
```bash
uv run python main.py                    # Run with default settings
uv run python main.py --help            # Show available CLI options
```

**Company filtering mode:**
```bash
uv run python main.py --company-name "Toyota Motor Corporation"
uv run python main.py --company-name "Sony Group" --lookback-days 14 --filing-types "160,180"
```

**Installing dependencies:**
```bash
uv sync
```

**Linting and code formatting:**
```bash
uv run ruff check .      # Check linting
uv run ruff format .     # Format code
uv run ruff check . --fix # Auto-fix issues
```

**Pre-commit hooks:**
```bash
uv run pre-commit install        # Install git hooks
uv run pre-commit run --all-files # Run on all files
```


## Architecture Overview

This project provides a Python SDK for interacting with Japan's EDINET API v2 to fetch, download, and process financial disclosure documents.

### Core Architecture Components

**Data Flow Pipeline:**
1. **EDINET API Interaction** (`src/edinet/client.py`) → Fetch filing metadata and download documents
2. **Filing Filtering** (`src/edinet/funcs.py`) → Filter filings by criteria (company, type, etc.)
3. **Data Processing** (`src/utils.py`) → Extract and clean CSV data from ZIP archives
4. **Document Processing** (`src/processors/base_processor.py`) → Transform raw CSV into structured data

### Key Modules

- **`src/edinet/client.py`**: EDINET API client with retry logic and error handling
- **`src/edinet/decorators.py`**: API error handling decorators
- **`src/edinet/funcs.py`**: Filing filtering utilities and helper functions
- **`src/processors/base_processor.py`**: Consolidated document processor with all processing logic
- **`src/utils.py`**: File processing utilities (encoding detection, CSV parsing, text cleaning, logging setup)
- **`src/config.py`**: Configuration including API URLs, constants, and document types
- **`src/models.py`**: Pydantic data models for API responses and document metadata

### Document Processing System

The processing system has been simplified to use a single consolidated processor:
- All document processing logic is now contained in `BaseProcessor` in `src/processors/base_processor.py`
- Uses static methods with explicit data parameters (no instance variables)
- Processors are purely functional - they don't maintain any internal state
- Generic processing handles all document types with common extraction patterns
- Document-specific logic can be added as static methods within the base processor

### SDK Architecture

The SDK provides a clean, simplified interface:
- `EdinetClient` class handles all API interactions with comprehensive error handling
- Built-in retry logic and proper logging throughout
- New methods: `list_recent_filings()` and `filter_filings()` for easier workflow
- Consolidated document processing in a single processor class
- Functional approach with static methods for better testability

## Configuration Requirements

The project uses Pydantic-based configuration validation with comprehensive error checking.

**Required Environment Variables:**
- `EDINET_API_KEY`: Japan EDINET API access key (required)

**Optional Processing Configuration:**
- `MAX_RETRIES`: Maximum retry attempts (default: 3)
- `DELAY_SECONDS`: Delay between retries in seconds (default: 5)

## Entry Points and CLI Usage

The application provides a simplified filing search interface:

**Default Mode:**
- Lists recent filings from the last 7 days
- Usage: `uv run python main.py`

**Company Filtering Mode:**
- Fetches recent filings and filters by company name
- Supports custom lookback period and filing type filtering
- Usage: `uv run python main.py --company-name "Company Name" --lookback-days 14 --filing-types "160,180"`

## Supported Document Types

Defined in `src/config.py:SUPPORTED_DOC_TYPES`:
- 160: Semi-Annual Report
- 140: Quarterly Report
- 180: Extraordinary Report
- 350: Large Holding Report
- 030: Securities Registration Statement
- 120: Securities Report

## Using the SDK

The SDK provides a simplified class-based interface:

```python
from src.edinet.client import EdinetClient

# Basic usage - get recent filings
client = EdinetClient()
recent_filings = client.list_recent_filings(lookback_days=7)

# Filter filings by company
filtered_filings = client.filter_filings(
    recent_filings,
    filer_names=["Toyota Motor Corporation"]
)

# Get filings for a specific date range
filings = client.list_filings(
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 1, 31),
    edinet_codes=['E12345']
)

# Download filings
client.download_filings(filings, "downloads/")
```

## Adding Document-Specific Processing Logic

Document processing is now consolidated in the `BaseProcessor` class. To add new processing logic:

1. Add static methods to `BaseProcessor` in `src/processors/base_processor.py`
2. Implement document-specific extraction using existing helper methods: `get_value_by_id()`, `get_all_text_blocks()`, `_get_common_metadata()`
3. Use conditional logic based on `doc_type_code` parameter to handle different document types
4. All methods should be static and functional - no instance variables

## Project Structure

```
edinet-sdk/
├── src/                           # Main source code
│   ├── __init__.py                # Package initialization
│   ├── config.py                  # Configuration and constants
│   ├── models.py                  # Pydantic data models
│   ├── utils.py                   # File processing utilities and logging setup
│   ├── edinet/                    # EDINET API integration
│   │   ├── __init__.py            # Package initialization
│   │   ├── client.py              # EDINET API client with retry logic
│   │   ├── decorators.py          # API error handling decorators
│   │   ├── funcs.py               # Filing filtering utilities
│   │   └── doc_metadata_example.py # Example document metadata
│   └── processors/                # Document processing
│       ├── __init__.py            # Package initialization
│       └── base_processor.py      # Consolidated document processor
├── main.py                        # CLI entry point
├── main.ipynb                     # Jupyter notebook for exploration
├── pyproject.toml                 # UV package configuration
├── downloads/                     # Downloaded ZIP files storage
└── docs/                          # Additional documentation
```

## Error Handling and Logging

The project implements comprehensive error handling:

- **Custom Exceptions**: Specific exception types in `src/models.py` for different error categories
- **Error Decorators**: `@handle_api_errors` decorator in `src/edinet/decorators.py` for API error handling
- **Centralized Logging**: Logging setup in `src/utils.py` with consistent configuration
- **Graceful Degradation**: Failed operations are logged and don't crash the entire pipeline

## Data Flow Details

**1. Filing Discovery:**
- `EdinetClient.list_recent_filings()` or `EdinetClient.list_filings()` query EDINET API for filing metadata
- Returns list of `FilingMetadata` objects with docID, docTypeCode, filerName, etc.

**2. Filing Filtering:**
- `EdinetClient.filter_filings()` applies filtering criteria using `src/edinet/funcs.py`
- Supports filtering by company name, EDINET codes, document types, etc.

**3. Document Download:**
- `EdinetClient.download_filings()` downloads ZIP files to specified directory
- Uses filename format: `{docID}-{docTypeCode}-{filerName}.zip`

**4. Document Processing:**
- `BaseProcessor` in `src/processors/base_processor.py` processes ZIP files
- Extracts CSV files, skips auditor reports (jpaud* files)
- Applies generic processing logic to extract structured data

## Python Coding Conventions
- Use Python 3.12>= style type hinting. For example, use `str | None` instead of `Optional[str]`.
- Always position public methods at the top of the file and private methods at the bottom.

## Implementation Learnings: Company Date Range Query Feature

### Key Insights from Issue #2 Implementation

**Unexpected Challenge: Import Organization Complexity**
- *Expectation*: Simple import additions would suffice
- *Reality*: Ruff's strict import sorting required careful attention to import order and formatting
- *Learning*: The project uses aggressive linting that automatically reorganizes imports, requiring multiple formatting passes

**Surprise: Existing Architecture Was Perfectly Suited**
- *Expectation*: Would need to modify or extend existing functions significantly
- *Reality*: The existing `get_documents_for_date_range` function already supported filtering by `edinet_codes` as a list, making the implementation straightforward
- *Learning*: The modular architecture with clear separation between API calls, downloading, and processing made composition trivial

**Testing Reality vs Expectations**
- *Expectation*: Would need complex test setup or live API calls for validation
- *Reality*: Basic argument validation and empty result handling provided sufficient confidence in the implementation
- *Learning*: The existing error handling and logging infrastructure meant that runtime issues would be clearly visible to users

**Documentation Structure Insight**
- *Expectation*: Would need extensive documentation updates
- *Reality*: The existing CLAUDE.md structure already covered the architecture well enough that minimal updates were needed
- *Learning*: Well-structured initial documentation pays dividends during feature additions

**CLI Argument Design Challenge**
- *Expectation*: Complex validation logic would be needed for CLI arguments
- *Reality*: Python's argparse combined with the existing date validation in the core function provided clean separation of concerns
- *Learning*: Validation at the service layer rather than CLI layer keeps the CLI simple and reusable

## Implementation Learnings: Processor Architecture Refactoring

### Key Insights from Static Method Transformation

**Architectural Decision: Functional vs Object-Oriented**
- *Problem*: Original design used instance variables (`self.raw_csv_data`, `self.doc_id`, etc.) but processors don't logically need to maintain state
- *Solution*: Converted all methods to static methods with explicit parameter passing
- *Learning*: Document processors are inherently functional operations - they transform input data to output structure without needing persistent state

**Method Signature Evolution**
- *Before*: `self.get_value_by_id(element_id, context_filter=None)`
- *After*: `BaseProcessor.get_value_by_id(all_records, element_id, context_filter=None)`
- *Benefit*: Clear data flow, better testability, no hidden dependencies on instance state

**Processing Flow Simplification**
- *Previous Flow*: Instantiate processor → Load data into instance → Call process()
- *Current Flow*: Combine raw CSV data → Call static process(all_records, doc_id, doc_type_code)
- *Result*: More predictable, easier to reason about, and follows functional programming principles

## Implementation Learnings: Architecture Simplification Refactor

### Key Insights from Consolidation

**Module Organization Benefits**
- *Problem*: Multiple processor files with similar patterns created maintenance overhead
- *Solution*: Consolidated all processing logic into `BaseProcessor` with conditional logic
- *Learning*: For this domain, generic processing with document-type-specific branches is more maintainable than separate classes

**Import Structure Clarification**
- *Problem*: `utils.py` was ambiguous - contained both file utilities and API decorators
- *Solution*: Split into `src/utils.py` (file processing) and `src/edinet/decorators.py` (API-specific)
- *Learning*: Clear module boundaries make the codebase more navigable and logical

**CLI Simplification Impact**
- *Previous*: Complex date range and output file handling
- *Current*: Simple company filtering with lookback days
- *Result*: More intuitive user experience focused on common use cases

**Functional Programming Benefits**
- *Achievement*: All processing methods are now pure functions with explicit parameters
- *Benefit*: Easier testing, debugging, and reasoning about data flow
- *Learning*: Financial document processing is inherently functional - no need for stateful objects
