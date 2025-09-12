"""
Manager responsible for downloading, parsing and populating a local schema.org sqlite database.

This is a scaffold: methods log and provide clear TODOs for implementation.
"""

import os
import shutil
import tempfile
import threading
import json
from typing import List, Tuple, Any, Dict, Optional
from sqlalchemy import text
from database.utils import init_db, get_engine as utils_get_engine, get_session_local as utils_get_session_local
from utils.logger import get_logger
from config import get_settings
from .models import Base, SchemaOrgEntity, SchemaOrgProperty
from embeddings.generate_embeddings import generate_embedding
import numpy as np
from .errors import DownloadError, ParseError, BackupError, RestoreError, DatabaseError, EmbeddingError

logger = get_logger(__name__)


class SchemaOrgManager:
    """Handles lifecycle of the schema.org database (download, populate, refresh).

    This scaffold provides method signatures and minimal behavior. Implementations
    should follow the design in documentation/requirements/08.2_schema_org_design.md.
    """

    def __init__(self, db_path: str = None):
        settings = get_settings()
        self.db_path = db_path or settings.SCHEMA_ORG_DB_PATH
        self.backup_path = f"{self.db_path}.backup"
        self.source_url = settings.SCHEMA_ORG_SOURCE_URL
        self.engine = None
        self._session_local = None
        self._lock = threading.Lock()

    def get_engine(self):
        """Return an SQLAlchemy engine for the schema.org database (lazy).

        Note: caller is responsible for disposing engine when appropriate.
        """
        if self.engine is None:
            # Build a base engine using the project's get_engine helper so
            # connection creation honors the repository's connect args.
            database_url = f"sqlite:///{os.path.abspath(self.db_path)}"
            base_engine = utils_get_engine(database_url=database_url)
            # Attach project-specific listeners (loads sqlite-vec) via init_db
            self.engine = init_db(engine=base_engine)
        return self.engine

    def get_session_local(self):
        """Return a sessionmaker bound to the schema.org engine."""
        if self._session_local is None:
            engine = self.get_engine()
            # Use the repository helper so sessionmaker settings stay consistent
            self._session_local = utils_get_session_local(engine)
        return self._session_local

    def initialize(self) -> bool:
        """Ensure database exists and is populated (if configured to auto-populate).

        This method should perform a non-blocking or background population when
        invoked during application startup.
        """
        logger.info("SchemaOrgManager.initialize called")
        engine = self.get_engine()
        # Create tables if they do not exist
        try:
            Base.metadata.create_all(engine)
        except Exception as e:
            logger.exception("Failed to create schema.org tables: %s", e)
            return False

        # If auto-initialize is enabled and DB not populated, start background refresh
        settings = get_settings()
        try:
            if settings.SCHEMA_ORG_AUTO_INITIALIZE and not self.is_populated():
                logger.info("Schema.org DB not populated, starting background population")
                thread = threading.Thread(target=self.refresh_data, kwargs={"force": False})
                thread.daemon = True
                thread.start()
        except Exception:
            logger.exception("Error checking auto-initialize status")

        return True

    def is_populated(self) -> bool:
        """Return True if the database contains schema.org data."""
        try:
            engine = self.get_engine()
            with engine.connect() as conn:
                # Check for the entities table and at least one row
                result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_org_entities'"),).fetchone()
                if not result:
                    return False
                count = conn.execute(text("SELECT COUNT(*) FROM schema_org_entities")).scalar()
                return bool(count and int(count) > 0)
        except Exception as e:
            logger.debug("is_populated check failed: %s", e)
            return False

    def get_status(self) -> Dict[str, Any]:
        """Return basic status information about the schema.org DB."""
        status: Dict[str, Any] = {"is_populated": False, "entity_count": 0, "property_count": 0, "last_updated": None, "database_size": None}
        try:
            engine = self.get_engine()
            db_path = os.path.abspath(self.db_path)
            if os.path.exists(db_path):
                status["database_size"] = os.path.getsize(db_path)
                status["last_updated"] = os.path.getmtime(db_path)

            with engine.connect() as conn:
                # If tables exist, get counts
                tbl = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_org_entities'")).fetchone()
                if tbl:
                    status["entity_count"] = int(conn.execute(text("SELECT COUNT(*) FROM schema_org_entities")).scalar() or 0)
                tblp = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_org_properties'")).fetchone()
                if tblp:
                    status["property_count"] = int(conn.execute(text("SELECT COUNT(*) FROM schema_org_properties")).scalar() or 0)

            status["is_populated"] = bool(status["entity_count"] or status["property_count"])
        except Exception as e:
            logger.debug("get_status failed: %s", e)
        return status

    def refresh_data(self, force: bool = False) -> Dict[str, Any]:
        """Refresh the local schema.org database with backup and validation.

        Returns a dict with success flag and diagnostic info.
        """
        logger.info("refresh_data called (force=%s)", force)
        result = {"success": False, "backup_created": False, "message": ""}

        with self._lock:
            logger.debug("Acquired lock for refresh_data")
            # Step 1: create backup
            try:
                backup_created = self._create_backup()
                result["backup_created"] = backup_created
            except BackupError as e:
                logger.exception("Backup creation failed: %s", e)
                result["message"] = f"backup_failed: {e}"
                return result
            except Exception as e:
                logger.exception("Unexpected error creating backup: %s", e)
                result["message"] = f"backup_failed: {e}"
                return result

            # If a database already exists, require a successful backup before proceeding
            if os.path.exists(self.db_path) and not result["backup_created"]:
                logger.error("Existing DB present but backup creation failed; aborting refresh")
                result["message"] = "backup_required_failed"
                return result

            # Step 2: download
            tmp_path = None
            try:
                tmp_path = self._download_schema_org()
                if not tmp_path:
                    raise DownloadError("Download returned empty path")
            except DownloadError as e:
                logger.exception("Download failed: %s", e)
                result["message"] = f"download_failed: {e}"
                # attempt restore; raise if restore fails
                try:
                    self._restore_from_backup()
                except RestoreError:
                    logger.exception("Restore after download failure failed")
                return result
            except Exception as e:
                logger.exception("Unexpected download error: %s", e)
                result["message"] = f"download_failed: {e}"
                try:
                    self._restore_from_backup()
                except RestoreError:
                    logger.exception("Restore after download failure failed")
                return result

            # Step 3: parse
            try:
                entities, properties = self._parse_jsonld(tmp_path)
            except ParseError as e:
                logger.exception("Parsing failed: %s", e)
                result["message"] = f"parse_failed: {e}"
                try:
                    self._restore_from_backup()
                except RestoreError:
                    logger.exception("Restore after parse failure failed")
                return result
            except Exception as e:
                logger.exception("Unexpected parse error: %s", e)
                result["message"] = f"parse_failed: {e}"
                try:
                    self._restore_from_backup()
                except RestoreError:
                    logger.exception("Restore after parse failure failed")
                return result

            # Step 4: populate database
            try:
                engine = self.get_engine()
                Base.metadata.create_all(engine)
                self._populate_database(entities, properties)
                result["success"] = True
                result["message"] = "populated"
            except DatabaseError as e:
                # If the failure is due to sqlite-vec failing to load, re-raise
                # so callers/tests fail fast and CI surfaces the native load error.
                if "failed_to_load_sqlite_vec" in str(e):
                    logger.exception("Critical population failure (sqlite_vec): %s", e)
                    raise
                logger.exception("Population failed: %s", e)
                result["message"] = f"populate_failed: {e}"
                try:
                    self._restore_from_backup()
                except RestoreError:
                    logger.exception("Restore after population failure failed")
                result["success"] = False
            except Exception as e:
                logger.exception("Unexpected population error: %s", e)
                result["message"] = f"populate_failed: {e}"
                try:
                    self._restore_from_backup()
                except RestoreError:
                    logger.exception("Restore after population failure failed")
                result["success"] = False
            finally:
                # cleanup temporary file
                try:
                    if tmp_path and os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except Exception:
                    pass

        return result

    def _create_backup(self) -> bool:
        """Create a filesystem backup of the existing database file.

        Returns True when backup created successfully.
        """
        logger.info("Creating schema.org DB backup from %s to %s", self.db_path, self.backup_path)
        try:
            if os.path.exists(self.db_path):
                try:
                    shutil.copy2(self.db_path, self.backup_path)
                except PermissionError as e:
                    logger.exception("Permission denied creating backup: %s", e)
                    raise BackupError("permission_denied")
                except OSError as e:
                    logger.exception("OS error creating backup: %s", e)
                    raise BackupError(str(e))
                logger.info("Backup created successfully")
                return True
            logger.info("No existing database file to backup")
            return False
        except BackupError:
            raise
        except Exception as e:
            logger.exception("Failed to create backup: %s", e)
            raise BackupError(str(e))

    def _restore_from_backup(self) -> bool:
        """Restore the database from the backup file. Returns True on success."""
        logger.info("Restoring schema.org DB from backup %s", self.backup_path)
        try:
            if os.path.exists(self.backup_path):
                try:
                    shutil.copy2(self.backup_path, self.db_path)
                except PermissionError as e:
                    logger.exception("Permission denied during restore: %s", e)
                    raise RestoreError("permission_denied")
                except OSError as e:
                    logger.exception("OS error during restore: %s", e)
                    raise RestoreError(str(e))
                logger.info("Restore completed successfully")
                return True
            logger.warning("No backup file found to restore")
            raise RestoreError("no_backup")
        except RestoreError:
            raise
        except Exception as e:
            logger.exception("Failed to restore from backup: %s", e)
            raise RestoreError(str(e))

    def _download_schema_org(self) -> str:
        """Download schema.org JSON-LD file and return path to temporary file.

        This scaffold returns an empty string. Implementers should download to a
        temp file and return its path.
        """
        logger.info("Starting schema.org download from %s", self.source_url)
        import requests

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jsonld")
        tmp_path = tmp.name
        tmp.close()

        try:
            with requests.get(self.source_url, stream=True, timeout=60) as r:
                try:
                    r.raise_for_status()
                except requests.HTTPError as e:
                    logger.exception("HTTP error downloading schema.org: %s", e)
                    raise DownloadError("http_error", http_status=getattr(e.response, 'status_code', None))
                total = int(r.headers.get("Content-Length", 0) or 0)
                downloaded = 0
                chunk_size = 8192
                with open(tmp_path, "wb") as fh:
                    for chunk in r.iter_content(chunk_size=chunk_size):
                        if not chunk:
                            continue
                        fh.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            pct = downloaded / total * 100
                            logger.info("Downloading schema.org: %.1f%% (%d/%d)", pct, downloaded, total)
                        else:
                            logger.info("Downloading schema.org: %d bytes", downloaded)
        except DownloadError:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            raise
        except requests.RequestException as e:
            logger.exception("Network error during download: %s", e)
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            raise DownloadError(str(e))
        except Exception as e:
            logger.exception("Unexpected error during download: %s", e)
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            raise DownloadError(str(e))

        logger.info("Download complete: %s", tmp_path)
        return tmp_path

    def _parse_jsonld(self, file_path: str) -> Tuple[List[dict], List[dict]]:
        """Parse JSON-LD into (entities, properties).

        Returns two lists of dicts. This scaffold returns empty lists.
        """
        logger.info("Parsing JSON-LD file %s", file_path)
        try:
            with open(file_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError as e:
            logger.exception("Invalid JSON-LD file: %s", e)
            raise ParseError(f"invalid_json: {e}")
        except Exception as e:
            logger.exception("Failed to read JSON-LD file: %s", e)
            raise ParseError(str(e))

    # schema.org JSON-LD typically has an '@graph' key with items
        items = []
        if isinstance(data, dict) and "@graph" in data:
            items = data["@graph"]
        elif isinstance(data, list):
            items = data
        elif isinstance(data, dict) and "@context" in data and isinstance(data.get("mainEntity"), list):
            items = data.get("mainEntity", [])
        else:
            # Fallback: try to find a list inside
            for v in data.values():
                if isinstance(v, list):
                    items = v
                    break

        entities: List[dict] = []
        properties: List[dict] = []

        def _get_types(obj):
            t = obj.get("@type") or obj.get("type")
            if t is None:
                return []
            if isinstance(t, list):
                return t
            return [t]

        def _extract_label(obj):
            return obj.get("label") or obj.get("rdfs:label") or obj.get("http://www.w3.org/2000/01/rdf-schema#label")

        def _extract_comment(obj):
            return obj.get("comment") or obj.get("rdfs:comment") or obj.get("http://www.w3.org/2000/01/rdf-schema#comment")

        for obj in items:
            types = [str(x) for x in _get_types(obj)]
            if any("Class" in t or "rdfs:Class" in t for t in types):
                entities.append(obj)
            elif any("Property" in t or "rdf:Property" in t for t in types):
                properties.append(obj)
            else:
                # Heuristic: properties often have domainIncludes/rangeIncludes
                if any(k in obj for k in ("domainIncludes", "rangeIncludes", "schema:domainIncludes", "schema:rangeIncludes")):
                    properties.append(obj)
                else:
                    entities.append(obj)

        logger.info("Parsed JSON-LD: %d entities, %d properties", len(entities), len(properties))
        # Validate we have at least some items to ingest
        if not (entities or properties):
            logger.error("Parsed JSON-LD contains no entities or properties")
            raise ParseError("no_items_parsed")
        return entities, properties

    def _populate_database(self, entities: List[dict], properties: List[dict]) -> None:
        """Populate the schema.org sqlite database with provided data.

        Should generate embeddings in batches and insert records efficiently.
        """
        logger.info("Populating database: %d entities, %d properties", len(entities), len(properties))
        SessionLocal = self.get_session_local()
        session = SessionLocal()
        try:
            # Clear existing rows to ensure refresh replaces data (prevents UNIQUE constraint on re-run)
            try:
                logger.info("Clearing existing schema_org tables before population")
                session.query(SchemaOrgProperty).delete()
                session.query(SchemaOrgEntity).delete()
                session.commit()
            except Exception:
                session.rollback()
                logger.debug("Failed to clear existing schema_org tables; continuing to populate")
            # Clear existing tables if force-populate behavior desired? For now, upsert by identifier
            # Insert properties in batches
            batch_size = 200
            # Helper to normalize fields
            def _get_identifier(o):
                return o.get("@id") or o.get("id")

            def _get_title(o):
                return o.get("label") or o.get("rdfs:label") or o.get("name")

            def _get_definition(o):
                return o.get("comment") or o.get("rdfs:comment") or o.get("description")

            # Insert properties in batches, generating embeddings in batch
            total_props = len(properties)
            for i in range(0, total_props, batch_size):
                batch = properties[i : i + batch_size]
                # Prepare minimal metadata for embedding generation
                items_for_embed = []
                id_to_raw = {}
                for p in batch:
                    identifier = _get_identifier(p)
                    if not identifier:
                        continue
                    title = _get_title(p) or ""
                    definition = _get_definition(p) or None
                    items_for_embed.append({"identifier": identifier, "title": title, "definition": definition})
                    id_to_raw[identifier] = p

                try:
                    embeddings = self._generate_embeddings_batch(items_for_embed, "properties")
                except EmbeddingError as e:
                    logger.exception("Embedding generation failed for properties: %s", e)
                    raise DatabaseError("embeddings_failed")

                objs = []
                for item in items_for_embed:
                    identifier = item["identifier"]
                    title = item["title"]
                    definition = item["definition"]
                    raw = id_to_raw.get(identifier)
                    title_emb, def_emb = embeddings.get(identifier, (None, None))
                    prop = SchemaOrgProperty(
                        identifier=identifier,
                        title=title,
                        definition=definition,
                        contributors=raw.get("contributor") or raw.get("schema:contributor"),
                        domain_includes=raw.get("domainIncludes") or raw.get("schema:domainIncludes"),
                        range_includes=raw.get("rangeIncludes") or raw.get("schema:rangeIncludes"),
                        inverse_of=raw.get("inverseOf"),
                        raw=raw,
                        title_embedding=title_emb,
                        definition_embedding=def_emb,
                    )
                    objs.append(prop)
                if objs:
                    try:
                        session.bulk_save_objects(objs)
                        session.commit()
                    except Exception as e:
                        logger.exception("Failed to insert property batch: %s", e)
                        session.rollback()
                        raise DatabaseError(str(e))

            # Insert entities
            # Insert entities in batches, generating embeddings in batch
            total_entities = len(entities)
            for i in range(0, total_entities, batch_size):
                batch = entities[i : i + batch_size]
                items_for_embed = []
                id_to_raw = {}
                for e in batch:
                    identifier = _get_identifier(e)
                    if not identifier:
                        continue
                    title = _get_title(e) or ""
                    definition = _get_definition(e) or None
                    items_for_embed.append({"identifier": identifier, "title": title, "definition": definition, "parent_identifier": e.get("rdfs:subClassOf") or e.get("subClassOf") or None})
                    id_to_raw[identifier] = e

                try:
                    embeddings = self._generate_embeddings_batch(items_for_embed, "entities")
                except EmbeddingError as e:
                    logger.exception("Embedding generation failed for entities: %s", e)
                    raise DatabaseError("embeddings_failed")

                objs = []
                for item in items_for_embed:
                    identifier = item["identifier"]
                    title = item["title"]
                    definition = item["definition"]
                    parent_identifier = item.get("parent_identifier")
                    raw = id_to_raw.get(identifier)
                    title_emb, def_emb = embeddings.get(identifier, (None, None))
                    ent = SchemaOrgEntity(
                        identifier=identifier,
                        title=title,
                        definition=definition,
                        parent_identifier=parent_identifier,
                        raw=raw,
                        title_embedding=title_emb,
                        definition_embedding=def_emb,
                    )
                    objs.append(ent)
                if objs:
                    try:
                        session.bulk_save_objects(objs)
                        session.commit()
                    except Exception as e:
                        logger.exception("Failed to insert entity batch: %s", e)
                        session.rollback()
                        raise DatabaseError(str(e))

            # Resolve parent_id relationships (one pass)
            try:
                all_entities = session.execute(text("SELECT id, identifier, parent_identifier FROM schema_org_entities")).fetchall()
                id_by_identifier = {row[1]: row[0] for row in all_entities}
                for row in all_entities:
                    eid, identifier, parent_identifier = row
                    if parent_identifier:
                        # parent_identifier may be dict or string
                        if isinstance(parent_identifier, dict):
                            pid = parent_identifier.get("@id")
                        else:
                            pid = parent_identifier
                        parent_id = id_by_identifier.get(pid)
                        if parent_id:
                            session.execute(
                                text("UPDATE schema_org_entities SET parent_id = :parent_id WHERE id = :id"),
                                {"parent_id": parent_id, "id": eid},
                            )
                session.commit()
            except Exception as e:
                logger.exception("Failed to resolve parent relationships: %s", e)
                # parent resolution failure is non-fatal, but log and continue

        finally:
            session.close()
        logger.info("Database population complete")
        # Create indexes and FTS5 virtual tables for faster text search
        try:
            with self.get_engine().connect() as conn:
                logger.info("Creating indexes and FTS5 tables for schema.org search")
                # Indexes - use exec_driver_sql for raw DDL
                try:
                    conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_schema_org_entities_identifier ON schema_org_entities(identifier)")
                    conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_schema_org_entities_title ON schema_org_entities(title)")
                    conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_schema_org_properties_identifier ON schema_org_properties(identifier)")
                    conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_schema_org_properties_title ON schema_org_properties(title)")
                except Exception:
                    logger.exception("Failed to create indexes; continuing")

                # FTS5 virtual tables (simple copy of title/definition for fast text queries)
                try:
                    conn.exec_driver_sql("CREATE VIRTUAL TABLE IF NOT EXISTS schema_org_entities_fts USING fts5(identifier, title, definition)")
                    conn.exec_driver_sql("CREATE VIRTUAL TABLE IF NOT EXISTS schema_org_properties_fts USING fts5(identifier, title, definition)")
                    # Populate FTS tables
                    conn.exec_driver_sql("INSERT INTO schema_org_entities_fts(identifier, title, definition) SELECT identifier, title, definition FROM schema_org_entities")
                    conn.exec_driver_sql("INSERT INTO schema_org_properties_fts(identifier, title, definition) SELECT identifier, title, definition FROM schema_org_properties")
                except Exception:
                    # FTS5 may not be available in all SQLite builds; log and continue
                    logger.exception("Failed to create/populate FTS5 tables; continuing without FTS5")

                # Create sqlite-vec virtual tables and populate from stored embeddings when present.
                # Use a raw DB-API connection to explicitly load the sqlite_vec extension into
                # the very connection used to create the virtual tables. This ensures the
                # extension is available for the DDL and the virtual tables are created
                # in a connection that supports vec0.
                try:
                    # Determine embedding dimension from first non-null stored embedding
                    ent_row = conn.execute(text("SELECT title_embedding FROM schema_org_entities WHERE title_embedding IS NOT NULL LIMIT 1")).fetchone()
                    prop_row = conn.execute(text("SELECT title_embedding FROM schema_org_properties WHERE title_embedding IS NOT NULL LIMIT 1")).fetchone()

                    ent_dim = None
                    prop_dim = None
                    if ent_row and ent_row[0]:
                        try:
                            ent_dim = int(np.frombuffer(ent_row[0], dtype=np.float32).size)
                        except Exception:
                            ent_dim = None
                    if prop_row and prop_row[0]:
                        try:
                            prop_dim = int(np.frombuffer(prop_row[0], dtype=np.float32).size)
                        except Exception:
                            prop_dim = None

                    # The sqlite_vec extension is automatically loaded by database/utils.py event listeners
                    # when the engine is initialized. We just need to create the vec virtual tables.
                    def _create_and_populate(table_name, dim, main_table):
                        if dim is None:
                            return
                        logger.info("Creating vec virtual table %s with dim=%s", table_name, dim)
                        try:
                            create_sql = f"CREATE VIRTUAL TABLE IF NOT EXISTS {table_name} USING vec0(id TEXT PRIMARY KEY, title_embedding FLOAT[{dim}], definition_embedding FLOAT[{dim}])"
                            conn.exec_driver_sql(create_sql)
                            
                            insert_sql = f"INSERT INTO {table_name} (id, title_embedding, definition_embedding) SELECT id, title_embedding, definition_embedding FROM {main_table}"
                            conn.exec_driver_sql(insert_sql)
                        except Exception as e:
                            logger.exception("Failed to create/populate vec table %s: %s", table_name, e)
                            raise DatabaseError(f"failed_to_create_vec_table_{table_name}: {e}")

                    # Create vec tables; sqlite_vec should already be loaded by init_db event listeners
                    _create_and_populate('schema_org_entities_vec', ent_dim, 'schema_org_entities')
                    _create_and_populate('schema_org_properties_vec', prop_dim, 'schema_org_properties')
                except DatabaseError:
                    # Critical error loading sqlite-vec; re-raise so caller/tests fail
                    raise
                except Exception:
                    logger.exception("Failed to create/populate vec tables; continuing")
        except Exception as e:
            # If a DatabaseError occurred (e.g. sqlite-vec failed to load), re-raise
            # so callers/tests fail fast and show the diagnostic error.
            if isinstance(e, DatabaseError):
                raise
            logger.exception("Failed to create indexes or FTS5 tables")

    def _generate_embeddings_batch(self, items: List[dict], item_type: str) -> None:
        """Generate embeddings for a batch of items (title/definition).

        `item_type` is a human-readable label for logging.
        """
        logger.info("Generating embeddings for %s: %d items", item_type, len(items))
        results: Dict[str, Tuple[Optional[bytes], Optional[bytes]]] = {}
        total = len(items)
        for idx, it in enumerate(items, start=1):
            identifier = it.get("identifier")
            title = it.get("title") or ""
            definition = it.get("definition") or None
            title_emb: Optional[bytes] = None
            def_emb: Optional[bytes] = None
            try:
                if title:
                    title_emb = generate_embedding(title)
                if definition:
                    def_emb = generate_embedding(definition)
            except Exception:
                logger.exception("Failed to generate embeddings for %s %s", item_type, identifier)
                # If embedding generation fails for many items we should escalate
                # For now, raise an EmbeddingError so caller can decide to abort
                raise EmbeddingError(f"embedding_failed_for_{identifier}")
            results[identifier] = (title_emb, def_emb)
            if idx % 50 == 0 or idx == total:
                logger.info("%s embedding progress: %d/%d", item_type, idx, total)
        return results
