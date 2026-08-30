"""Embedding providers used by the knowledge quality-gated RAG path."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import unicodedata
import urllib.request
from typing import Protocol


class EmbeddingProvider(Protocol):
    model_name: str

    def embed(self, text: str) -> list[float]: ...


class HashEmbeddingProvider:
    """Deterministic offline vectorizer for contracts, not a semantic model claim."""

    model_name = "local-hash-v1"

    def __init__(self, dimensions: int = 64) -> None:
        if dimensions < 8:
            raise ValueError("Embedding dimensions must be at least 8")
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        normalized = unicodedata.normalize("NFKC", text).lower().strip()
        if not normalized:
            raise ValueError("Cannot embed empty text")
        terms = re.findall(r"[a-z0-9_]+|[\u3400-\u9fff]", normalized)
        if not terms:
            terms = list(normalized)
        vector = [0.0] * self.dimensions
        for term in terms:
            digest = hashlib.blake2b(term.encode("utf-8"), digest_size=16).digest()
            index = int.from_bytes(digest[:8], "big") % self.dimensions
            sign = 1.0 if digest[8] & 1 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            raise ValueError("Embedding vector has zero norm")
        return [value / norm for value in vector]


class OpenAICompatibleEmbeddingProvider:
    """Minimal credential-safe client for a configured embeddings endpoint."""

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        model_name: str,
        timeout_seconds: float = 20.0,
    ) -> None:
        if not endpoint.startswith("https://"):
            raise ValueError("Embedding endpoint must use HTTPS")
        if not api_key:
            raise ValueError("Embedding API key is required")
        if not model_name:
            raise ValueError("Embedding model name is required")
        self.endpoint = endpoint
        self.api_key = api_key
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds

    def embed(self, text: str) -> list[float]:
        payload = json.dumps(
            {"model": self.model_name, "input": [text]},
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        try:
            vector = [float(value) for value in body["data"][0]["embedding"]]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise RuntimeError("Embedding endpoint returned an invalid response") from exc
        if not vector or any(not math.isfinite(value) for value in vector):
            raise RuntimeError("Embedding endpoint returned a non-finite or empty vector")
        return vector


def embedding_provider_from_env() -> EmbeddingProvider:
    """Build the explicitly configured provider without logging credentials."""
    mode = os.environ.get("DIANXUN_EMBEDDING_MODE", "hash").strip().lower()
    if mode == "hash":
        return HashEmbeddingProvider()
    if mode != "remote":
        raise ValueError("DIANXUN_EMBEDDING_MODE must be 'hash' or 'remote'")
    return OpenAICompatibleEmbeddingProvider(
        endpoint=os.environ.get("DIANXUN_EMBEDDING_ENDPOINT", ""),
        api_key=os.environ.get("DIANXUN_EMBEDDING_API_KEY", ""),
        model_name=os.environ.get("DIANXUN_EMBEDDING_MODEL", ""),
    )
