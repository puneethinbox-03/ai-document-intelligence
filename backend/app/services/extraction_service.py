from pathlib import Path

from app.parsers.parser_factory import ParserFactory


def extract_document_text(file_path: Path) -> str:
    """
    Extract text from a supported document.
    """

    parser = ParserFactory.get_parser(file_path)

    text = parser.parse(file_path)

    return text