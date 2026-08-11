from app.services.text_processing.cleaning_service import clean_text
from app.services.text_processing.normalization_service import normalize_text


def process_text(text: str) -> str:
    """
    Process extracted document text.

    Pipeline:
    1. Clean text
    2. Normalize text
    """

    if not text:
        return ""

    text = clean_text(text)
    text = normalize_text(text)

    return text
