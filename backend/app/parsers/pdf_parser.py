from pathlib import Path

from pypdf import PdfReader

from app.parsers.base_parser import BaseParser
from app.parsers.ocr.ocr_service import (
    extract_text_from_scanned_pdf,
)


MIN_TEXT_LENGTH_FOR_NATIVE_EXTRACTION = 50


class PDFParser(BaseParser):
    """
    Parser for PDF documents.

    Uses native PDF text extraction first.
    Falls back to OCR when native extraction
    returns no meaningful text.
    """

    def parse(
        self,
        file_path: Path,
    ) -> str:
        reader = PdfReader(
            str(file_path)
        )

        pages: list[str] = []

        for page in reader.pages:
            text = page.extract_text()

            if text and text.strip():
                pages.append(
                    text.strip()
                )

        extracted_text = "\n\n".join(
            text
            for text in pages
            if text
        ).strip()

        # Use OCR when native extraction produces
        # no meaningful amount of text.
        if len(extracted_text) < (
            MIN_TEXT_LENGTH_FOR_NATIVE_EXTRACTION
        ):
            ocr_text = extract_text_from_scanned_pdf(
                file_path
            ).strip()

            if ocr_text:
                return ocr_text

        return extracted_text