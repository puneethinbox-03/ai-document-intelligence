import re


def normalize_text(text: str) -> str:
    """
    Normalize extracted document text.

    Operations:
    - Normalize line endings
    - Remove excessive spaces
    - Remove excessive blank lines
    - Normalize tabs
    - Strip leading/trailing whitespace
    """

    if not text:
        return ""

    # Normalize line endings
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Replace tabs with spaces
    text = text.replace("\t", " ")

    # Remove trailing spaces from each line
    text = "\n".join(
        line.rstrip()
        for line in text.split("\n")
    )

    # Collapse multiple spaces
    text = re.sub(r"[ ]{2,}", " ", text)

    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Remove leading/trailing whitespace
    text = text.strip()

    return text