"""Fake in-memory implementation of EmbeddingService for testing."""

import sys
import os
import hashlib
import struct

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class FakeEmbeddingService:
    """Deterministic embedding service for unit testing using SHA-256 hashing.

    Returns embeddings as bytes (serialized float32 values), matching the
    EmbeddingService Protocol specification.
    """

    EMBEDDING_DIMENSION = 8  # 32 bytes / 4 bytes per float32

    def embed_text(self, text: str) -> bytes:
        """
        Generate a deterministic fake embedding by hashing text.

        Args:
            text: The text to embed

        Returns:
            Deterministic embedding as serialized bytes (32 bytes = 8 float32s)
        """
        hash_bytes = hashlib.sha256(text.encode()).digest()
        return hash_bytes[:32]

    def embed_batch(self, texts: list[str]) -> list[bytes]:
        """
        Embed multiple texts in batch.

        Args:
            texts: List of texts to embed

        Returns:
            List of embeddings as serialized bytes
        """
        return [self.embed_text(t) for t in texts]

    def similarity(self, embedding_a: bytes, embedding_b: bytes) -> float:
        """
        Compute similarity between two embeddings.

        Args:
            embedding_a: First embedding as serialized bytes
            embedding_b: Second embedding as serialized bytes

        Returns:
            Similarity score (typically 0.0 to 1.0)
        """
        if embedding_a == embedding_b:
            return 1.0

        # Hash both embeddings and convert first 4 bytes to float in [0, 1)
        combined = hashlib.sha256(embedding_a + embedding_b).digest()
        score = struct.unpack('f', combined[:4])[0]
        return max(0.0, min(1.0, score))
