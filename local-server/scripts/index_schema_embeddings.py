#!/usr/bin/env python
"""
Backfill title/definition embeddings for existing schema entities.

Populates the ontology_entities.title_embedding / definition_embedding columns
(added by the 'add title/definition embeddings' migration) for all classes and
property definitions, so the SchemaVectorIndex can search them. Safe to re-run —
it recomputes every entity's vectors.

Usage (from local-server/, venv active):
    python scripts/index_schema_embeddings.py
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
from adapters.persistence.sqlite.connection import DatabaseManager
from adapters.persistence.sqlite.schema_vector_index import SqliteSchemaVectorIndex
from config import get_config_manager


def main() -> int:
    settings = get_config_manager().get_settings()
    db_manager = DatabaseManager()
    db_manager.initialize(
        local_db_url=f"sqlite:///{settings.database.local_db_path}",
        operations_db_url=f"sqlite:///{settings.database.operations_db_path}",
    )
    session_factory = db_manager.get_local_session_factory()
    embedding_service = SentenceTransformerEmbedding(model_name="all-MiniLM-L12-v2")

    index = SqliteSchemaVectorIndex(session_factory, embedding_service)
    count = index.reindex_all()
    print(f"Indexed {count} schema entities (classes + property definitions).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
