"""
Voyage AI embedding client.
Uses voyage-large-2 model for semantic similarity.
"""
import hashlib
import os
import re
import math

import voyageai

_client = None
_EMBEDDING_DIM = 1536


def get_voyage_client():
    global _client
    if _client is None:
        api_key = os.environ.get("VOYAGE_API_KEY")
        if not api_key:
            raise ValueError("VOYAGE_API_KEY environment variable is not set.")
        _client = voyageai.Client(api_key=api_key)
    return _client


def embed_text(text: str) -> list[float]:
    """Embed a single text string using Voyage AI."""
    try:
        client = get_voyage_client()
        result = client.embed([text], model="voyage-large-2", input_type="document")
        return result.embeddings[0]
    except Exception:
        return _local_embed(text)


def embed_query(text: str) -> list[float]:
    """Embed a query string (optimized for retrieval)."""
    try:
        client = get_voyage_client()
        result = client.embed([text], model="voyage-large-2", input_type="query")
        return result.embeddings[0]
    except Exception:
        return _local_embed(text)


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed multiple texts in a single API call."""
    try:
        client = get_voyage_client()
        result = client.embed(texts, model="voyage-large-2", input_type="document")
        return result.embeddings
    except Exception:
        return [_local_embed(text) for text in texts]


def _local_embed(text: str) -> list[float]:
    """
    Deterministic local fallback embedding.

    This keeps the knowledge base indexable when the Voyage API is rate-limited
    or unavailable. It is lower quality than Voyage embeddings, but it preserves
    the pgvector pipeline without requiring an external call.
    """
    tokens = re.findall(r"[A-Za-z0-9_]+", text.lower())
    vector = [0.0] * _EMBEDDING_DIM

    if not tokens:
        return vector

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % _EMBEDDING_DIM
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]
