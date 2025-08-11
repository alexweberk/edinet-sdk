# Feature: Document Type Filtering in `fetch_document`

**Description**

The `fetch_document` function currently hardcodes the `type` parameter to `1`, which only fetches the CSV version of a document. The EDINET API allows fetching other document types. This feature will extend `fetch_document` to support fetching different document types as specified by the API.

**Acceptance Criteria**

- The `fetch_document` function should accept a `doc_type` parameter.
- The `doc_type` parameter should support the following values:
  - `1`: Main document and audit report (XBRL for financial statements)
  - `2`: PDF
  - `3`: Alternative documents (e.g., attachments)
  - `4`: English documents (if available)
  - `5`: CSV data (for XBRL)
- The function should default to `1` if no `doc_type` is provided.
- The function should raise a `ValidationError` if an unsupported `doc_type` is provided.

**Technical Details**

- Modify the `fetch_document` function in `src/edinet/edinet_tools.py` to accept a `doc_type` argument.
- Update the `params` dictionary to use the provided `doc_type`.
- Add validation for the `doc_type` parameter.
