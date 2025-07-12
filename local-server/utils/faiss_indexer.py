import faiss
import numpy as np
from threading import Lock
from utils.logger import get_logger

class FaissIndexer:
    def __init__(self, dim, entity_type):
        self.dim = dim
        self.entity_type = entity_type
        self.logger = get_logger(f"faiss_indexer.{entity_type}")
        self.index = faiss.IndexFlatL2(dim)
        self.id_map = {}  # sqlite_id -> faiss_idx
        self.rev_id_map = {}  # faiss_idx -> sqlite_id
        self.lock = Lock()
        self.next_faiss_idx = 0

    def add(self, sqlite_id, vector):
        with self.lock:
            vec = np.array(vector, dtype=np.float32).reshape(1, -1)
            self.index.add(vec)
            self.id_map[sqlite_id] = self.next_faiss_idx
            self.rev_id_map[self.next_faiss_idx] = sqlite_id
            self.next_faiss_idx += 1
            self.logger.debug(f"Added {sqlite_id} to FAISS index at {self.next_faiss_idx-1}")

    def update(self, sqlite_id, vector):
        with self.lock:
            if sqlite_id in self.id_map:
                faiss_idx = self.id_map[sqlite_id]
                vec = np.array(vector, dtype=np.float32).reshape(1, -1)
                self.index.reconstruct(faiss_idx)  # ensure index exists
                self.index.remove_ids(np.array([faiss_idx], dtype=np.int64))
                self.index.add_with_ids(vec, np.array([faiss_idx], dtype=np.int64))
                self.logger.debug(f"Updated {sqlite_id} in FAISS index at {faiss_idx}")
            else:
                self.add(sqlite_id, vector)

    def remove(self, sqlite_id):
        with self.lock:
            if sqlite_id in self.id_map:
                faiss_idx = self.id_map.pop(sqlite_id)
                self.rev_id_map.pop(faiss_idx, None)
                self.index.remove_ids(np.array([faiss_idx], dtype=np.int64))
                self.logger.debug(f"Removed {sqlite_id} from FAISS index at {faiss_idx}")

    def search(self, vector, top_n=10):
        with self.lock:
            if self.index.ntotal == 0:
                return []
            vec = np.array(vector, dtype=np.float32).reshape(1, -1)
            D, I = self.index.search(vec, top_n)
            results = []
            for idx, dist in zip(I[0], D[0]):
                if idx == -1:
                    continue
                sqlite_id = self.rev_id_map.get(idx)
                if sqlite_id is not None:
                    results.append((sqlite_id, dist))
            return results

    def size(self):
        with self.lock:
            return self.index.ntotal
