"""Quality-gated knowledge candidates and PolarDB pgvector retrieval."""

from .embeddings import (
    EmbeddingProvider,
    HashEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
    embedding_provider_from_env,
)
from .evaluation import evaluate_retrieval
from .repository import KnowledgeService
from .store import add, all_entries, init, review, search

__all__ = [
    "EmbeddingProvider",
    "HashEmbeddingProvider",
    "KnowledgeService",
    "OpenAICompatibleEmbeddingProvider",
    "add",
    "all_entries",
    "embedding_provider_from_env",
    "evaluate_retrieval",
    "init",
    "review",
    "search",
]
