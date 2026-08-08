from pathlib import Path
import csv

from app.parsers.base_parser import BaseParser


class CSVParser(BaseParser):
    """
    Parser for CSV documents.
    """

    def parse(self, file_path: Path) -> str:
        rows = []

        with file_path.open(
            "r",
            encoding="utf-8",
            errors="replace",
            newline="",
        ) as file:
            reader = csv.reader(file)

            for row in reader:
                rows.append(" | ".join(row))

        return "\n".join(rows)