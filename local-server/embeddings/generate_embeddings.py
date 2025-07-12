from sentence_transformers import SentenceTransformer
import numpy as np

_model = None

def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model

def generate_embedding(text: str):
    model = get_model()
    embedding = model.encode([text])[0]
    return np.array(embedding, dtype=np.float32).tobytes()
