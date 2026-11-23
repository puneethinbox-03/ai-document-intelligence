
from collections.abc import Iterator

import ollama

from app.core.config import settings


# Create one reusable Ollama client using centralized configuration.
ollama_client = ollama.Client(
    host=settings.ollama_url,
)


def generate_with_ollama(
    prompt: str,
) -> str:
    """
    Generate an answer using the configured Ollama model.
    """

    if not prompt or not prompt.strip():
        raise ValueError("Prompt cannot be empty")

    try:
        response = ollama_client.chat(
            model=settings.ollama_model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )
    except Exception as exc:
        raise RuntimeError(
            f"Ollama generation failed: {exc}"
        ) from exc

    try:
        answer = response["message"]["content"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(
            "Invalid response received from Ollama"
        ) from exc

    if not isinstance(answer, str):
        raise TypeError(
            "Ollama response content must be a string"
        )

    answer = answer.strip()

    if not answer:
        raise RuntimeError(
            "Ollama returned an empty answer"
        )

    return answer


def stream_with_ollama(
    prompt: str,
) -> Iterator[str]:
    """
    Stream answer chunks from the configured Ollama model.

    Each yielded string contains a portion of the generated answer.
    """

    if not prompt or not prompt.strip():
        raise ValueError("Prompt cannot be empty")

    try:
        response_stream = ollama_client.chat(
            model=settings.ollama_model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            stream=True,
        )

        has_content = False

        for chunk in response_stream:
            try:
                content = chunk["message"]["content"]
            except (KeyError, TypeError) as exc:
                raise RuntimeError(
                    "Invalid streaming response received from Ollama"
                ) from exc

            if not isinstance(content, str):
                raise TypeError(
                    "Ollama streaming content must be a string"
                )

            if content:
                has_content = True
                yield content

        if not has_content:
            raise RuntimeError(
                "Ollama returned an empty streaming response"
            )

    except (ValueError, TypeError):
        raise
    except Exception as exc:
        raise RuntimeError(
            f"Ollama streaming failed: {exc}"
        ) from exc
