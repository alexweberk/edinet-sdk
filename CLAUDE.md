# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

This is a Python project using UV for package management with pyproject.toml configuration.

**Running main.py:**
```bash
uv run python main.py                    # Run demo mode
uv run python main.py --help            # Show available CLI options
```

**Company date range query mode:**
```bash
uv run python main.py --edinet-code E12345 --start-date 2024-01-01 --end-date 2024-01-31
uv run python main.py --edinet-code E12345 --start-date 2024-01-01 --end-date 2024-01-31 --doc-types "160,180" --output results.json
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
1. **EDINET API Interaction** (`src/edinet/client.py`) → Fetch document lists and download ZIP files
2. **Data Processing** (`src/utils.py`) → Extract and clean CSV data from ZIP archives
3. **Document Processing** (`src/processors/`) → Transform raw CSV into structured data
4. **Service Layer** (`src/services.py`) → Orchestrate the complete workflow

### Key Modules

- **`src/edinet/client.py`**: EDINET API client with retry logic and error handling
- **`src/processors/`**: Document-type-specific processors that transform raw CSV data:
  - `base_processor.py`: Abstract base class defining the processor interface
  - `semiannual_processor.py`: Handles Semi-Annual Reports (160)
  - `extraordinary_processor.py`: Handles Extraordinary Reports (180)
  - `generic_processor.py`: Fallback processor for unsupported document types
- **`src/services.py`**: High-level service functions orchestrating the complete workflow
- **`src/utils.py`**: File processing utilities (encoding detection, CSV parsing, text cleaning)
- **`src/config.py`**: Configuration including API URLs, constants, and document types
- **`src/exceptions.py`**: Custom exception classes for error handling
- **`src/error_handlers.py`**: Error handling decorators and context managers
- **`src/logging_config.py`**: Centralized logging configuration

### Document Processing System

The system uses a processor mapping pattern with static methods in `BaseProcessor.process_structured_data_from_raw_csv()`:
- Document type codes (160, 180, etc.) map to specific processor classes
- Each processor uses static methods with explicit data parameters (no instance variables)
- Falls back to `GenericReportProcessor` for unsupported document types
- All processors inherit from `BaseProcessor` and implement static `process(all_records, doc_id, doc_type_code)` method
- Processors are purely functional - they don't maintain any internal state

### SDK Architecture

The SDK provides a clean, class-based interface:
- `EdinetClient` class handles all API interactions with comprehensive error handling
- Built-in retry logic and proper logging throughout
- Document processors transform raw CSV data into structured formats
- Backward compatibility functions maintain existing API surface

## Configuration Requirements

The project uses Pydantic-based configuration validation with comprehensive error checking.

**Required Environment Variables:**
- `EDINET_API_KEY`: Japan EDINET API access key (required)

**Optional Processing Configuration:**
- `MAX_RETRIES`: Maximum retry attempts (default: 3)
- `DELAY_SECONDS`: Delay between retries in seconds (default: 5)
- `DAYS_BACK`: Days to search back for recent documents (default: 7)

## Entry Points and CLI Usage

The application has two main modes:

**1. Demo Mode (default):**
- Fetches recent documents of specified types
- Downloads and processes them
- Usage: `uv run python main.py`

**2. Company Date Range Query Mode:**
- Fetches documents for a specific company within a date range
- Supports document type filtering
- Outputs structured JSON data
- Usage: `uv run python main.py --edinet-code <CODE> --start-date <DATE> --end-date <DATE>`

## Supported Document Types

Defined in `src/config.py:SUPPORTED_DOC_TYPES`:
- 160: Semi-Annual Report
- 140: Quarterly Report
- 180: Extraordinary Report
- 350: Large Holding Report
- 030: Securities Registration Statement
- 120: Securities Report

## Using the SDK

The SDK provides both class-based and function-based interfaces:

```python
from src.edinet.client import EdinetClient
import datetime

# Class-based usage (recommended)
client = EdinetClient()
docs = client.get_documents_for_date_range(
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 1, 31),
    edinet_codes=['E12345']
)
client.download_documents(docs)

# Function-based usage (for backward compatibility)
from src.edinet.client import get_documents_for_date_range, download_documents
docs = get_documents_for_date_range(
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 1, 31)
)
download_documents(docs)
```

## Adding New Document Processors

1. Create class inheriting from `BaseProcessor` in `src/processors/`
2. Implement static `process(all_records, doc_id, doc_type_code)` method with document-specific data extraction logic
3. Use static helper methods from `BaseProcessor`: `get_value_by_id()`, `get_all_text_blocks()`, `_get_common_metadata()`
4. Add to `processor_map` in `BaseProcessor.process_structured_data_from_raw_csv()`
5. Import the new processor class in the `process_structured_data_from_raw_csv()` method

## Project Structure

```
edinet-sdk/
├── src/                           # Main source code
│   ├── __init__.py                # Package initialization
│   ├── config.py                  # Configuration and constants
│   ├── exceptions.py              # Custom exception classes
│   ├── error_handlers.py          # Error handling decorators
│   ├── logging_config.py          # Centralized logging setup
│   ├── services.py                # High-level service orchestration
│   ├── utils.py                   # File processing utilities
│   ├── edinet/                    # EDINET API integration
│   │   ├── __init__.py            # Package initialization
│   │   └── client.py              # EDINET API client with retry logic
│   └── processors/                # Document-specific processors
│       ├── __init__.py            # Package initialization
│       ├── base_processor.py      # Abstract base class
│       ├── generic_processor.py   # Fallback processor
│       ├── semiannual_processor.py # Semi-Annual Reports (160)
│       └── extraordinary_processor.py # Extraordinary Reports (180)
├── main.py                        # CLI entry point
├── main.ipynb                     # Jupyter notebook for exploration
├── pyproject.toml                 # UV package configuration
├── downloads/                     # Downloaded ZIP files storage
└── docs/                          # Additional documentation
```

## Error Handling and Logging

The project implements comprehensive error handling:

- **Custom Exceptions**: Specific exception types in `src/exceptions.py` for different error categories
- **Error Decorators**: `@log_exceptions` decorator in `src/error_handlers.py` for consistent error logging
- **Context Managers**: `ErrorContext` for scoped error handling
- **Centralized Logging**: Consistent logging configuration across all modules
- **Graceful Degradation**: Failed document processing doesn't stop the entire pipeline

## Data Flow Details

**1. Document Discovery:**
- `EdinetClient.get_documents_for_date_range()` queries EDINET API for document metadata
- Returns list of document metadata dictionaries with docID, docTypeCode, filerName, etc.

**2. Document Download:**
- `EdinetClient.download_documents()` downloads ZIP files to specified directory
- Uses filename format: `{docID}-{docTypeCode}-{filerName}.zip`

**3. Document Processing:**
- `services.get_structured_data_from_zip_directory()` processes all ZIP files in directory
- Extracts CSV files, skips auditor reports (jpaud* files)
- Dispatches to appropriate processor based on document type code

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
