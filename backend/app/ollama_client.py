"""Ollama integration — embeddings and chat with local LLM."""

import logging
import ollama as _ollama

logger = logging.getLogger("tousmeslikes")

EMBED_MODEL = "nomic-embed-text"
CHAT_MODEL = "mistral"


def is_ollama_available() -> bool:
    """Check if Ollama server is reachable."""
    try:
        _ollama.list()
        return True
    except Exception:
        return False


def list_models() -> list[str]:
    """List available Ollama models."""
    try:
        response = _ollama.list()
        return [m.model for m in response.models]
    except Exception:
        return []


def has_model(model_name: str) -> bool:
    """Check if a specific model is pulled."""
    models = list_models()
    return any(model_name in m for m in models)


def get_embeddings(texts: list[str], model: str = EMBED_MODEL) -> list[list[float]]:
    """Get embeddings for a batch of texts using Ollama."""
    # Truncate very long texts to avoid timeouts
    truncated = [t[:2000] for t in texts]
    response = _ollama.embed(model=model, input=truncated)
    return list(response.embeddings)


def chat(query: str, context: str, system_prompt: str | None = None, model: str = CHAT_MODEL) -> str:
    """Chat with RAG context."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    messages.append({
        "role": "user",
        "content": f"""Voici du contexte issu de mes likes, bookmarks et tweets :

---
{context}
---

Ma question : {query}"""
    })

    response = _ollama.chat(model=model, messages=messages)
    return response.message.content


RAG_SYSTEM_PROMPT = """Tu es un assistant personnel qui m'aide à retrouver et comprendre les contenus que j'ai likés, bookmarkés ou tweetés sur les réseaux sociaux.

Règles :
- Réponds en français sauf si la question est en anglais
- Base-toi uniquement sur le contexte fourni
- Si tu ne trouves pas la réponse dans le contexte, dis-le clairement
- Chaque contenu du contexte est numéroté [1], [2]… : cite le numéro entre crochets après chaque contenu que tu mentionnes
- Ne mentionne que des contenus présents dans le contexte, et n'invente jamais de lien, d'auteur ni de sujet
- Sois concis et direct"""
