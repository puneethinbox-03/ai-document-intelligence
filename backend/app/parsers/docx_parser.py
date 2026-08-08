from pathlib import Path

from docx import Document

from app.parsers.base_parser import BaseParser


class DOCXParser(BaseParser):
    """
    Parser for Microsoft Word DOCX documents.
    """

    def parse(self, file_path: Path) -> str:
        document = Document(str(file_path))

        paragraphs = []

        for paragraph in document.paragraphs:
            text = paragraph.text.strip()

            if text:
                paragraphs.append(text)

        return "\n\n".join(paragraphs)