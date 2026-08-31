# mypy: ignore-errors
"""
Schema.org import pipeline with vector embeddings and relationship extraction.

This module implements Phase 2 of the reference database import workflow:
- Fetches Schema.org JSON-LD with retry logic and exponential backoff
- Generates vector embeddings for titles and definitions
- Imports Schema.org Classes as ReferenceNodes (entities)
- Imports Schema.org Properties as ExternalPredicates (relationships)
- Extracts Schema.org Class hierarchy (subClassOf) as ReferenceLinks
- Property metadata (domainIncludes, rangeIncludes, inverseOf) stored in ExternalPredicate.attributes
- Implements 5-step vector table synchronization workflow
- Provides transaction boundaries with rollback support
- Implements lock file management for concurrent import protection
"""

import json
import logging
import os
import tempfile
import time
from datetime import datetime
from typing import Any
from uuid import uuid4

import requests
from embeddings.generate_embeddings import generate_embedding
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from reference_db.config import ReferenceConfig
from reference_db.manager import ReferenceManager
from reference_db.models import ExternalPredicate, ReferenceLink, ReferenceNode

logger = logging.getLogger(__name__)

# Constants
DEFAULT_BATCH_SIZE = 200
MAX_BATCH_SIZE = 5000
MIN_BATCH_SIZE = 1
DEFAULT_RETRY_COUNT = 3
DEFAULT_STALE_LOCK_THRESHOLD = 3600  # 1 hour in seconds
DEFAULT_EMBEDDING_DIMS = 384  # all-MiniLM-L6-v2 model
PROGRESS_LOG_INTERVAL = 500  # Log progress every N nodes
SOURCE_NAME = "schema.org"


class SchemaOrgImportError(Exception):
    """Base exception for Schema.org import errors."""



class DownloadError(SchemaOrgImportError):
    """Error during Schema.org data download."""



class ParseError(SchemaOrgImportError):
    """Error during JSON-LD parsing."""



class EmbeddingError(SchemaOrgImportError):
    """Error during embedding generation."""



class LockError(SchemaOrgImportError):
    """Error acquiring or managing lock file."""



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

    def __init__(
        self,
        config: ReferenceConfig,
        manager: ReferenceManager,
        stale_lock_threshold: int = DEFAULT_STALE_LOCK_THRESHOLD,
    ):
        """
        Initialize the Schema.org importer.

        Args:
            config: ReferenceConfig with operational parameters
            manager: ReferenceManager instance for database operations
            stale_lock_threshold: Time in seconds after which a lock file is considered stale
        """
        self.config = config
        self.manager = manager
        self.lock_path = f"{manager.db_path}.import.lock"
        self.stale_lock_threshold = stale_lock_threshold
        self.vec_table_created = False  # Track vec table creation state

        # Setup signal handlers for graceful lock cleanup
        import signal

        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle termination signals for graceful lock cleanup."""
        logger.info(f"Received signal {signum}, cleaning up...")
        self._release_lock()
        raise SystemExit(0)

    def import_schema_org(self, batch_size: int = DEFAULT_BATCH_SIZE) -> dict[str, Any]:
        """
        Execute the complete Schema.org import pipeline.

        This method implements the revised import workflow:
        1. Download and parse Schema.org JSON-LD
        2. Generate embeddings for all items (entities and properties)
        3. Insert Classes as ReferenceNodes with embeddings
        4. Insert Properties as ExternalPredicates with embeddings
        5. Create vec0 virtual table for ReferenceNodes
        6. Extract and insert metadata relationships as ReferenceLinks

        Args:
            batch_size: Number of items to process per batch (default: 200, max: 5000)

        Returns:
            Dict with import statistics and status

        Raises:
            LockError: If another import is in progress
            DownloadError: If download fails after retries
            ParseError: If JSON-LD parsing fails
            EmbeddingError: If embedding generation fails
            SchemaOrgImportError: For other import failures
            ValueError: If batch_size is invalid
        """
        # Validate batch size
        if not MIN_BATCH_SIZE <= batch_size <= MAX_BATCH_SIZE:
            raise ValueError(
                f"batch_size must be between {MIN_BATCH_SIZE} and {MAX_BATCH_SIZE}, "
                f"got {batch_size}"
            )

        logger.info("Starting Schema.org import pipeline")

        # Check and acquire lock
        self._acquire_lock()

        try:
            # Step 1: Download and parse
            logger.info("Step 1: Downloading and parsing Schema.org JSON-LD")
            json_data = self._download_with_retry()
            entities, properties = self._parse_jsonld(json_data)

            logger.info(
                f"Parsed {len(entities)} entities (Classes) and {len(properties)} properties"
            )

            # Step 2: Generate embeddings for entities
            logger.info("Step 2: Generating embeddings for entities")
            embedded_entities = self._generate_embeddings_batch(
                entities, batch_size=batch_size
            )

            # Step 3: Generate embeddings for properties
            logger.info("Step 3: Generating embeddings for properties")
            embedded_properties = self._generate_embeddings_batch(
                properties, batch_size=batch_size
            )

            # Step 4: Insert entities as ReferenceNodes with embeddings
            logger.info("Step 4: Inserting entities as ReferenceNodes")
            node_map = self._insert_nodes_transaction(embedded_entities)

            # Step 5: Insert properties as ExternalPredicates with embeddings
            logger.info("Step 5: Inserting properties as ExternalPredicates")
            predicate_map = self._insert_predicates_transaction(embedded_properties)

            # Step 6: Create and populate vec0 virtual table for ReferenceNodes
            logger.info("Step 6: Creating and populating vec0 virtual table")
            try:
                vec_success = self._create_vec_table()
                if not vec_success:
                    logger.warning(
                        "Operating in degraded mode: embeddings stored but not searchable "
                        "via vec tables. Install sqlite-vec extension for full functionality."
                    )
            except Exception as e:
                # Clean up vec table if creation failed partway
                logger.error(f"Vec table creation failed, cleaning up: {e}")
                self._cleanup_vec_table()
                # Re-raise to trigger full rollback
                raise

            # Step 7: Extract and insert metadata relationships
            logger.info("Step 7: Extracting and inserting metadata relationships")
            link_count = self._insert_relationships_transaction(
                entities, properties, node_map, predicate_map
            )

            result = {
                "success": True,
                "entities_imported": len(node_map),
                "properties_imported": len(predicate_map),
                "links_imported": link_count,
                "timestamp": datetime.now().isoformat(),
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
        Acquire import lock file to prevent concurrent imports using atomic file creation.

        Uses atomic file creation (open with 'x' mode) to prevent TOCTOU race conditions.
        If the lock file exists and is stale (older than stale_lock_threshold), it will
        be removed and acquisition will be retried.

        Raises:
            LockError: If lock cannot be acquired or stale lock detected
        """
        # Check for stale lock files
        if os.path.exists(self.lock_path):
            lock_age = time.time() - os.path.getmtime(self.lock_path)

            if lock_age > self.stale_lock_threshold:
                logger.warning(
                    f"Detected stale lock file (age: {lock_age/3600:.1f} hours, "
                    f"threshold: {self.stale_lock_threshold/3600:.1f} hours). "
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

        # Create lock file atomically using 'x' mode (exclusive creation)
        # This prevents race conditions between check and creation
        try:
            with open(self.lock_path, "x") as f:
                f.write(
                    json.dumps(
                        {"pid": os.getpid(), "timestamp": datetime.now().isoformat()}
                    )
                )
            logger.info(f"Acquired import lock: {self.lock_path}")
        except FileExistsError:
            # Another process created the file between our check and creation attempt
            raise LockError(
                f"Another import acquired the lock concurrently (lock file: {self.lock_path})"
            )
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
        # IMPORTANT: Security check - only HTTPS URLs allowed for remote sources
        # Exception: localhost/127.0.0.1 allowed for testing purposes
        # WARNING: Localhost exception could be exploited via DNS rebinding attacks
        # Mitigation: Ensure firewall rules prevent external access to localhost endpoints
        if not url.startswith("https://"):
            if not ("localhost" in url or "127.0.0.1" in url):
                raise DownloadError(
                    "Non-HTTPS URL rejected for security. "
                    "Only HTTPS URLs are allowed for remote sources."
                )

        logger.info(f"Downloading Schema.org data from {url}")

        last_error = None
        for attempt in range(retry_count):
            try:
                # Exponential backoff: 1s, 2s, 4s, ...
                if attempt > 0:
                    delay = 2 ** (attempt - 1)
                    logger.info(
                        f"Retry attempt {attempt + 1}/{retry_count} after {delay}s delay"
                    )
                    time.sleep(delay)

                response = requests.get(url, timeout=timeout)
                response.raise_for_status()

                # Write to temporary file
                tmp_file = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".jsonld", delete=False
                )
                tmp_file.write(response.text)
                tmp_file.close()

                logger.debug(
                    f"Downloaded {len(response.text)} bytes to {tmp_file.name}"
                )
                return tmp_file.name

            except requests.exceptions.Timeout as e:
                last_error = e
                # Log as debug on retryable attempts, warning on final failure
                log_level = (
                    logger.debug if attempt < retry_count - 1 else logger.warning
                )
                log_level(
                    f"Download attempt {attempt + 1}/{retry_count} failed with timeout "
                    f"({timeout}s): {e}"
                )
                if attempt == retry_count - 1:
                    raise DownloadError(
                        f"Failed to download after {retry_count} attempts (timeout): {e}"
                    )
            except requests.exceptions.RequestException as e:
                last_error = e
                # Log as debug on retryable attempts, warning on final failure
                log_level = (
                    logger.debug if attempt < retry_count - 1 else logger.warning
                )
                log_level(
                    f"Download attempt {attempt + 1}/{retry_count} failed with network error: {e}"
                )
                if attempt == retry_count - 1:
                    raise DownloadError(
                        f"Failed to download after {retry_count} attempts: {e}"
                    )
            except Exception as e:
                last_error = e
                # Log as debug on retryable attempts, warning on final failure
                log_level = (
                    logger.debug if attempt < retry_count - 1 else logger.warning
                )
                log_level(f"Download attempt {attempt + 1}/{retry_count} failed: {e}")
                if attempt == retry_count - 1:
                    raise DownloadError(
                        f"Failed to download after {retry_count} attempts: {e}"
                    )

        # This should not be reached due to exceptions, but as a safety net
        raise DownloadError(f"Download failed: {last_error}")

    def _parse_jsonld(self, file_path: str) -> tuple[list[dict], list[dict]]:
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
            with open(file_path, "r", encoding="utf-8") as f:
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
                if any(
                    k in item
                    for k in [
                        "domainIncludes",
                        "rangeIncludes",
                        "schema:domainIncludes",
                        "schema:rangeIncludes",
                    ]
                ):
                    properties.append(item)
                else:
                    entities.append(item)

        logger.info(f"Parsed {len(entities)} entities and {len(properties)} properties")
        return entities, properties

    def _generate_embeddings_batch(
        self, items: list[dict], batch_size: int = DEFAULT_BATCH_SIZE
    ) -> list[dict[str, Any]]:
        """
        Generate embeddings for a list of Schema.org items.

        This method processes items in configurable batches and generates
        separate embeddings for title and definition fields. Validates embedding
        dimensions and provides progress logging.

        Args:
            items: List of Schema.org items (entities or properties)
            batch_size: Number of items to process per batch

        Returns:
            List of dictionaries with item data and embeddings

        Raises:
            EmbeddingError: If embedding generation fails or returns invalid dimensions
        """
        embedded_items = []
        failed_items = []
        items_processed = 0

        for i in range(0, len(items), batch_size):
            batch = items[i : i + batch_size]
            logger.info(
                f"Processing batch {i//batch_size + 1} ({i+1}-{i+len(batch)}/{len(items)})"
            )

            for item in batch:
                try:
                    # Extract fields
                    external_id = item.get("@id", "")

                    # Extract title - handle both string and JSON-LD object format
                    title_raw = (
                        item.get("rdfs:label")
                        or item.get("label")
                        or item.get("name")
                        or ""
                    )
                    if isinstance(title_raw, dict):
                        # JSON-LD object with @value
                        title = title_raw.get("@value", str(title_raw))
                    elif isinstance(title_raw, list):
                        # Multiple values - take the first string
                        title = next(
                            (
                                t.get("@value", t) if isinstance(t, dict) else t
                                for t in title_raw
                            ),
                            "",
                        )
                    else:
                        title = str(title_raw) if title_raw else ""

                    # Extract definition - handle both string and JSON-LD object format
                    definition_raw = (
                        item.get("rdfs:comment")
                        or item.get("comment")
                        or item.get("description")
                        or ""
                    )
                    if isinstance(definition_raw, dict):
                        # JSON-LD object with @value
                        definition = definition_raw.get("@value", str(definition_raw))
                    elif isinstance(definition_raw, list):
                        # Multiple values - take the first string
                        definition = next(
                            (
                                d.get("@value", d) if isinstance(d, dict) else d
                                for d in definition_raw
                            ),
                            "",
                        )
                    else:
                        definition = str(definition_raw) if definition_raw else ""

                    # Generate embeddings separately for title and definition
                    title_embedding = None
                    definition_embedding = None

                    if title:
                        title_embedding = generate_embedding(title)
                        # Validate embedding dimensions
                        if title_embedding:
                            actual_dims = len(title_embedding) // 4  # float32 = 4 bytes
                            if actual_dims != DEFAULT_EMBEDDING_DIMS:
                                raise EmbeddingError(
                                    f"Title embedding dimension mismatch: expected {DEFAULT_EMBEDDING_DIMS}, "
                                    f"got {actual_dims} for '{title}'"
                                )

                    if definition:
                        definition_embedding = generate_embedding(definition)
                        # Validate embedding dimensions
                        if definition_embedding:
                            actual_dims = (
                                len(definition_embedding) // 4
                            )  # float32 = 4 bytes
                            if actual_dims != DEFAULT_EMBEDDING_DIMS:
                                raise EmbeddingError(
                                    f"Definition embedding dimension mismatch: expected {DEFAULT_EMBEDDING_DIMS}, "
                                    f"got {actual_dims} for '{definition[:50]}...'"
                                )

                    embedded_items.append(
                        {
                            "external_id": external_id,
                            "title": title,
                            "definition": definition,
                            "title_embedding": title_embedding,
                            "definition_embedding": definition_embedding,
                            "raw_data": item,
                        }
                    )

                    # Progress logging
                    items_processed += 1
                    if items_processed % PROGRESS_LOG_INTERVAL == 0:
                        logger.info(
                            f"Progress: {items_processed}/{len(items)} items processed"
                        )

                except Exception as e:
                    logger.error(
                        "Embedding generation failed",
                        extra={
                            "external_id": item.get("@id", "unknown"),
                            "error": str(e),
                        },
                    )
                    failed_items.append(item.get("@id", "unknown"))

        # Fail-fast behavior (TC-I001)
        if failed_items:
            logger.error(
                "Embedding generation failed",
                extra={"failed_count": len(failed_items), "failed_ids": failed_items},
            )
            raise EmbeddingError(
                f"Embedding generation failed for {len(failed_items)} items: "
                f"{', '.join(failed_items)}"
            )

        logger.info(f"Generated embeddings for {len(embedded_items)} items")
        return embedded_items

    def _insert_nodes_transaction(
        self, embedded_nodes: list[dict[str, Any]]
    ) -> dict[str, str]:
        """
        Insert Schema.org Classes as ReferenceNodes with embeddings in a single transaction.

        This method uses transaction boundaries to ensure atomicity.
        If any insert fails, the entire transaction is rolled back.

        Args:
            embedded_nodes: List of entity (Class) items with embeddings

        Returns:
            Dict mapping external_id to node UUID

        Raises:
            SchemaOrgImportError: If transaction fails
        """
        node_map = {}
        nodes_inserted = 0

        try:
            # Clear any existing nodes from this source for idempotency
            self.manager.session.query(ReferenceNode).filter_by(
                source=SOURCE_NAME
            ).delete()
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
                        updated_at=datetime.now().isoformat(),
                    )

                    self.manager.session.add(node)
                    node_map[node_data["external_id"]] = node.id

                    # Progress logging
                    nodes_inserted += 1
                    if nodes_inserted % PROGRESS_LOG_INTERVAL == 0:
                        logger.info(
                            f"Progress: {nodes_inserted}/{len(embedded_nodes)} nodes inserted"
                        )

            # Commit transaction
            self.manager.session.commit()
            logger.info(f"Inserted {len(node_map)} nodes in transaction")

        except SQLAlchemyError as e:
            logger.error(f"Transaction failed, rolling back: {e}")
            self.manager.session.rollback()
            raise SchemaOrgImportError(f"Node insertion failed: {e}")

        return node_map

    def _insert_predicates_transaction(
        self, embedded_predicates: list[dict[str, Any]]
    ) -> dict[str, str]:
        """
        Insert Schema.org Properties as ExternalPredicates with embeddings in a single transaction.

        This method uses transaction boundaries to ensure atomicity.
        If any insert fails, the entire transaction is rolled back.

        Args:
            embedded_predicates: List of property (rdf:Property) items with embeddings

        Returns:
            Dict mapping external_id to predicate UUID

        Raises:
            SchemaOrgImportError: If transaction fails
        """
        predicate_map = {}
        predicates_inserted = 0

        try:
            # Clear any existing predicates from this source for idempotency
            self.manager.session.query(ExternalPredicate).filter_by(
                source=SOURCE_NAME
            ).delete()
            self.manager.session.commit()

            # Start transaction for new predicates
            with self.manager.session.begin_nested():
                for predicate_data in embedded_predicates:
                    predicate = ExternalPredicate(
                        id=str(uuid4()),
                        title=predicate_data["title"],
                        definition=predicate_data["definition"],
                        source=SOURCE_NAME,
                        external_id=predicate_data["external_id"],
                        attributes=json.dumps(predicate_data["raw_data"]),
                        title_embedding=predicate_data["title_embedding"],
                        definition_embedding=predicate_data["definition_embedding"],
                        created_at=datetime.now().isoformat(),
                        updated_at=datetime.now().isoformat(),
                    )

                    self.manager.session.add(predicate)
                    predicate_map[predicate_data["external_id"]] = predicate.id

                    # Progress logging
                    predicates_inserted += 1
                    if predicates_inserted % PROGRESS_LOG_INTERVAL == 0:
                        logger.info(
                            f"Progress: {predicates_inserted}/{len(embedded_predicates)} predicates inserted"
                        )

            # Commit transaction
            self.manager.session.commit()
            logger.info(f"Inserted {len(predicate_map)} predicates in transaction")

        except SQLAlchemyError as e:
            logger.error(f"Transaction failed, rolling back: {e}")
            self.manager.session.rollback()
            raise SchemaOrgImportError(f"Predicate insertion failed: {e}")

        return predicate_map

    def _create_vec_table(self) -> bool:
        """
        Create vec0 virtual table and populate via INSERT...SELECT (Phase 4).

        This method implements atomic vector table creation and population
        as specified in the 5-step workflow.

        Returns:
            bool: True if vec table was created successfully, False if skipped

        Note:
            If sqlite-vec extension is not available, this step is skipped and False is returned.
            The embeddings are still stored in the reference_nodes table as BLOB columns.
            Callers should check the return value to determine if full functionality is available.
        """
        try:
            # Check if sqlite-vec extension is available
            try:
                self.manager.session.execute(text("SELECT vec_version()")).fetchone()
            except Exception:
                logger.warning(
                    "sqlite-vec extension not available, skipping vec table creation. "
                    "Embeddings are still stored in reference_nodes table."
                )
                self.vec_table_created = False
                return False

            # Determine embedding dimensions from first non-null embedding
            result = self.manager.session.execute(text("""
                    SELECT title_embedding
                    FROM reference_nodes
                    WHERE title_embedding IS NOT NULL
                    LIMIT 1
                """)).fetchone()

            if not result or not result[0]:
                logger.warning("No embeddings found, skipping vec table creation")
                self.vec_table_created = False
                return False

            # Calculate dimensions (float32 = 4 bytes per dimension)
            embedding_bytes = result[0]
            dims = len(embedding_bytes) // 4

            logger.info(f"Creating vec0 table with {dims} dimensions")

            # Drop existing vec table if it exists
            self.manager.session.execute(
                text("DROP TABLE IF EXISTS reference_nodes_vec")
            )

            # Create vec0 virtual table with two embedding columns
            # Column naming: title_embedding and definition_embedding maintain consistency
            # with the source table column names for semantic clarity
            self.manager.session.execute(text(f"""
                    CREATE VIRTUAL TABLE reference_nodes_vec
                    USING vec0(
                        id TEXT PRIMARY KEY,
                        title_embedding FLOAT[{dims}],
                        definition_embedding FLOAT[{dims}]
                    )
                """))

            # Populate vec table via INSERT...SELECT (atomic operation)
            self.manager.session.execute(
                text("""
                    INSERT INTO reference_nodes_vec (id, title_embedding, definition_embedding)
                    SELECT id, title_embedding, definition_embedding
                    FROM reference_nodes
                    WHERE source = :source
                """),
                {"source": SOURCE_NAME},
            )

            self.manager.session.commit()
            logger.info("Vec0 table created and populated successfully")
            self.vec_table_created = True
            return True

        except SQLAlchemyError as e:
            error_msg = str(e)
            # If it's just a vec extension issue, log warning and continue
            if "vec" in error_msg.lower() or "extension" in error_msg.lower():
                logger.warning(f"Vec table creation skipped (extension issue): {e}")
                try:
                    self.manager.session.rollback()
                except Exception:
                    pass
                self.vec_table_created = False
                return False
            else:
                # Other SQLAlchemy errors should fail
                logger.error(f"Vec table creation failed: {e}")
                self.manager.session.rollback()
                raise SchemaOrgImportError(f"Vec table creation failed: {e}")

    def _cleanup_vec_table(self):
        """
        Clean up orphaned vec table in case of partial creation failure.

        This method is called when vec table creation fails partway through,
        ensuring no orphaned tables are left behind.
        """
        if not self.vec_table_created:
            return

        try:
            logger.info("Cleaning up vec table after failed import")
            self.manager.session.execute(
                text("DROP TABLE IF EXISTS reference_nodes_vec")
            )
            self.manager.session.commit()
            self.vec_table_created = False
            logger.info("Vec table cleanup complete")
        except Exception as e:
            logger.warning(f"Failed to clean up vec table: {e}")
            # Don't raise - this is a best-effort cleanup

    def _insert_relationships_transaction(
        self,
        entities: list[dict],
        properties: list[dict],
        node_map: dict[str, str],
        predicate_map: dict[str, str],
    ) -> int:
        """
        Extract and insert Schema.org metadata relationships in separate transaction.

        Extracts the following relationship types:
        - subClassOf: Entity inheritance relationships (Class -> Class)
        - domainIncludes: Property domain constraints (Property -> Class)
        - rangeIncludes: Property range constraints (Property -> Class)
        - inverseOf: Inverse property relationships (Property -> Property)

        Note: These are metadata relationships that describe the schema structure,
        not the actual relationships that the properties represent.

        Args:
            entities: List of Schema.org entity (Class) items
            properties: List of Schema.org property (rdf:Property) items
            node_map: Mapping of entity external_id to ReferenceNode UUID
            predicate_map: Mapping of property external_id to ExternalPredicate UUID

        Returns:
            Number of links inserted

        Raises:
            SchemaOrgImportError: If transaction fails
        """
        links_to_insert = []

        # Note: Currently we can only create ReferenceLinks between ReferenceNodes,
        # so property metadata relationships (domainIncludes, rangeIncludes, inverseOf)
        # will be stored in the ExternalPredicate.attributes field rather than as links.
        # Only subClassOf relationships between entities will be stored as ReferenceLinks.

        # Extract relationships for entities only (subClassOf)
        for item in entities:
            external_id = item.get("@id", "")
            subject_id = node_map.get(external_id)

            if not subject_id:
                continue

            # Extract subClassOf (Class -> Class relationships)
            subclass_of = item.get("rdfs:subClassOf") or item.get("subClassOf")
            if subclass_of:
                if isinstance(subclass_of, list):
                    for parent in subclass_of:
                        parent_id = self._extract_id(parent)
                        if parent_id and parent_id in node_map:
                            links_to_insert.append(
                                {
                                    "subject": subject_id,
                                    "predicate": "subClassOf",
                                    "object": node_map[parent_id],
                                    "metadata": {
                                        "source": "schema.org",
                                        "type": "class_hierarchy",
                                    },
                                }
                            )
                else:
                    parent_id = self._extract_id(subclass_of)
                    if parent_id and parent_id in node_map:
                        links_to_insert.append(
                            {
                                "subject": subject_id,
                                "predicate": "subClassOf",
                                "object": node_map[parent_id],
                                "metadata": {
                                    "source": "schema.org",
                                    "type": "class_hierarchy",
                                },
                            }
                        )

        # Note: Property relationships (domainIncludes, rangeIncludes, inverseOf)
        # are already stored in the ExternalPredicate.attributes field as part of the raw_data.
        # We skip creating ReferenceLinks for these since:
        # 1. ReferenceLinks are designed to connect ReferenceNodes, not ExternalPredicates
        # 2. The property metadata is preserved in the attributes field
        # 3. A future refactoring could add support for predicate-to-predicate links if needed

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
                        updated_at=datetime.now().isoformat(),
                    )
                    self.manager.session.add(link)

            self.manager.session.commit()
            logger.info(f"Inserted {len(links_to_insert)} relationship links")

        except SQLAlchemyError as e:
            logger.error(f"Link insertion failed, rolling back: {e}")
            self.manager.session.rollback()
            raise SchemaOrgImportError(f"Link insertion failed: {e}")

        return len(links_to_insert)

    def _extract_id(self, value: Any) -> str | None:
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
