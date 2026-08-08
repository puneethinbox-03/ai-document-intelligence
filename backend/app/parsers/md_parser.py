from pathlib import Path

from app.parsers.base_parser import BaseParser


class MDParser(BaseParser):
    """
    Parser for Markdown documents.
    """

    def parse(self, file_path: Path) -> str:
        try:
            return file_path.read_text(encoding="utf-8")

        except UnicodeDecodeError:
            return file_path.read_text(
                encoding="utf-8",
                errors="replace",
            )