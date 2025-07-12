import numpy as np
import sqlite3
from utils.faiss_indexer import FaissIndexer
from utils.logger import get_logger

class FaissManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.logger = get_logger("faiss_manager")
        self.indexes = {}
        self.dim = 384  # hardcoded for MiniLM-L6-v2

    def load_all_indexes(self):
        self.logger.info("Loading FAISS indexes from SQLite...")
        self.indexes = {
            'layer': FaissIndexer(self.dim, 'layer'),
            'domain': FaissIndexer(self.dim, 'domain'),
            'term': FaissIndexer(self.dim, 'term'),
        }
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        # Layers
        cur.execute("SELECT id, title_embedding FROM layers WHERE title_embedding IS NOT NULL")
        for row in cur:
            vec = np.frombuffer(row['title_embedding'], dtype=np.float32)
            self.indexes['layer'].add(row['id'], vec)
        self.logger.info(f"Loaded {self.indexes['layer'].size()} layer vectors into FAISS.")
        # Domains
        cur.execute("SELECT id, title_embedding FROM domains WHERE title_embedding IS NOT NULL")
        for row in cur:
            vec = np.frombuffer(row['title_embedding'], dtype=np.float32)
            self.indexes['domain'].add(row['id'], vec)
        self.logger.info(f"Loaded {self.indexes['domain'].size()} domain vectors into FAISS.")
        # Terms
        cur.execute("SELECT id, title_embedding FROM terms WHERE title_embedding IS NOT NULL")
        for row in cur:
            vec = np.frombuffer(row['title_embedding'], dtype=np.float32)
            self.indexes['term'].add(row['id'], vec)
        self.logger.info(f"Loaded {self.indexes['term'].size()} term vectors into FAISS.")
        conn.close()
        self.logger.info("All FAISS indexes loaded.")

    def get_index(self, entity_type):
        return self.indexes.get(entity_type)
