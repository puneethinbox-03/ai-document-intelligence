from pathlib import Path

from pypdf import PdfReader

from app.parsers.base_parser import BaseParser


class PDFParser(BaseParser):
    """
    Parser for PDF documents.
    """

    def parse(self, file_path: Path) -> str:
        reader = PdfReader(str(file_path))

        pages = []

        for page in reader.pages:
            text = page.extract_text()

            if text:
                pages.append(text)

        return "\n\n".join(pages)