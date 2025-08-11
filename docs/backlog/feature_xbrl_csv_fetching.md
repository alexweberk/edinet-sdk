# Feature: Dedicated XBRL and CSV Fetching

**Description**

The primary purpose of this tool is to analyze financial data, and XBRL and CSV are the key formats for this. To simplify the process of fetching this data, we should create dedicated functions that wrap the generic `fetch_document` primitive.

**Acceptance Criteria**

- Create a new function `fetch_xbrl(doc_id: str) -> bytes`.
  - This function should call `fetch_document` with `doc_type=1`.
  - It should return the raw bytes of the ZIP file containing the XBRL data.
- Create a new function `fetch_csv(doc_id: str) -> bytes`.
  - This function should call `fetch_document` with `doc_type=5`.
  - It should return the raw bytes of the ZIP file containing the CSV data.
- Both functions should include appropriate docstrings explaining what they do.

**Technical Details**

- Implement the new `fetch_xbrl` and `fetch_csv` functions in `src/edinet/edinet_tools.py`.
- These functions will internally call the modified `fetch_document` function.
