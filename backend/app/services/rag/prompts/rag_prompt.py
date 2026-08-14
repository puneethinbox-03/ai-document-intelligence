from app.services.rag.retrieval.models import RetrievedChunk


SYSTEM_PROMPT = """You are an AI document assistant.

Answer the user's question using only the provided document context.

Rules:
1. Use only information present in the provided context.
2. Do not invent or assume facts that are not present.
3. If the context does not contain enough information, clearly say that the answer cannot be determined from the provided documents.
4. Give a concise and accurate answer.
5. When possible, mention the source document or relevant chunk information.
"""


def build_rag_prompt(
    query: str,
    chunks: list[RetrievedChunk],
) -> str:
    """
    Build a prompt for RAG-based LLM generation.
    """

    if not query or not query.strip():
        raise ValueError("Query cannot be empty")

    if not chunks:
        context = "No relevant document context was retrieved."
    else:
        context_parts: list[str] = []

        for index, chunk in enumerate(chunks, start=1):
            document_id = chunk.metadata.get(
                "document_id",
                "unknown",
            )

            chunk_index = chunk.metadata.get(
                "chunk_index",
                "unknown",
            )

            context_parts.append(
                f"""[Context {index}]
Document ID: {document_id}
Chunk Index: {chunk_index}
Chunk ID: {chunk.chunk_id}

{chunk.text}
"""
            )

        context = "\n".join(context_parts)

    return f"""{SYSTEM_PROMPT}

DOCUMENT CONTEXT:
{context}

USER QUESTION:
{query.strip()}

ANSWER:
"""