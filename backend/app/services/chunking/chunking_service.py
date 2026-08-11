import uuid
import tiktoken

from app.services.chunking.chunk_model import Chunk


chunk_size = 1000
chunk_overlap = 150


def get_tokenizer():
    return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    tokenizer = get_tokenizer()
    return len(tokenizer.encode(text))


def chunk_text(
    text: str,
    document_id: str,
    chunk_size: int = chunk_size,
    chunk_overlap: int = chunk_overlap,
) -> list[Chunk]:

    if not text.strip():
        return []

    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    tokenizer = get_tokenizer()
    tokens = tokenizer.encode(text)

    chunks = []

    start = 0
    chunk_index = 0

    while start < len(tokens):

        end = min(start + chunk_size, len(tokens))

        chunk_tokens = tokens[start:end]
        chunk_text_value = tokenizer.decode(chunk_tokens).strip()

        if chunk_text_value:
            chunks.append(
                Chunk(
                    chunk_id=str(uuid.uuid4()),
                    document_id=document_id,
                    chunk_index=chunk_index,
                    text=chunk_text_value,
                    token_count=len(chunk_tokens),
                )
            )

            chunk_index += 1

        if end >= len(tokens):
            break

        start = end - chunk_overlap

    return chunks