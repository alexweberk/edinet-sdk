# Feature: Dedicated XBRL and CSV Download Functions

**Description**

While the `fetch_document` function can be extended to download different document types, XBRL and CSV files are fundamental for financial analysis and deserve dedicated, high-level functions for ease of use. This feature will introduce `fetch_xbrl` and `fetch_csv` functions.

**Acceptance Criteria**

- A new function `fetch_xbrl(doc_id)` should be created that calls `fetch_document` with `doc_type=1`.
- A new function `fetch_csv(doc_id)` should be created that calls `fetch_document` with `doc_type=5`.
- Both functions should return the raw `bytes` of the document.
- The functions should be added to `src/edinet/edinet_tools.py`.

**Technical Details**

- Implement `fetch_xbrl` and `fetch_csv` in `src/edinet/edinet_tools.py`.
- These functions will be thin wrappers around the `fetch_document` function, setting the appropriate `doc_type`.
