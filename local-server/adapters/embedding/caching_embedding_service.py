"""
Memoizing wrapper around an EmbeddingService.

The grounded sweeps in the eval harness (Loop A/B, see
`scripts/quality_tournament.py` and `scripts/quality_loop.py`) re-run the same
open_v1 pipeline dozens of times per iteration, changing only the config knobs.
The candidate labels handed to grounding are identical across those evals, so
the underlying SentenceTransformer forward pass for `.embed(label)` is repeated
many times for the same text.

`CachingEmbeddingService` wraps any EmbeddingService and memoizes `.embed(text)`
in a plain dict keyed by the exact text. Repeated `.embed(label)` calls for the
same text after the first are served from the cache instead of the model.
`embed_batch` and `similarity` delegate straight through to the wrapped service;
`embed_batch` is intentionally left uncached because the harness only reuses it
for one-shot index builds (`SchemaVectorIndex.reindex_all`), where the win is
negligible and per-text bookkeeping would add cost.

The wrapper is safe for the eval seam because the model is deterministic:
identical text always yields an identical vector, so a cached `.embed(text)`
result is indistinguishable from a fresh one — including when the SAME wrapped
service both builds the index (via `embed_batch` in `reindex_all`) and answers
grounding queries (via `.embed`).
"""

from domain.ontology.ports import EmbeddingService


class CachingEmbeddingService:
    """
    EmbeddingService decorator that memoizes single-text `.embed` calls.

    Implements the full EmbeddingService protocol structurally and delegates
    every uncached call to the wrapped service.
    """

    def __init__(self, wrapped: EmbeddingService) -> None:
        """
        Wrap an EmbeddingService with a single-text embedding cache.

        Args:
            wrapped: The underlying embedding service to delegate to.
        """
        self._wrapped = wrapped
        self._cache: dict[str, list[float]] = {}

    def embed(self, text: str) -> list[float]:
        """
        Embed a single text, returning a cached vector when available.

        Args:
            text: The text to embed.

        Returns:
            The embedding as a list of floats. The same text always returns the
            same vector, served from the cache after the first call.
        """
        cached = self._cache.get(text)
        if cached is None:
            cached = self._wrapped.embed(text)
            self._cache[text] = cached
        return cached

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Embed multiple texts in batch, delegating straight to the wrapped service.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embeddings, each as a list of floats.
        """
        return self._wrapped.embed_batch(texts)

    def similarity(self, embedding_a: list[float], embedding_b: list[float]) -> float:
        """
        Compute similarity between two embeddings via the wrapped service.

        Args:
            embedding_a: First embedding as a list of floats.
            embedding_b: Second embedding as a list of floats.

        Returns:
            Similarity score as a float.
        """
        return self._wrapped.similarity(embedding_a, embedding_b)
