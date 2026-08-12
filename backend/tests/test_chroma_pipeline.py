from pathlib import Path

from app.parsers.pdf_parser import PDFParser
from app.services.text_processing.cleaning_service import clean_text
from app.services.text_processing.normalization_service import normalize_text
from app.services.chunking.chunking_service import chunk_text
from app.services.embeddings.embedding_service import embed_texts
from app.services.vectorstore.chroma_service import add_chunks, get_chunks


def test_pdf_to_chroma_pipeline():

    file_path = Path(
        r"C:\Users\punee\Projects\ai-document-intelligence\sample_documents\pdflatex-4-pages.pdf"
    )

    # Parse PDF
    text = PDFParser().parse(file_path)

    # Clean text
    text = clean_text(text)

    # Normalize text
    text = normalize_text(text)

    # Create chunks
    chunks = chunk_text(text, file_path.stem)

    # Create embeddings
    embeddings = embed_texts(
        [chunk.text for chunk in chunks]
    )

    # Create chunk IDs
    chunk_ids = [
        f"pipeline-{file_path.stem}-{i}"
        for i in range(len(chunks))
    ]

    # Create metadata
    metadatas = [
        {
            "document_id": file_path.stem,
            "filename": file_path.name,
            "chunk_index": i,
        }
        for i in range(len(chunks))
    ]

    # Store in ChromaDB
    add_chunks(
        chunk_ids=chunk_ids,
        texts=[chunk.text for chunk in chunks],
        embeddings=embeddings,
        metadatas=metadatas,
    )

    # Retrieve from ChromaDB
    result = get_chunks(chunk_ids)

    # Verify
    assert len(result["ids"]) == len(chunks)
    assert len(result["documents"]) == len(chunks)
    assert len(embeddings[0]) == 1024