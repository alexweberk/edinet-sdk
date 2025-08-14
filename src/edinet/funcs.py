from src.models import FilingMetadata
from src.utils import snake_to_camel


def filter_filings(
    all_filings: list[FilingMetadata],
    doc_ids: list[str] | None = None,
    edinet_codes: list[str] | None = None,
    sec_codes: list[str] | None = None,
    filer_names: list[str] | None = None,
    form_codes: list[str] | None = None,
    doc_type_codes: list[str] | None = None,  # the filing type codes
    doc_descriptions: list[str] | None = None,
) -> list[FilingMetadata]:
    """
    Filter filings based on the given criteria with AND combination between filters.
    Within each filter, OR logic is applied (any matching value passes).

    For example, if you want to filter by the filer name and the document type code,
    you can use the following:
    ```
    client.filter_filings(
        all_filings,
        filer_names=["野村マイクロ", "株式会社セルシード"],
        doc_type_codes=["140", "160"],
    )
    ```
    """
    if not all_filings:
        return []

    # Build filter predicates for non-None values
    filters = {
        "doc_ids": doc_ids,
        "edinet_codes": edinet_codes,
        "sec_codes": sec_codes,
        "filer_names": filer_names,
        "form_codes": form_codes,
        "doc_type_codes": doc_type_codes,
        "doc_descriptions": doc_descriptions,
    }

    def matches_all_filters(filing: FilingMetadata) -> bool:
        """Check if filing matches all provided filters (AND combination)."""
        return all(
            filter_values is None
            or any(
                value in getattr(filing, snake_to_camel(filter_name))
                for value in filter_values
            )
            for filter_name, filter_values in filters.items()
        )

    return [filing for filing in all_filings if matches_all_filters(filing)]
