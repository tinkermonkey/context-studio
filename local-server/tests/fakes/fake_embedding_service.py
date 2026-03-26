"""Fake in-memory implementation of EmbeddingService for testing."""

import sys
import os
import hashlib
import struct

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class FakeEmbeddingService:
    """Deterministic embedding service for unit testing using SHA-256 hashing."""

    def embed_text(self, text: str) -> bytes:
        """
        Generate a deterministic fake embedding by hashing text and serializing
        the hash bytes as float32 values.

        Args:
            text: The text to embed

        Returns:
            Serialized float32 numpy array as bytes
        """
        hash_bytes = hashlib.sha256(text.encode()).digest()
        # Convert each hash byte to a float in [0, 1) and pack as float32
        floats = [float(byte) / 256.0 for byte in hash_bytes]
        return struct.pack(f'{len(floats)}f', *floats)

    def embed_batch(self, texts: list[str]) -> list[bytes]:
        """
        Embed multiple texts in batch.

        Args:
            texts: List of texts to embed

        Returns:
            List of serialized embeddings
        """
        return [self.embed_text(t) for t in texts]

    def similarity(self, embedding_a: bytes, embedding_b: bytes) -> float:
        """
        Compute cosine similarity between two embeddings.

        Args:
            embedding_a: First embedding as serialized bytes
            embedding_b: Second embedding as serialized bytes

        Returns:
            Similarity score (typically 0.0 to 1.0)
        """
        if not embedding_a or not embedding_b:
            return 0.0

        # Unpack bytes into float arrays
        len_a = len(embedding_a) // 4
        len_b = len(embedding_b) // 4

        if len_a != len_b:
            return 0.0

        floats_a = struct.unpack(f'{len_a}f', embedding_a)
        floats_b = struct.unpack(f'{len_b}f', embedding_b)

        # Compute cosine similarity
        dot_product = sum(a * b for a, b in zip(floats_a, floats_b))
        norm_a = sum(a * a for a in floats_a) ** 0.5
        norm_b = sum(b * b for b in floats_b) ** 0.5

        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0

        return dot_product / (norm_a * norm_b)
