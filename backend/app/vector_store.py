"""ChromaDB vector store with optional Ollama embeddings."""

import logging
import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from pathlib import Path

logger = logging.getLogger("tousmeslikes")

CHROMA_PATH = Path(__file__).parent.parent / "data" / "chroma"

_use_ollama = False
_ollama_ef = None


class OllamaEmbeddingFunction:
    """ChromaDB-compatible embedding function using Ollama."""

    def __init__(self, model: str = "nomic-embed-text"):
        self.model = model

    def __call__(self, input: list[str]) -> list[list[float]]:
        from .ollama_client import get_embeddings
        return get_embeddings(input, model=self.model)


def init_vector_store(use_ollama: bool = False, embed_model: str = "nomic-embed-text"):
    """Initialize the vector store, optionally with Ollama embeddings."""
    global _use_ollama, _ollama_ef
    _use_ollama = use_ollama
    if use_ollama:
        _ollama_ef = OllamaEmbeddingFunction(model=embed_model)
        logger.info(f"[vector] Using Ollama embeddings ({embed_model})")
    else:
        _ollama_ef = None
        logger.info("[vector] Using default ChromaDB embeddings")


def get_collection():
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))

    kwargs = {
        "name": "items_ollama" if _use_ollama else "items",
        "metadata": {"hnsw:space": "cosine"},
    }
    if _ollama_ef:
        kwargs["embedding_function"] = _ollama_ef

    collection = client.get_or_create_collection(**kwargs)
    return collection


def add_items_to_vector_store(items: list[dict]):
    """Add items to ChromaDB."""
    collection = get_collection()
    if not items:
        return

    ids = [str(item["id"]) for item in items]
    documents = [
        f"{item.get('title', '')} {item.get('content', '')}".strip()
        for item in items
    ]
    metadatas = [
        {"platform": item.get("platform", ""), "type": item.get("type", "")}
        for item in items
    ]

    # Filter out empty documents
    filtered = [
        (id_, doc, meta)
        for id_, doc, meta in zip(ids, documents, metadatas)
        if doc
    ]
    if not filtered:
        return

    ids, documents, metadatas = zip(*filtered)

    # Batch in chunks of 50 (smaller batches for Ollama)
    batch_size = 50
    for i in range(0, len(ids), batch_size):
        collection.upsert(
            ids=list(ids[i:i + batch_size]),
            documents=list(documents[i:i + batch_size]),
            metadatas=list(metadatas[i:i + batch_size]),
        )


def semantic_search(query: str, n_results: int = 20, platform: str | None = None):
    """Search items by semantic similarity."""
    collection = get_collection()
    if collection.count() == 0:
        return []

    where = {"platform": platform} if platform else None
    results = collection.query(
        query_texts=[query],
        n_results=min(n_results, collection.count()),
        where=where,
    )

    return [
        {"id": int(id_), "distance": dist}
        for id_, dist in zip(results["ids"][0], results["distances"][0])
    ]
