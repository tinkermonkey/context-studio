"""
Schema.org import pipeline with vector embeddings and relationship extraction.

This module implements Phase 2 of the reference database import workflow:
- Fetches Schema.org JSON-LD with retry logic and exponential backoff
- Generates vector embeddings for titles and definitions
- Implements 5-step vector table synchronization workflow
- Extracts Schema.org relationships (subClassOf, domainIncludes, rangeIncludes, inverseOf)
- Provides transaction boundaries with rollback support
- Implements lock file management for concurrent import protection
"""

import os
import json
import time
import logging
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from uuid import uuid4

import requests
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from reference_db.config import ReferenceConfig
from reference_db.manager import ReferenceManager
from reference_db.models import ReferenceNode, ReferenceLink
from embeddings.generate_embeddings import generate_embedding

logger = logging.getLogger(__name__)

# Constants
DEFAULT_BATCH_SIZE = 200
DEFAULT_RETRY_COUNT = 3
LOCK_FILE_STALE_HOURS = 1
SOURCE_NAME = "schema.org"


class SchemaOrgImportError(Exception):
    """Base exception for Schema.org import errors."""
    pass


class DownloadError(SchemaOrgImportError):
    """Error during Schema.org data download."""
    pass


class ParseError(SchemaOrgImportError):
    """Error during JSON-LD parsing."""
    pass


class EmbeddingError(SchemaOrgImportError):
    """Error during embedding generation."""
    pass


class LockError(SchemaOrgImportError):
    """Error acquiring or managing lock file."""
    pass


class SchemaOrgImporter:
    """
    Manages the import of Schema.org data into the reference database.

    This class implements the complete import pipeline including:
    - HTTP download with retry logic
    - JSON-LD parsing
    - Embedding generation in configurable batches
    - 5-step vector table synchronization
    - Relationship extraction and link creation
    - Transaction management with rollback support
    - Lock file management for concurrent import protection
    """

    def __init__(self, config: ReferenceConfig, manager: ReferenceManager):
        """
        Initialize the Schema.org importer.

        Args:
            config: ReferenceConfig with operational parameters
            manager: ReferenceManager instance for database operations
        """
        self.config = config
        self.manager = manager
        self.lock_path = f"{manager.db_path}.import.lock"

    def import_schema_org(self, batch_size: int = DEFAULT_BATCH_SIZE) -> Dict[str, Any]:
        """
        Execute the complete Schema.org import pipeline.

        This method implements the 5-step vector table synchronization workflow:
        1. Download and parse Schema.org JSON-LD
        2. Generate embeddings for all nodes (title and definition)
        3. Insert nodes with embeddings in single transaction (Phase 3)
        4. Create vec0 virtual table and populate via INSERT...SELECT (atomic)
        5. Extract and insert relationships in separate transaction

        Args:
            batch_size: Number of items to process per batch (default: 200)

        Returns:
            Dict with import statistics and status

        Raises:
            LockError: If another import is in progress
            DownloadError: If download fails after retries
            ParseError: If JSON-LD parsing fails
            EmbeddingError: If embedding generation fails
            SchemaOrgImportError: For other import failures
        """
        logger.info("Starting Schema.org import pipeline")

        # Check and acquire lock
        self._acquire_lock()

        try:
            # Step 1: Download and parse
            logger.info("Step 1: Downloading and parsing Schema.org JSON-LD")
            json_data = self._download_with_retry()
            entities, properties = self._parse_jsonld(json_data)

            total_items = len(entities) + len(properties)
            logger.info(f"Parsed {len(entities)} entities and {len(properties)} properties")

            # Step 2: Generate embeddings
            logger.info("Step 2: Generating embeddings in batches")
            embedded_nodes = self._generate_embeddings_batch(
                entities + properties,
                batch_size=batch_size
            )

            # Step 3: Insert nodes with embeddings in transaction
            logger.info("Step 3: Inserting nodes with embeddings")
            node_map = self._insert_nodes_transaction(embedded_nodes)

            # Step 4: Create and populate vec0 virtual table
            logger.info("Step 4: Creating and populating vec0 virtual table")
            self._create_vec_table()

            # Step 5: Extract and insert relationships
            logger.info("Step 5: Extracting and inserting relationships")
            link_count = self._insert_relationships_transaction(
                entities + properties,
                node_map
            )

            result = {
                "success": True,
                "nodes_imported": len(node_map),
                "links_imported": link_count,
                "timestamp": datetime.now().isoformat()
            }

            logger.info(f"Import complete: {result}")
            return result

        except Exception as e:
            logger.error(f"Import failed: {e}", exc_info=True)
            # Attempt rollback of any partial changes
            try:
                self.manager.session.rollback()
            except Exception:
                pass
            raise

        finally:
            # Always release lock
            self._release_lock()

    def _acquire_lock(self):
        """
        Acquire import lock file to prevent concurrent imports.

        Raises:
            LockError: If lock cannot be acquired or stale lock detected
        """
        # Check for stale lock files
        if os.path.exists(self.lock_path):
            lock_age = time.time() - os.path.getmtime(self.lock_path)
            stale_threshold = LOCK_FILE_STALE_HOURS * 3600

            if lock_age > stale_threshold:
                logger.warning(
                    f"Detected stale lock file (age: {lock_age/3600:.1f} hours). "
                    f"Removing stale lock."
                )
                try:
                    os.remove(self.lock_path)
                except Exception as e:
                    raise LockError(f"Failed to remove stale lock file: {e}")
            else:
                raise LockError(
                    f"Another import is in progress (lock file: {self.lock_path})"
                )

        # Create lock file
        try:
            with open(self.lock_path, 'w') as f:
                f.write(json.dumps({
                    "pid": os.getpid(),
                    "timestamp": datetime.now().isoformat()
                }))
            logger.info(f"Acquired import lock: {self.lock_path}")
        except Exception as e:
            raise LockError(f"Failed to create lock file: {e}")

    def _release_lock(self):
        """Release import lock file."""
        try:
            if os.path.exists(self.lock_path):
                os.remove(self.lock_path)
                logger.info(f"Released import lock: {self.lock_path}")
        except Exception as e:
            logger.warning(f"Failed to remove lock file: {e}")

    def _download_with_retry(self) -> str:
        """
        Download Schema.org JSON-LD with retry logic and exponential backoff.

        Returns:
            Path to downloaded temporary file

        Raises:
            DownloadError: If download fails after all retries
        """
        retry_count = self.config.retry_count
        timeout = self.config.request_timeout
        url = self.config.schema_org_api_url

        # Runtime URL validation (TC-SEC002)
        if not url.startswith('https://'):
            if not ('localhost' in url or '127.0.0.1' in url):
                raise DownloadError(
                    "Non-HTTPS URL rejected for security. "
                    "Only HTTPS URLs are allowed for remote sources."
                )

        logger.info(f"Downloading Schema.org data from {url}")

        for attempt in range(retry_count):
            try:
                # Exponential backoff: 1s, 2s, 4s, ...
                if attempt > 0:
                    delay = 2 ** (attempt - 1)
                    logger.info(f"Retry attempt {attempt + 1}/{retry_count} after {delay}s delay")
                    time.sleep(delay)

                response = requests.get(url, timeout=timeout)
                response.raise_for_status()

                # Write to temporary file
                tmp_file = tempfile.NamedTemporaryFile(
                    mode='w',
                    suffix='.jsonld',
                    delete=False
                )
                tmp_file.write(response.text)
                tmp_file.close()

                logger.info(f"Downloaded {len(response.text)} bytes to {tmp_file.name}")
                return tmp_file.name

            except requests.RequestException as e:
                logger.warning(f"Download attempt {attempt + 1} failed: {e}")
                if attempt == retry_count - 1:
                    raise DownloadError(
                        f"Failed to download after {retry_count} attempts: {e}"
                    )

        raise DownloadError("Download failed for unknown reason")

    def _parse_jsonld(self, file_path: str) -> Tuple[List[Dict], List[Dict]]:
        """
        Parse Schema.org JSON-LD file into entities and properties.

        Args:
            file_path: Path to JSON-LD file

        Returns:
            Tuple of (entities, properties) as lists of dictionaries

        Raises:
            ParseError: If parsing fails
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ParseError(f"Invalid JSON-LD: {e}")
        except Exception as e:
            raise ParseError(f"Failed to read file: {e}")
        finally:
            # Clean up temp file
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass

        # Extract graph items
        items = []
        if isinstance(data, dict) and "@graph" in data:
            items = data["@graph"]
        elif isinstance(data, list):
            items = data
        else:
            raise ParseError("Unrecognized JSON-LD structure")

        entities = []
        properties = []

        for item in items:
            item_type = item.get("@type", "")
            if isinstance(item_type, list):
                item_type = " ".join(item_type)

            # Classify as entity or property
            if "rdfs:Class" in item_type or "Class" in item_type:
                entities.append(item)
            elif "rdf:Property" in item_type or "Property" in item_type:
                properties.append(item)
            else:
                # Heuristic: properties have domain/range
                if any(k in item for k in ["domainIncludes", "rangeIncludes",
                                           "schema:domainIncludes", "schema:rangeIncludes"]):
                    properties.append(item)
                else:
                    entities.append(item)

        logger.info(f"Parsed {len(entities)} entities and {len(properties)} properties")
        return entities, properties

    def _generate_embeddings_batch(
        self,
        items: List[Dict],
        batch_size: int = DEFAULT_BATCH_SIZE
    ) -> List[Dict[str, Any]]:
        """
        Generate embeddings for a list of Schema.org items.

        This method processes items in configurable batches and generates
        separate embeddings for title and definition fields.

        Args:
            items: List of Schema.org items (entities or properties)
            batch_size: Number of items to process per batch

        Returns:
            List of dictionaries with item data and embeddings

        Raises:
            EmbeddingError: If embedding generation fails (fail-fast)
        """
        embedded_items = []
        failed_items = []

        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1} ({i+1}-{i+len(batch)}/{len(items)})")

            for item in batch:
                try:
                    # Extract fields
                    external_id = item.get("@id", "")
                    title = (
                        item.get("rdfs:label") or
                        item.get("label") or
                        item.get("name") or
                        ""
                    )
                    definition = (
                        item.get("rdfs:comment") or
                        item.get("comment") or
                        item.get("description") or
                        ""
                    )

                    # Generate embeddings separately for title and definition
                    title_embedding = None
                    definition_embedding = None

                    if title:
                        title_embedding = generate_embedding(title)

                    if definition:
                        definition_embedding = generate_embedding(definition)

                    embedded_items.append({
                        "external_id": external_id,
                        "title": title,
                        "definition": definition,
                        "title_embedding": title_embedding,
                        "definition_embedding": definition_embedding,
                        "raw_data": item
                    })

                except Exception as e:
                    error_msg = f"Failed to generate embedding for {item.get('@id', 'unknown')}: {e}"
                    logger.error(error_msg)
                    failed_items.append(item.get("@id", "unknown"))

        # Fail-fast behavior (TC-I001)
        if failed_items:
            raise EmbeddingError(
                f"Embedding generation failed for {len(failed_items)} items. "
                f"Failed IDs: {failed_items[:5]}..."
            )

        logger.info(f"Generated embeddings for {len(embedded_items)} items")
        return embedded_items

    def _insert_nodes_transaction(
        self,
        embedded_nodes: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """
        Insert nodes with embeddings in a single transaction (Phase 3).

        This method uses transaction boundaries to ensure atomicity.
        If any insert fails, the entire transaction is rolled back.

        Args:
            embedded_nodes: List of nodes with embeddings

        Returns:
            Dict mapping external_id to node UUID

        Raises:
            SchemaOrgImportError: If transaction fails
        """
        node_map = {}

        try:
            # Clear any existing nodes from this source for idempotency
            self.manager.session.query(ReferenceNode).filter_by(source=SOURCE_NAME).delete()
            self.manager.session.commit()

            # Start transaction for new nodes
            with self.manager.session.begin_nested():
                for node_data in embedded_nodes:
                    node = ReferenceNode(
                        id=str(uuid4()),
                        title=node_data["title"],
                        definition=node_data["definition"],
                        source=SOURCE_NAME,
                        external_id=node_data["external_id"],
                        attributes=json.dumps(node_data["raw_data"]),
                        title_embedding=node_data["title_embedding"],
                        definition_embedding=node_data["definition_embedding"],
                        created_at=datetime.now().isoformat(),
                        updated_at=datetime.now().isoformat()
                    )

                    self.manager.session.add(node)
                    node_map[node_data["external_id"]] = node.id

            # Commit transaction
            self.manager.session.commit()
            logger.info(f"Inserted {len(node_map)} nodes in transaction")

        except SQLAlchemyError as e:
            logger.error(f"Transaction failed, rolling back: {e}")
            self.manager.session.rollback()
            raise SchemaOrgImportError(f"Node insertion failed: {e}")

        return node_map

    def _create_vec_table(self):
        """
        Create vec0 virtual table and populate via INSERT...SELECT (Phase 4).

        This method implements atomic vector table creation and population
        as specified in the 5-step workflow.

        Note: If sqlite-vec extension is not available, this step is skipped.
        The embeddings are still stored in the reference_nodes table as BLOB columns.
        """
        try:
            # Check if sqlite-vec extension is available
            try:
                test_result = self.manager.session.execute(
                    text("SELECT vec_version()")
                ).fetchone()
            except Exception:
                logger.warning(
                    "sqlite-vec extension not available, skipping vec table creation. "
                    "Embeddings are still stored in reference_nodes table."
                )
                return

            # Determine embedding dimensions from first non-null embedding
            result = self.manager.session.execute(
                text("""
                    SELECT title_embedding
                    FROM reference_nodes
                    WHERE title_embedding IS NOT NULL
                    LIMIT 1
                """)
            ).fetchone()

            if not result or not result[0]:
                logger.warning("No embeddings found, skipping vec table creation")
                return

            # Calculate dimensions (float32 = 4 bytes per dimension)
            embedding_bytes = result[0]
            dims = len(embedding_bytes) // 4

            logger.info(f"Creating vec0 table with {dims} dimensions")

            # Drop existing vec table if it exists
            self.manager.session.execute(
                text("DROP TABLE IF EXISTS reference_nodes_vec")
            )

            # Create vec0 virtual table with two embedding columns
            self.manager.session.execute(
                text(f"""
                    CREATE VIRTUAL TABLE reference_nodes_vec
                    USING vec0(
                        id TEXT PRIMARY KEY,
                        title_embedding FLOAT[{dims}],
                        definition_embedding FLOAT[{dims}]
                    )
                """)
            )

            # Populate vec table via INSERT...SELECT (atomic operation)
            self.manager.session.execute(
                text("""
                    INSERT INTO reference_nodes_vec (id, title_embedding, definition_embedding)
                    SELECT id, title_embedding, definition_embedding
                    FROM reference_nodes
                    WHERE source = :source
                """),
                {"source": SOURCE_NAME}
            )

            self.manager.session.commit()
            logger.info("Vec0 table created and populated successfully")

        except SQLAlchemyError as e:
            error_msg = str(e)
            # If it's just a vec extension issue, log warning and continue
            if "vec" in error_msg.lower() or "extension" in error_msg.lower():
                logger.warning(f"Vec table creation skipped (extension issue): {e}")
                try:
                    self.manager.session.rollback()
                except Exception:
                    pass
            else:
                # Other SQLAlchemy errors should fail
                logger.error(f"Vec table creation failed: {e}")
                self.manager.session.rollback()
                raise SchemaOrgImportError(f"Vec table creation failed: {e}")

    def _insert_relationships_transaction(
        self,
        items: List[Dict],
        node_map: Dict[str, str]
    ) -> int:
        """
        Extract and insert Schema.org relationships in separate transaction (Phase 5).

        Extracts the following relationship types:
        - subClassOf: Entity inheritance relationships
        - domainIncludes: Property domain constraints
        - rangeIncludes: Property range constraints
        - inverseOf: Inverse property relationships

        Args:
            items: List of Schema.org items
            node_map: Mapping of external_id to node UUID

        Returns:
            Number of links inserted

        Raises:
            SchemaOrgImportError: If transaction fails
        """
        links_to_insert = []

        # Extract relationships
        for item in items:
            external_id = item.get("@id", "")
            subject_id = node_map.get(external_id)

            if not subject_id:
                continue

            # Extract subClassOf
            subclass_of = item.get("rdfs:subClassOf") or item.get("subClassOf")
            if subclass_of:
                if isinstance(subclass_of, list):
                    for parent in subclass_of:
                        parent_id = self._extract_id(parent)
                        if parent_id and parent_id in node_map:
                            links_to_insert.append({
                                "subject": subject_id,
                                "predicate": "subClassOf",
                                "object": node_map[parent_id],
                                "metadata": {"source": "schema.org"}
                            })
                else:
                    parent_id = self._extract_id(subclass_of)
                    if parent_id and parent_id in node_map:
                        links_to_insert.append({
                            "subject": subject_id,
                            "predicate": "subClassOf",
                            "object": node_map[parent_id],
                            "metadata": {"source": "schema.org"}
                        })

            # Extract domainIncludes
            domain_includes = (
                item.get("schema:domainIncludes") or
                item.get("domainIncludes")
            )
            if domain_includes:
                if isinstance(domain_includes, list):
                    for domain in domain_includes:
                        domain_id = self._extract_id(domain)
                        if domain_id and domain_id in node_map:
                            links_to_insert.append({
                                "subject": subject_id,
                                "predicate": "domainIncludes",
                                "object": node_map[domain_id],
                                "metadata": {"source": "schema.org"}
                            })

            # Extract rangeIncludes
            range_includes = (
                item.get("schema:rangeIncludes") or
                item.get("rangeIncludes")
            )
            if range_includes:
                if isinstance(range_includes, list):
                    for range_item in range_includes:
                        range_id = self._extract_id(range_item)
                        if range_id and range_id in node_map:
                            links_to_insert.append({
                                "subject": subject_id,
                                "predicate": "rangeIncludes",
                                "object": node_map[range_id],
                                "metadata": {"source": "schema.org"}
                            })

            # Extract inverseOf
            inverse_of = item.get("inverseOf") or item.get("schema:inverseOf")
            if inverse_of:
                inverse_id = self._extract_id(inverse_of)
                if inverse_id and inverse_id in node_map:
                    links_to_insert.append({
                        "subject": subject_id,
                        "predicate": "inverseOf",
                        "object": node_map[inverse_id],
                        "metadata": {"source": "schema.org"}
                    })

        # Insert links in transaction
        try:
            with self.manager.session.begin_nested():
                for link_data in links_to_insert:
                    link = ReferenceLink(
                        id=str(uuid4()),
                        subject_node=link_data["subject"],
                        predicate=link_data["predicate"],
                        object_node=link_data["object"],
                        attributes=json.dumps(link_data["metadata"]),
                        created_at=datetime.now().isoformat(),
                        updated_at=datetime.now().isoformat()
                    )
                    self.manager.session.add(link)

            self.manager.session.commit()
            logger.info(f"Inserted {len(links_to_insert)} relationship links")

        except SQLAlchemyError as e:
            logger.error(f"Link insertion failed, rolling back: {e}")
            self.manager.session.rollback()
            raise SchemaOrgImportError(f"Link insertion failed: {e}")

        return len(links_to_insert)

    def _extract_id(self, value: Any) -> Optional[str]:
        """
        Extract @id from a value that might be a dict or string.

        Args:
            value: Value to extract ID from

        Returns:
            Extracted ID or None
        """
        if isinstance(value, dict):
            return value.get("@id")
        elif isinstance(value, str):
            return value
        return None
