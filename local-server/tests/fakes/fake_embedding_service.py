"""Fake in-memory implementation of EmbeddingService for testing."""

import hashlib
import math
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class FakeEmbeddingService:
    """Deterministic embedding service for unit testing using SHA-256 hashing.

    Returns embeddings as fixed-length lists of floats, matching the
    EmbeddingService Protocol specification (BA spec FR-1.15 and FR-1.22).
    """

    EMBEDDING_DIMENSION = 8  # 8 float values per embedding

    def embed(self, text: str) -> list[float]:
        """
        Generate a deterministic fake embedding by hashing text.

        Returns a fixed-length list of floats derived from SHA-256 hash
        of the input text. The embedding is deterministic: the same text
        always produces the same embedding.

        Args:
            text: The text to embed

        Returns:
            Deterministic embedding as a list of 8 floats in [0, 1)
        """
        hash_bytes = hashlib.sha256(text.encode()).digest()
        # Convert 32 bytes into 8 float values by taking 4-byte chunks
        embedding = []
        for i in range(self.EMBEDDING_DIMENSION):
            # Extract 4 bytes and convert to float in [0, 1) using integer normalization
            # This avoids NaN/Inf that can result from interpreting raw bytes as float32
            chunk = hash_bytes[i * 4 : (i + 1) * 4]
            int_val = int.from_bytes(chunk, byteorder="little")
            # Normalize to [0, 1) range using integer division
            normalized = (int_val % (2**32)) / (2**32)
            embedding.append(normalized)
        return embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Embed multiple texts in batch.

        Args:
            texts: List of texts to embed

        Returns:
            List of embeddings, each as a list of floats
        """
        return [self.embed(t) for t in texts]

    def similarity(self, embedding_a: list[float], embedding_b: list[float]) -> float:
        """
        Compute similarity between two embeddings using cosine similarity.

        Args:
            embedding_a: First embedding as a list of floats
            embedding_b: Second embedding as a list of floats

        Returns:
            Similarity score as float in range [0.0, 1.0]

        Raises:
            ValueError: If embeddings contain NaN or Inf values
        """
        if len(embedding_a) != len(embedding_b):
            raise ValueError("Embeddings must have the same length")

        # Check for NaN or Inf values which indicate invalid embeddings
        for val in embedding_a:
            if math.isnan(val) or math.isinf(val):
                raise ValueError(f"embedding_a contains invalid value: {val}")
        for val in embedding_b:
            if math.isnan(val) or math.isinf(val):
                raise ValueError(f"embedding_b contains invalid value: {val}")

        if embedding_a == embedding_b:
            return 1.0

        # Compute cosine similarity
        dot_product = sum(a * b for a, b in zip(embedding_a, embedding_b))
        norm_a = sum(a * a for a in embedding_a) ** 0.5
        norm_b = sum(b * b for b in embedding_b) ** 0.5

        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0

        cosine_sim = dot_product / (norm_a * norm_b)
        # Clamp to [0, 1] range
        return max(0.0, min(1.0, cosine_sim))
