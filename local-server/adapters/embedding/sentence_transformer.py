"""
SentenceTransformer embedding adapter implementation.

This adapter implements the EmbeddingService port using the SentenceTransformer
library with a pre-trained model. Embeddings are cached at the class level to avoid
reloading the model for each request.

The current implementation uses the 'all-MiniLM-L12-v2' model by default,
which is lightweight and suitable for desktop deployment.
"""

from typing import TYPE_CHECKING, Optional

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from utils.logger import get_logger
from utils.async_executor import run_sync_in_executor

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)


class SentenceTransformerEmbedding:
    """
    Embedding service using SentenceTransformer pre-trained models.

    This adapter is responsible for converting text into fixed-length semantic
    embeddings. The embeddings are returned as lists of floats suitable for
    similarity comparisons and semantic search.

    The model is lazily loaded on first use to avoid startup delays.
    """

    def __init__(self, model_name: str = "all-MiniLM-L12-v2") -> None:
        """
        Initialize the embedding service.

        Args:
            model_name: Name of the SentenceTransformer model to use
        """
        self.model_name = model_name
        self._model: Optional[SentenceTransformer] = None

    def _ensure_model_loaded(self) -> None:
        """
        Lazily load the model if not already loaded.

        Defers model loading to the first embedding request to reduce
        application startup time.
        """
        if self._model is None:
            try:
                # Lazy import to avoid hard dependency on sentence-transformers
                from sentence_transformers import SentenceTransformer

                logger.info(f"Loading SentenceTransformer model: {self.model_name}")
                self._model = SentenceTransformer(self.model_name)
                logger.info("SentenceTransformer model loaded successfully")
            except ImportError:
                logger.error(
                    "sentence-transformers not installed. Install with: pip install sentence-transformers"
                )
                raise RuntimeError(
                    "SentenceTransformer model not available. Install sentence-transformers."
                )
            except Exception as e:
                logger.error(f"Failed to load SentenceTransformer model: {e}")
                raise

    def embed(self, text: str) -> list[float]:
        """
        Embed a single text into a vector.

        Args:
            text: The text to embed

        Returns:
            The embedding as a list of floats

        Raises:
            RuntimeError: If model loading fails
        """
        with tracer.start_as_current_span("embedding.encode") as span:
            span.set_attribute("embedding.model", self.model_name)
            span.set_attribute("embedding.text_count", 1)

            try:
                self._ensure_model_loaded()
                if self._model is None:
                    raise RuntimeError("Model failed to load")
                # SentenceTransformer.encode returns numpy array; convert to list
                embedding = self._model.encode(text, convert_to_tensor=False)
                return embedding.tolist()
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR))
                span.record_exception(e)
                logger.error(f"Failed to embed text: {e}")
                raise

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Embed multiple texts in batch.

        This method is more efficient than calling embed() multiple times
        as it processes texts in a single model pass.

        Args:
            texts: List of texts to embed

        Returns:
            List of embeddings, each as a list of floats

        Raises:
            RuntimeError: If model loading fails
        """
        with tracer.start_as_current_span("embedding.encode") as span:
            span.set_attribute("embedding.model", self.model_name)
            span.set_attribute("embedding.text_count", len(texts))

            try:
                self._ensure_model_loaded()
                if self._model is None:
                    raise RuntimeError("Model failed to load")
                # SentenceTransformer.encode returns numpy array; convert to list of lists
                embeddings = self._model.encode(texts, convert_to_tensor=False)
                return [emb.tolist() for emb in embeddings]
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR))
                span.record_exception(e)
                logger.error(f"Failed to embed batch: {e}")
                raise

    def similarity(self, embedding_a: list[float], embedding_b: list[float]) -> float:
        """
        Compute similarity between two embeddings using cosine similarity.

        Args:
            embedding_a: First embedding as a list of floats
            embedding_b: Second embedding as a list of floats

        Returns:
            Similarity score as float (typically 0.0 to 1.0 for cosine similarity)
        """
        try:
            import numpy as np
            from sklearn.metrics.pairwise import cosine_similarity  # type: ignore[import-untyped]

            # Convert to numpy arrays and compute cosine similarity
            arr_a = np.array(embedding_a).reshape(1, -1)
            arr_b = np.array(embedding_b).reshape(1, -1)
            similarity_score = cosine_similarity(arr_a, arr_b)[0, 0]
            return float(similarity_score)
        except ImportError:
            logger.error(
                "scikit-learn not installed. Install with: pip install scikit-learn"
            )
            raise RuntimeError("Similarity computation requires scikit-learn")
        except Exception as e:
            logger.error(f"Failed to compute similarity: {e}")
            raise

    def is_loaded(self) -> bool:
        """
        Check if the embedding model is currently loaded.

        Returns:
            True if the model is loaded, False otherwise
        """
        return self._model is not None

    def cleanup(self) -> None:
        """
        Clean up resources (e.g., unload model).

        Called during application shutdown.
        """
        if self._model is not None:
            self._model = None
            logger.info("SentenceTransformer model unloaded")

    async def embed_async(self, text: str) -> list[float]:
        """
        Embed a single text into a vector (async version).

        Runs the embedding operation in a thread pool to avoid blocking the event loop.

        Args:
            text: The text to embed

        Returns:
            The embedding as a list of floats

        Raises:
            RuntimeError: If model loading fails
        """
        return await run_sync_in_executor(self.embed, text)

    async def embed_batch_async(self, texts: list[str]) -> list[list[float]]:
        """
        Embed multiple texts in batch (async version).

        Runs the embedding operation in a thread pool to avoid blocking the event loop.

        Args:
            texts: List of texts to embed

        Returns:
            List of embeddings, each as a list of floats

        Raises:
            RuntimeError: If model loading fails
        """
        return await run_sync_in_executor(self.embed_batch, texts)

    async def similarity_async(
        self, embedding_a: list[float], embedding_b: list[float]
    ) -> float:
        """
        Compute similarity between two embeddings (async version).

        Runs the computation in a thread pool to avoid blocking the event loop.

        Args:
            embedding_a: First embedding as a list of floats
            embedding_b: Second embedding as a list of floats

        Returns:
            Similarity score as float
        """
        return await run_sync_in_executor(self.similarity, embedding_a, embedding_b)
