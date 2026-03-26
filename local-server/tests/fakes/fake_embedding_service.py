"""Fake in-memory implementation of EmbeddingService for testing."""

import sys
import os
import hashlib

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class FakeEmbeddingService:
    """Deterministic embedding service for unit testing using SHA-256 hashing."""

    def embed_text(self, text: str) -> list[float]:
        hash_bytes = hashlib.sha256(text.encode()).digest()
        return [float(byte) / 256.0 for byte in hash_bytes]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(t) for t in texts]

    def similarity(self, embedding_a: list[float], embedding_b: list[float]) -> float:
        if not embedding_a or not embedding_b:
            return 0.0
        if len(embedding_a) != len(embedding_b):
            return 0.0
        dot_product = sum(a * b for a, b in zip(embedding_a, embedding_b))
        norm_a = sum(a * a for a in embedding_a) ** 0.5
        norm_b = sum(b * b for b in embedding_b) ** 0.5
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot_product / (norm_a * norm_b)
