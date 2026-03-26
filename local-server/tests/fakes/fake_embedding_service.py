"""Fake in-memory implementation of EmbeddingService for testing."""

import sys
import os
import hashlib

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class FakeEmbeddingService:
    """Deterministic embedding service for unit testing using SHA-256 hashing."""

    EMBEDDING_DIMENSION = 32

    def embed_text(self, text: str) -> list[float]:
        """
        Generate a deterministic fake embedding by hashing text and converting
        to a fixed-length list of float values.

        Args:
            text: The text to embed

        Returns:
            Deterministic fixed-length list of float values
        """
        hash_bytes = hashlib.sha256(text.encode()).digest()
        return [float(byte) / 256.0 for byte in hash_bytes]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Embed multiple texts in batch.

        Args:
            texts: List of texts to embed

        Returns:
            List of fixed-length float embeddings
        """
        return [self.embed_text(t) for t in texts]

    def similarity(self, embedding_a: list[float], embedding_b: list[float]) -> float:
        """
        Compute cosine similarity between two embeddings.

        Args:
            embedding_a: First embedding as list of floats
            embedding_b: Second embedding as list of floats

        Returns:
            Similarity score (typically 0.0 to 1.0)
        """
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
