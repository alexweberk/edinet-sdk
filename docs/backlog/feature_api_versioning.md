# Feature: API Versioning

**Description**

The current EDINET API implementation does not specify the API version in the request URL. This can lead to unexpected behavior if the API is updated. To ensure stability and predictability, all API calls should explicitly use version 2 of the EDINET API.

**Acceptance Criteria**

- All EDINET API requests must include `/api/v2/` in the URL path.
- The base URL config in the application should be updated to reflect this change.
- Existing tests should pass, and new tests should be added to verify that the correct URL is being called.

**Technical Details**

- Update `EDINET_API_BASE_URL` in `src/config.py` to `https://api.edinet-fsa.go.jp/api/v2`.
- Update `EDINET_DOCUMENT_API_BASE_URL` in `src/config.py` to `https://api.edinet-fsa.go.jp/api/v2`.
