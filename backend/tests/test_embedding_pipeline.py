from pathlib import Path

from app.parsers.pdf_parser import PDFParser
from app.services.text_processing.cleaning_service import clean_text
from app.services.text_processing.normalization_service import normalize_text
from app.services.chunking.chunking_service import chunk_text
from app.services.embeddings.embedding_service import embed_texts


def test_pdf_chunk_embedding_pipeline():
    file_path = Path(
        r"C:\Users\punee\Projects\ai-document-intelligence\sample_documents\pdflatex-4-pages.pdf"
    )

    text = PDFParser().parse(file_path)

    text = clean_text(text)
    text = normalize_text(text)

    chunks = chunk_text(
        text,
        "pdflatex-4-pages"
    )

    embeddings = embed_texts(
        [chunk.text for chunk in chunks]
    )

    assert len(chunks) > 0
    assert len(embeddings) == len(chunks)
    assert all(len(embedding) == 1024 for embedding in embeddings)