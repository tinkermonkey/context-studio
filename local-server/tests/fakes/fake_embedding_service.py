"""Fake in-memory implementation of EmbeddingService for testing."""

import sys
import os
import hashlib

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class FakeEmbeddingService:
    """Deterministic embedding service for unit testing using SHA-256 hashing."""

    def embed_text(self, text: str) -> bytes:
        return hashlib.sha256(text.encode()).digest()

    def embed_batch(self, texts: list[str]) -> list[bytes]:
        return [self.embed_text(t) for t in texts]

    def similarity(self, embedding_a: bytes, embedding_b: bytes) -> float:
        if not embedding_a or not embedding_b:
            return 0.0
        matches = sum(a == b for a, b in zip(embedding_a, embedding_b))
        return matches / len(embedding_a)
