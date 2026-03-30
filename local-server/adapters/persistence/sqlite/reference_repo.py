"""LocalReferenceRepository adapter for offline reference lookups."""

import sqlite3
from pathlib import Path

from domain.extraction.ports import ReferenceResult, ReferenceRelation
from utils.logger import get_logger

logger = get_logger(__name__)


class LocalReferenceRepository:
    """
    Repository for offline reference data lookups.

    Queries pre-imported reference.db to provide fast, offline access to
    reference data from ConceptNet, DBpedia, Wikidata, and schema.org.

    Schema:
    - references: Stores indexed reference entities
      - id: INTEGER PRIMARY KEY
      - uri: TEXT UNIQUE
      - label: TEXT
      - description: TEXT
      - source: TEXT (source name: ConceptNet, DBpedia, Wikidata, schema.org)

    - reference_relations: Stores relationships between references
      - id: INTEGER PRIMARY KEY
      - subject_uri: TEXT
      - predicate: TEXT
      - object_uri: TEXT
      - source: TEXT
    """

    def __init__(self, db_path: str = "./reference.db"):
        """
        Initialize the repository.

        Args:
            db_path: Path to the reference.db SQLite database
        """
        self._db_path = db_path
        self._ensure_db()

    def _ensure_db(self) -> None:
        """
        Create database schema if it doesn't exist.

        This is idempotent and safe to call multiple times.

        Raises:
            OSError: If parent directory cannot be created
            sqlite3.DatabaseError: If database schema creation fails
        """
        try:
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)

            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS "references" (
                        id INTEGER PRIMARY KEY,
                        uri TEXT UNIQUE NOT NULL,
                        label TEXT NOT NULL,
                        description TEXT,
                        source TEXT NOT NULL
                    )
                    """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_references_uri ON "references"(uri)
                    """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_references_label ON "references"(label)
                    """
                )

                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS "reference_relations" (
                        id INTEGER PRIMARY KEY,
                        subject_uri TEXT NOT NULL,
                        predicate TEXT NOT NULL,
                        object_uri TEXT NOT NULL,
                        source TEXT NOT NULL
                    )
                    """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_relations_subject
                    ON "reference_relations"(subject_uri)
                    """
                )

                conn.commit()
        except OSError as e:
            logger.error(f"Failed to create directory for reference database: {e}")
            raise
        except sqlite3.DatabaseError as e:
            logger.error(f"Failed to initialize reference database schema: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error initializing reference database: {e}")
            raise

    def search(self, term: str, limit: int = 10) -> list[ReferenceResult]:
        """
        Search for references matching a term in the local database.

        Performs substring matching on labels and descriptions (case-insensitive).

        Args:
            term: Search query
            limit: Maximum number of results to return

        Returns:
            List of ReferenceResult objects from the local database
        """
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT uri, label, description, source
                    FROM "references"
                    WHERE label LIKE ? OR description LIKE ?
                    LIMIT ?
                    """,
                    (f"%{term}%", f"%{term}%", limit),
                )

                results = []
                for row in cursor.fetchall():
                    uri, label, description, source = row
                    results.append(
                        ReferenceResult(
                            uri=uri,
                            label=label,
                            description=description,
                            source=source,
                        )
                    )

                return results
        except Exception as e:
            logger.error("Local reference search failed for '%s': %s", term, e, exc_info=True)
            raise

    def get_relations(self, uri: str, limit: int = 10) -> list[ReferenceRelation]:
        """
        Get relationships for a URI from the local database.

        Args:
            uri: URI of the resource to find relations for
            limit: Maximum number of relations to return

        Returns:
            List of ReferenceRelation objects from the local database
        """
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT subject_uri, predicate, object_uri, source
                    FROM "reference_relations"
                    WHERE subject_uri = ?
                    LIMIT ?
                    """,
                    (uri, limit),
                )

                relations = []
                for row in cursor.fetchall():
                    subject_uri, predicate, object_uri, source = row
                    relations.append(
                        ReferenceRelation(
                            subject_uri=subject_uri,
                            predicate=predicate,
                            object_uri=object_uri,
                            source=source,
                        )
                    )

                return relations
        except Exception as e:
            logger.error("Local reference get_relations failed for '%s': %s", uri, e, exc_info=True)
            raise

    def import_reference(
        self, uri: str, label: str, description: str | None, source: str
    ) -> None:
        """
        Import a single reference into the database.

        Idempotent: if the URI already exists, it is updated.

        Args:
            uri: Unique URI for the reference
            label: Human-readable label
            description: Optional description
            source: Source name (ConceptNet, DBpedia, etc.)
        """
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO "references" (uri, label, description, source)
                    VALUES (?, ?, ?, ?)
                    """,
                    (uri, label, description, source),
                )
                conn.commit()
        except Exception as e:
            logger.error("Failed to import reference %s: %s", uri, e, exc_info=True)
            raise

    def import_relation(
        self,
        subject_uri: str,
        predicate: str,
        object_uri: str,
        source: str,
    ) -> None:
        """
        Import a single relationship into the database.

        Idempotent: if the relationship already exists, it is updated.

        Args:
            subject_uri: URI of the source entity
            predicate: Relationship type
            object_uri: URI of the target entity
            source: Source name (ConceptNet, DBpedia, etc.)
        """
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO "reference_relations"
                    (subject_uri, predicate, object_uri, source)
                    VALUES (?, ?, ?, ?)
                    """,
                    (subject_uri, predicate, object_uri, source),
                )
                conn.commit()
        except Exception as e:
            logger.error("Failed to import relation %s -> %s: %s", subject_uri, object_uri, e, exc_info=True)
            raise
