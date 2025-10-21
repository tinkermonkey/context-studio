from sentence_transformers import SentenceTransformer
import numpy as np
import torch
import threading

# Module-level singleton for thread-safe model access
_model = None
_model_lock = threading.Lock()

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
                device = 'cpu'
                # Load model with explicit device specification to avoid meta tensor issues
                _model = SentenceTransformer('all-MiniLM-L12-v2', device=device)
    
    return _model

def generate_embedding(text: str):
    """
    Generate embedding for the given text.
    
    Uses the singleton SentenceTransformer model (thread-safe).
    First call loads the model (~1.5s), subsequent calls are fast (~20-50ms).
    
    Args:
        text: Text to generate embedding for
        
    Returns:
        Embedding as bytes (numpy float32 array serialized)
    """
    model = get_model()
    embedding = model.encode([text])[0]
    return np.array(embedding, dtype=np.float32).tobytes()

def cleanup_model():
    """Clean up the singleton model instance."""
    global _model
    
    if _model is not None:
        _model = None
