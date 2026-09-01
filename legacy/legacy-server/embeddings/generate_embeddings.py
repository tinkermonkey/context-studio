import threading
import time

import numpy as np
from sentence_transformers import SentenceTransformer

# Module-level singleton for thread-safe model access
_model = None
_model_lock = threading.Lock()

# Constants for retry logic
DEFAULT_EMBEDDING_RETRIES = 3
DEFAULT_EMBEDDING_RETRY_DELAY = 1  # seconds


def get_model():
    """
    Get or create the singleton SentenceTransformer model.

    Thread-safe via double-check locking pattern (consistent with other singletons).
    The model is loaded once and reused across all threads/requests.

    Returns:
        Cached SentenceTransformer model instance
    """
    global _model

    # Fast path: check without lock
    if _model is None:
        # Acquire lock for initialization
        with _model_lock:
            # Double-check after lock
            if _model is None:
                # Explicitly set device to CPU and avoid meta tensor issues
                device = "cpu"
                # Load model with explicit device specification to avoid meta tensor issues
                _model = SentenceTransformer("all-MiniLM-L12-v2", device=device)

    return _model


def generate_embedding(text: str, retries: int = DEFAULT_EMBEDDING_RETRIES):
    """
    Generate embedding for the given text with retry logic.

    Uses the singleton SentenceTransformer model (thread-safe).
    First call loads the model (~1.5s), subsequent calls are fast (~20-50ms).
    Retries with exponential backoff on transient failures.

    Args:
        text: Text to generate embedding for
        retries: Number of retry attempts on failure (default: 3)

    Returns:
        Embedding as bytes (numpy float32 array serialized)

    Raises:
        Exception: If embedding generation fails after all retries
    """
    last_error = None
    for attempt in range(retries):
        try:
            model = get_model()
            embedding = model.encode([text])[0]
            return np.array(embedding, dtype=np.float32).tobytes()
        except Exception as e:
            last_error = e
            if attempt < retries - 1:
                # Exponential backoff: 1s, 2s, 4s, ...
                delay = DEFAULT_EMBEDDING_RETRY_DELAY * (2**attempt)
                time.sleep(delay)
            continue

    # All retries exhausted
    raise last_error if last_error else Exception("Failed to generate embedding")


def cleanup_model():
    """Clean up the singleton model instance."""
    global _model

    if _model is not None:
        _model = None
