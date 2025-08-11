# Feature: Download EDINET and Fund Code Lists

**Description**

The EDINET API provides lists of all EDINET codes and fund codes. These lists are essential for identifying companies and funds when making API requests. This feature will add functionality to download and cache these code lists.

**Acceptance Criteria**

- A new function `get_edinet_code_list()` should be created.
  - This function should download the EDINET code list from the URL specified in the API documentation.
  - The function should cache the downloaded list locally to avoid repeated downloads.
  - The function should return a list of EDINET codes.
- A new function `get_fund_code_list()` should be created.
  - This function should download the fund code list from the URL specified in the API documentation.
  - The function should cache the downloaded list locally.
  - The function should return a list of fund codes.

**Technical Details**

- The URLs for the code lists are:
  - EDINET Code List (JP): `https://disclosure2dl.edinet-fsa.go.jp/searchdocument/codelist/Edinetcode.zip`
  - Fund Code List (JP): `https://disclosure2dl.edinet-fsa.go.jp/searchdocument/codelist/Fundcode.zip`
- Implement the new functions in `src/edinet/edinet_tools.py`.
- Use a suitable caching mechanism, for example, storing the files in a `cache` directory and checking the file's modification time.