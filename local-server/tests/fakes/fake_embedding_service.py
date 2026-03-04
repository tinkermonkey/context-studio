"""
Fake implementation of EmbeddingService for testing.

Provides a deterministic embedding generation strategy using SHA-256 hashing,
ensuring that the same text always produces the same embedding.
"""

import hashlib


class FakeEmbeddingService:
    """Deterministic fake embedding service using hash-based embeddings.

    Generates consistent, deterministic embeddings suitable for testing.
    The same text will always produce the same 32-byte embedding.
    """

    def generate(self, text: str) -> bytes:
        """Generate a deterministic 32-byte embedding for text.

        Args:
            text: The text to embed.

        Returns:
            A 32-byte SHA-256 hash of the text as bytes.
        """
        return hashlib.sha256(text.encode()).digest()

    def similarity(self, embedding_a: bytes, embedding_b: bytes) -> float:
        """Calculate similarity between two embeddings.

        Similarity is computed as the proportion of matching bytes, with
        identical embeddings returning 1.0 and completely different embeddings
        returning 0.0.

        Args:
            embedding_a: First embedding as bytes.
            embedding_b: Second embedding as bytes.

        Returns:
            Similarity score between 0.0 and 1.0.
        """
        if embedding_a == embedding_b:
            return 1.0
        matches = sum(a == b for a, b in zip(embedding_a, embedding_b))
        return matches / max(len(embedding_a), len(embedding_b))

    def batch_generate(self, texts: list) -> list:
        """Generate embeddings for multiple texts.

        Args:
            texts: A list of text strings to embed.

        Returns:
            A list of byte embeddings corresponding to each input text.
        """
        return [self.generate(t) for t in texts]
