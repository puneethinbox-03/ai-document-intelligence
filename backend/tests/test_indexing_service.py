from pathlib import Path
from uuid import uuid4

import pytest

from app.services.indexing_service import (
    IndexingResult,
    index_document,
)
from app.services.vectorstore.chroma_service import (
    delete_chunks,
    get_chunks,
)


def create_test_file(
    tmp_path: Path,
    content: str,
) -> Path:
    file_path = tmp_path / "test.txt"

    file_path.write_text(
        content,
        encoding="utf-8",
    )

    return file_path


def cleanup_document(
    document_id: str,
) -> None:
    stored_chunks = get_chunks()

    ids = stored_chunks.get("ids", [])
    metadatas = stored_chunks.get("metadatas", [])

    chunk_ids = [
        chunk_id
        for chunk_id, metadata in zip(
            ids,
            metadatas,
        )
        if metadata.get("document_id") == document_id
    ]

    if chunk_ids:
        delete_chunks(chunk_ids)


def test_index_document(
    tmp_path: Path,
):
    document_id = f"index-test-{uuid4()}"

    file_path = create_test_file(
        tmp_path,
        (
            "Python is a programming language. "
            "Python is widely used for software development. "
            "Python has many libraries."
        ),
    )

    try:
        result = index_document(
            file_path=file_path,
            document_id=document_id,
            filename="test.txt",
        )

        assert isinstance(
            result,
            IndexingResult,
        )

        assert result.document_id == document_id
        assert result.chunk_count >= 1
        assert result.token_count > 0

    finally:
        cleanup_document(document_id)


def test_index_document_stores_chunks(
    tmp_path: Path,
):
    document_id = f"index-test-{uuid4()}"

    file_path = create_test_file(
        tmp_path,
        (
            "Python programming is useful. "
            "Python supports many libraries."
        ),
    )

    try:
        result = index_document(
            file_path=file_path,
            document_id=document_id,
            filename="test.txt",
        )

        stored = get_chunks()

        ids = stored.get("ids", [])
        metadatas = stored.get("metadatas", [])

        matching = [
            (chunk_id, metadata)
            for chunk_id, metadata in zip(
                ids,
                metadatas,
            )
            if metadata.get("document_id") == document_id
        ]

        assert len(matching) == result.chunk_count

        for chunk_id, metadata in matching:
            assert chunk_id.startswith(
                f"{document_id}-"
            )

            assert metadata["document_id"] == document_id
            assert metadata["filename"] == "test.txt"
            assert "chunk_index" in metadata
            assert "token_count" in metadata

    finally:
        cleanup_document(document_id)


def test_index_document_reindex_replaces_old_chunks(
    tmp_path: Path,
):
    document_id = f"index-test-{uuid4()}"

    file_path = create_test_file(
        tmp_path,
        (
            "Python is a programming language. "
            "Python is useful."
        ),
    )

    try:
        first_result = index_document(
            file_path=file_path,
            document_id=document_id,
            filename="test.txt",
        )

        second_result = index_document(
            file_path=file_path,
            document_id=document_id,
            filename="test.txt",
        )

        stored = get_chunks()

        ids = stored.get("ids", [])
        metadatas = stored.get("metadatas", [])

        matching_ids = [
            chunk_id
            for chunk_id, metadata in zip(
                ids,
                metadatas,
            )
            if metadata.get("document_id") == document_id
        ]

        assert second_result.chunk_count == (
            first_result.chunk_count
        )

        assert len(matching_ids) == (
            second_result.chunk_count
        )

        assert len(
            set(matching_ids)
        ) == len(matching_ids)

    finally:
        cleanup_document(document_id)


def test_index_document_empty_file(
    tmp_path: Path,
):
    document_id = f"index-test-{uuid4()}"

    file_path = create_test_file(
        tmp_path,
        "",
    )

    try:
        result = index_document(
            file_path=file_path,
            document_id=document_id,
        )

        assert result.document_id == document_id
        assert result.chunk_count == 0
        assert result.token_count == 0

    finally:
        cleanup_document(document_id)


def test_index_document_missing_file(
    tmp_path: Path,
):
    document_id = f"index-test-{uuid4()}"

    file_path = (
        tmp_path / "does-not-exist.txt"
    )

    with pytest.raises(FileNotFoundError):
        index_document(
            file_path=file_path,
            document_id=document_id,
        )


def test_index_document_invalid_document_id(
    tmp_path: Path,
):
    file_path = create_test_file(
        tmp_path,
        "Python is a programming language.",
    )

    with pytest.raises(ValueError):
        index_document(
            file_path=file_path,
            document_id="",
        )