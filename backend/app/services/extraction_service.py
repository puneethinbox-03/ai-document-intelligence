from pathlib import Path

from app.parsers.parser_factory import ParserFactory
from app.services.text_processing.text_processor import process_text


def extract_document_text(file_path: Path) -> str:
    """
    Extract and process text from a supported document.
    """

    parser = ParserFactory.get_parser(file_path)

    raw_text = parser.parse(file_path)

    processed_text = process_text(raw_text)

    return processed_text