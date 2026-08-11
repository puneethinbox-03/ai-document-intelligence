import re
import unicodedata


def normalize_unicode(text: str) -> str:
    """
    Normalize Unicode characters into a consistent representation.
    """
    return unicodedata.normalize("NFKC", text)


def normalize_line_endings(text: str) -> str:
    """
    Normalize Windows/Mac line endings to Unix-style line endings.
    """
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")
    return text


def normalize_whitespace(text: str) -> str:
    """
    Normalize unnecessary spaces and tabs while preserving newlines.
    """
    lines = text.split("\n")

    cleaned_lines = []

    for line in lines:
        line = re.sub(r"[ \t]+", " ", line)
        line = line.strip()
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def remove_excessive_newlines(text: str) -> str:
    """
    Replace excessive blank lines with a maximum of one blank line.
    """
    return re.sub(r"\n{3,}", "\n\n", text)


def clean_text(text: str) -> str:
    """
    Main text-cleaning pipeline.
    """

    if text is None:
        return ""

    if not isinstance(text, str):
        text = str(text)

    if not text.strip():
        return ""

    # 1. Unicode normalization
    text = normalize_unicode(text)

    # 2. Normalize line endings
    text = normalize_line_endings(text)

    # 3. Normalize whitespace
    text = normalize_whitespace(text)

    # 4. Remove excessive blank lines
    text = remove_excessive_newlines(text)

    # 5. Remove leading/trailing whitespace
    text = text.strip()

    return text