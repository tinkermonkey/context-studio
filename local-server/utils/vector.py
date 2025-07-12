# Existing imports and code...

def decode_emb(emb):
    """Decode a vector embedding from bytes to a list of floats."""
    import numpy as np
    if emb is None:
        return None
    if isinstance(emb, bytes):
        return np.frombuffer(emb, dtype=np.float32).tolist()
    return emb
import numpy as np

def cosine_similarity(vec1, vec2):
    if vec1 is None or vec2 is None:
        return 0.0
    # Accept bytes or list/array
    def decode(v):
        if isinstance(v, bytes):
            return np.frombuffer(v, dtype=np.float32)
        return np.array(v, dtype=np.float32)
    v1 = decode(vec1)
    v2 = decode(vec2)
    if np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0:
        return 0.0
    return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
