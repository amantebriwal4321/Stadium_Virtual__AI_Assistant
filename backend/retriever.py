"""
retriever.py — RAG Knowledge Base for Setu.

Embeds stadium policy documents locally with ``sentence-transformers``
(all-MiniLM-L6-v2) and stores them in a local ChromaDB collection.
On a ``policy_question`` intent, embeds the user query and retrieves
the top-3 most relevant policy chunks via cosine similarity.

Runs FULLY OFFLINE / LOCAL — zero external embedding API calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import chromadb
from sentence_transformers import SentenceTransformer

# Paths
_DATA_DIR = Path(__file__).resolve().parent / "mock_data"
_POLICIES_FILE = _DATA_DIR / "stadium_policies.json"
_VECTOR_STORE_DIR = Path(__file__).resolve().parent / "vector_store"

# Lazy singletons
_model: SentenceTransformer | None = None
_collection: chromadb.Collection | None = None
_initialised = False


def _get_model() -> SentenceTransformer:
    """Load the embedding model once (downloads ~90 MB on first run)."""
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _get_collection() -> chromadb.Collection:
    """Return the ChromaDB collection, creating it if necessary."""
    global _collection
    if _collection is None:
        client = chromadb.Client(chromadb.Settings(
            is_persistent=True,
            persist_directory=str(_VECTOR_STORE_DIR),
            anonymized_telemetry=False,
        ))
        _collection = client.get_or_create_collection(
            name="stadium_policies",
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def initialise() -> None:
    """
    Load policy documents, embed them, and upsert into ChromaDB.
    Safe to call multiple times — skips if already populated.
    """
    global _initialised
    if _initialised:
        return

    collection = _get_collection()

    # Skip if already populated
    if collection.count() > 0:
        _initialised = True
        return

    model = _get_model()

    with open(_POLICIES_FILE, "r", encoding="utf-8") as fh:
        policies: list[dict] = json.load(fh)

    ids = [p["id"] for p in policies]
    documents = [f"{p['topic']}: {p['content']}" for p in policies]
    metadatas = [{"topic": p["topic"]} for p in policies]

    # Embed all documents
    embeddings = model.encode(documents, show_progress_bar=False).tolist()

    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    _initialised = True


def retrieve(query: str, top_k: int = 3) -> list[str]:
    """
    Embed the user query and return the top-k most relevant policy chunks
    as plain text strings.
    """
    initialise()  # ensure index is ready
    model = _get_model()
    collection = _get_collection()

    query_embedding = model.encode([query], show_progress_bar=False).tolist()

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=min(top_k, collection.count()),
    )

    # results["documents"] is a list of lists — flatten
    if results and results.get("documents"):
        return results["documents"][0]
    return []
