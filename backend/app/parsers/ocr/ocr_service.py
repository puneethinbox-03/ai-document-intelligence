from pathlib import Path

import pytesseract
from PIL import Image, ImageOps, ImageFilter
from pdf2image import convert_from_path


TESSERACT_PATH = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

POPPLER_PATH = (
    r"C:\poppler\poppler-26.02.0"
    r"\poppler-26.02.0\Library\bin"
)


pytesseract.pytesseract.tesseract_cmd = (
    TESSERACT_PATH
)


def get_ocr_version() -> str:
    """
    Return installed Tesseract OCR version.
    """

    return str(
        pytesseract.get_tesseract_version()
    )


def _preprocess_image(
    image: Image.Image,
) -> Image.Image:
    """
    Preprocess image for better OCR accuracy.

    Steps:
    1. Convert to grayscale.
    2. Upscale small images.
    3. Improve contrast.
    4. Apply light sharpening.
    5. Apply thresholding.
    """

    image = image.convert("L")

    width, height = image.size

    # Small images benefit significantly from upscaling.
    if width < 1200 or height < 1200:
        scale = 3

        image = image.resize(
            (
                width * scale,
                height * scale,
            ),
            Image.Resampling.LANCZOS,
        )

    # Improve contrast.
    image = ImageOps.autocontrast(image)

    # Light sharpening.
    image = image.filter(
        ImageFilter.SHARPEN
    )

    # Convert to black/white.
    image = image.point(
        lambda pixel: 255 if pixel > 160 else 0
    )

    return image


def _run_tesseract(
    image: Image.Image,
) -> str:
    """
    Run Tesseract using a layout mode suitable
    for normal document/screenshot text.
    """

    
    config = "--oem 3 --psm 6"

    text = pytesseract.image_to_string(
        image,
        config=config,
    )

    return text.strip()


def extract_text_from_image(
    file_path: Path,
) -> str:
    """
    Extract text from an image using Tesseract OCR
    with preprocessing.
    """

    image = Image.open(file_path)

    processed_image = _preprocess_image(
        image
    )

    return _run_tesseract(
        processed_image
    )


def extract_text_from_scanned_pdf(
    file_path: Path,
) -> str:
    """
    Convert scanned PDF pages to images and
    extract text using Tesseract OCR.
    """

    pages = convert_from_path(
        str(file_path),
        dpi=300,
        poppler_path=POPPLER_PATH,
    )

    extracted_pages: list[str] = []

    for page in pages:
        processed_page = _preprocess_image(
            page
        )

        text = _run_tesseract(
            processed_page
        )

        if text:
            extracted_pages.append(text)

    return "\n\n".join(
        extracted_pages
    )