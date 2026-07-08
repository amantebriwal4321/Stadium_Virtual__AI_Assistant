"""
retriever.py — RAG Knowledge Base for Setu.

Lightweight keyword-based retriever that works within Render's 512MB free tier.
Uses TF-IDF-style keyword matching against stadium policy documents.
Falls back to ChromaDB + SentenceTransformer when running locally with enough memory.

On a ``policy_question`` intent, searches the knowledge base and retrieves
the top-3 most relevant policy chunks.
"""

from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

# Paths
_DATA_DIR = Path(__file__).resolve().parent / "mock_data"
_POLICIES_FILE = _DATA_DIR / "stadium_policies.json"
_VECTOR_STORE_DIR = Path(__file__).resolve().parent / "vector_store"

# Lazy singletons
_policies: list[dict] | None = None
_documents: list[str] | None = None
_initialised = False

# Whether to use the lightweight mode (no ChromaDB/SentenceTransformer)
_USE_LIGHTWEIGHT = os.environ.get("LIGHTWEIGHT_RAG", "true").lower() == "true"


def _tokenize(text: str) -> list[str]:
    """Simple tokenizer: lowercase, strip punctuation, split on whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return [w for w in text.split() if len(w) > 1]


def _compute_idf(documents: list[str]) -> dict[str, float]:
    """Compute inverse document frequency for all terms across documents."""
    n = len(documents)
    doc_freq: Counter = Counter()
    for doc in documents:
        unique_terms = set(_tokenize(doc))
        for term in unique_terms:
            doc_freq[term] += 1
    return {term: math.log((n + 1) / (freq + 1)) + 1 for term, freq in doc_freq.items()}


def _tfidf_score(query: str, document: str, idf: dict[str, float]) -> float:
    """Compute a TF-IDF cosine similarity score between query and document."""
    query_terms = _tokenize(query)
    doc_terms = _tokenize(document)

    if not query_terms or not doc_terms:
        return 0.0

    doc_tf: Counter = Counter(doc_terms)
    query_tf: Counter = Counter(query_terms)

    # Compute vectors
    all_terms = set(query_terms) | set(doc_terms)
    dot_product = 0.0
    query_norm = 0.0
    doc_norm = 0.0

    for term in all_terms:
        q_weight = query_tf.get(term, 0) * idf.get(term, 1.0)
        d_weight = doc_tf.get(term, 0) * idf.get(term, 1.0)
        dot_product += q_weight * d_weight
        query_norm += q_weight ** 2
        doc_norm += d_weight ** 2

    if query_norm == 0 or doc_norm == 0:
        return 0.0

    return dot_product / (math.sqrt(query_norm) * math.sqrt(doc_norm))


# ─── Lightweight retriever (keyword-based) ──────────────────────────────

_idf: dict[str, float] | None = None


def _init_lightweight() -> None:
    """Load policy documents and precompute IDF values."""
    global _policies, _documents, _idf, _initialised

    if _initialised:
        return

    with open(_POLICIES_FILE, "r", encoding="utf-8") as fh:
        _policies = json.load(fh)

    _documents = [f"{p['topic']}: {p['content']}" for p in _policies]
    _idf = _compute_idf(_documents)
    _initialised = True


def _retrieve_lightweight(query: str, top_k: int = 3) -> list[str]:
    """Retrieve top-k most relevant policy chunks using keyword matching."""
    _init_lightweight()

    scores = []
    for i, doc in enumerate(_documents):
        score = _tfidf_score(query, doc, _idf)
        scores.append((score, i))

    # Sort by score descending
    scores.sort(key=lambda x: x[0], reverse=True)

    results = []
    for score, idx in scores[:top_k]:
        if score > 0.0:
            results.append(_documents[idx])

    return results


# ─── ChromaDB retriever (heavy, for local use) ─────────────────────────

def _init_chromadb() -> None:
    """Load ChromaDB + SentenceTransformer for high-quality retrieval."""
    global _initialised

    if _initialised:
        return

    try:
        import chromadb
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("all-MiniLM-L6-v2")

        client = chromadb.Client(chromadb.Settings(
            is_persistent=True,
            persist_directory=str(_VECTOR_STORE_DIR),
            anonymized_telemetry=False,
        ))
        collection = client.get_or_create_collection(
            name="stadium_policies",
            metadata={"hnsw:space": "cosine"},
        )

        if collection.count() == 0:
            with open(_POLICIES_FILE, "r", encoding="utf-8") as fh:
                policies = json.load(fh)

            ids = [p["id"] for p in policies]
            documents = [f"{p['topic']}: {p['content']}" for p in policies]
            metadatas = [{"topic": p["topic"]} for p in policies]
            embeddings = model.encode(documents, show_progress_bar=False).tolist()

            collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
            )

        # Store references for retrieve
        global _chromadb_model, _chromadb_collection
        _chromadb_model = model
        _chromadb_collection = collection
        _initialised = True

    except (ImportError, MemoryError, Exception) as e:
        print(f"[Setu] ChromaDB unavailable ({type(e).__name__}), falling back to lightweight RAG")
        global _USE_LIGHTWEIGHT
        _USE_LIGHTWEIGHT = True
        _init_lightweight()


_chromadb_model = None
_chromadb_collection = None


def _retrieve_chromadb(query: str, top_k: int = 3) -> list[str]:
    """Retrieve using ChromaDB vector similarity."""
    _init_chromadb()

    if _chromadb_model is None or _chromadb_collection is None:
        return _retrieve_lightweight(query, top_k)

    query_embedding = _chromadb_model.encode([query], show_progress_bar=False).tolist()
    results = _chromadb_collection.query(
        query_embeddings=query_embedding,
        n_results=min(top_k, _chromadb_collection.count()),
    )

    if results and results.get("documents"):
        return results["documents"][0]
    return []


# ─── Public API ─────────────────────────────────────────────────────────

def initialise() -> None:
    """
    Load policy documents and prepare the retrieval index.
    Safe to call multiple times — skips if already initialised.
    """
    if _USE_LIGHTWEIGHT:
        _init_lightweight()
    else:
        _init_chromadb()


def retrieve(query: str, top_k: int = 3) -> list[str]:
    """
    Search the knowledge base and return the top-k most relevant policy chunks
    as plain text strings.
    """
    if _USE_LIGHTWEIGHT:
        return _retrieve_lightweight(query, top_k)
    else:
        return _retrieve_chromadb(query, top_k)
