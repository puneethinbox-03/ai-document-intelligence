from pathlib import Path

from pypdf import PdfReader

from app.parsers.base_parser import BaseParser
from app.parsers.ocr.ocr_service import extract_text_from_scanned_pdf


class PDFParser(BaseParser):
    """
    Parser for PDF documents.

    Uses normal PDF text extraction first.
    Falls back to OCR for scanned PDFs.
    """

    def parse(self, file_path: Path) -> str:
        reader = PdfReader(str(file_path))

        pages = []

        for page in reader.pages:
            text = page.extract_text()

            if text:
                pages.append(text.strip())

        extracted_text = "\n\n".join(
            text for text in pages if text
        )

        # OCR fallback for scanned PDFs
        if not extracted_text.strip():
            return extract_text_from_scanned_pdf(
                file_path
            )

        return extracted_text