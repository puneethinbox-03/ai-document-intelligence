from pathlib import Path

from app.parsers.base_parser import BaseParser
from app.parsers.csv_parser import CSVParser
from app.parsers.docx_parser import DOCXParser
from app.parsers.md_parser import MDParser
from app.parsers.pdf_parser import PDFParser
from app.parsers.pptx_parser import PPTXParser
from app.parsers.txt_parser import TXTParser
from app.parsers.ocr_parser import OCRParser

class ParserFactory:
    """
    Factory responsible for selecting the correct
    parser based on the document extension.
    """

    
    _parsers = {
    ".txt": TXTParser,
    ".md": TXTParser,
    ".pdf": PDFParser,
    ".docx": DOCXParser,
    ".csv": CSVParser,
    ".pptx": PPTXParser,
    ".png": OCRParser,
    ".jpg": OCRParser,
    ".jpeg": OCRParser,
    }

    @classmethod
    def get_parser(cls, file_path: Path) -> BaseParser:
        extension = file_path.suffix.lower()

        parser_class = cls._parsers.get(extension)

        if parser_class is None:
            raise ValueError(
                f"No parser available for file type: {extension}"
            )

        return parser_class()