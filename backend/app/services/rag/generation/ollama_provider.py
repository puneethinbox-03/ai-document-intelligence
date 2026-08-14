import os

import ollama


OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen3:8b-q4_K_M",
)


def generate_with_ollama(
    prompt: str,
) -> str:
    """
    Generate an answer using the local Ollama model.
    """

    if not prompt or not prompt.strip():
        raise ValueError("Prompt cannot be empty")

    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
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