from pathlib import Path

import pytesseract
from pdf2image import convert_from_path

TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
POPPLER_PATH = (
    r"C:\poppler\poppler-26.02.0"
    r"\poppler-26.02.0\Library\bin"
)

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
def get_ocr_version() -> str:
    """
    Return installed Tesseract OCR version.
    """
    return str(pytesseract.get_tesseract_version())


def extract_text_from_image(file_path: Path) -> str:
    """
    Extract text from an image using Tesseract OCR.
    """
    return pytesseract.image_to_string(
        str(file_path)
    ).strip()


def extract_text_from_scanned_pdf(
    file_path: Path,
) -> str:
    """
    Convert scanned PDF pages to images
    and extract text using Tesseract OCR.
    """

    pages = convert_from_path(
        str(file_path),
        poppler_path=POPPLER_PATH,
    )

    extracted_pages = []

    for page in pages:
        text = pytesseract.image_to_string(
            page
        ).strip()

        if text:
            extracted_pages.append(text)

    return "\n\n".join(extracted_pages)