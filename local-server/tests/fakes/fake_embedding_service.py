"""
Fake in-memory implementation of EmbeddingService for testing.

This implementation generates deterministic embeddings using SHA-256 hashing.
It does not call any external services and is suitable for unit tests.
"""

import hashlib


class FakeEmbeddingService:
    """
    In-memory embedding service that generates deterministic embeddings.

    Uses SHA-256 hashing to produce consistent 32-byte embeddings for any input.
    Suitable for unit tests that need embedding functionality without external
    service calls.
    """

    def embed_text(self, text: str) -> bytes:
        """
        Embed a single text into a vector.

        Args:
            text: The text to embed

        Returns:
            The embedding as bytes (SHA-256 hash, 32 bytes)
        """
        return hashlib.sha256(text.encode()).digest()

    def embed_batch(self, texts: list[str]) -> list[bytes]:
        """
        Embed multiple texts in batch.

        Args:
            texts: List of texts to embed

        Returns:
            List of embeddings as bytes
        """
        return [self.embed_text(t) for t in texts]

    def similarity(self, embedding_a: bytes, embedding_b: bytes) -> float:
        """
        Compute similarity between two embeddings.

        Computes byte-level overlap proportion: the ratio of matching bytes
        to the maximum length of the two embeddings.

        Args:
            embedding_a: First embedding
            embedding_b: Second embedding

        Returns:
            Similarity score as float (0.0 to 1.0)
        """
        if not embedding_a or not embedding_b:
            return 0.0

        matches = sum(a == b for a, b in zip(embedding_a, embedding_b))
        max_len = max(len(embedding_a), len(embedding_b))

        if max_len == 0:
            return 0.0

        return matches / max_len
