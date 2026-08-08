from pathlib import Path

from app.parsers.base_parser import BaseParser
from app.parsers.ocr.ocr_service import extract_text_from_image


class OCRParser(BaseParser):
    """
    Parser for image documents using OCR.
    """

    def parse(self, file_path: Path) -> str:
        return extract_text_from_image(file_path)