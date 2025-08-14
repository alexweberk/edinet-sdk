import logging

from src.config import LOG_FORMAT, TEXT_REPLACEMENTS


def setup_logging() -> None:
    """Configures basic logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[logging.StreamHandler()],
    )


def clean_text(text: str | None) -> str | None:
    """Clean and normalize text from disclosures."""
    if text is None:
        return None
    # replace full-width space with regular space
    text = text.replace(
        TEXT_REPLACEMENTS["FULL_WIDTH_SPACE"], TEXT_REPLACEMENTS["REGULAR_SPACE"]
    )
    # remove excessive whitespace
    # text = re.sub(r"\s+", " ", text).strip()

    # replace specific Japanese punctuation with Western equivalents for consistency
    # return text.replace('。', '. ').replace('、', ', ')
    return text


def snake_to_camel(s: str, remove_trailing_s: bool = True) -> str:
    """
    Convert a snake_case string to camelCase.
    If remove_trailing_s is True, remove the trailing "s" from the camelCase string.
    """
    parts = s.split("_")
    base = parts[0].lower() + "".join(word.capitalize() for word in parts[1:])
    if remove_trailing_s and base.endswith("s"):
        return base[:-1]
    return base
