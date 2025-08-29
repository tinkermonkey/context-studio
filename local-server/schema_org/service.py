"""
Service layer for Schema.org business logic.

Provides a thin wrapper around the manager exposing search and retrieval
capabilities to the API layer.
"""

from typing import Optional, Dict, Any, List, Tuple
from .manager import SchemaOrgManager
from .models import SchemaOrgEntity, SchemaOrgProperty
from utils.logger import get_logger
import numpy as np
from sqlalchemy import select, func, text
from .errors import SearchError, ValidationError

logger = get_logger(__name__)


def _deserialize_embedding(blob: bytes) -> Optional[np.ndarray]:
    """Convert stored float32 bytes back into a numpy array, or return None."""
    if not blob:
        return None
    try:
        arr = np.frombuffer(blob, dtype=np.float32)
        return arr
    except Exception:
        logger.exception("Failed to deserialize embedding blob")
        return None


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two 1-D numpy arrays."""
    if a is None or b is None:
        return -1.0
    # Defensive normalization
    try:
        a_norm = a / np.linalg.norm(a)
        b_norm = b / np.linalg.norm(b)
        return float(np.dot(a_norm, b_norm))
    except Exception:
        return -1.0


class SchemaOrgService:
    """Business logic layer for schema.org functionality."""
    def __init__(self, manager: SchemaOrgManager = None):
        """Create service instance and in-memory caches."""
        self.manager = manager or SchemaOrgManager()
        # in-memory cache for embeddings to speed up fallback semantic_search
        # structure: {"entities": {identifier: (title_emb, def_emb, row)}, "properties": {...}}
        self._embedding_cache: Dict[str, Dict[str, Tuple[Optional[np.ndarray], Optional[np.ndarray], Any]]] = {
            "entities": {},
            "properties": {},
        }

    def _serialize_entity(self, row: SchemaOrgEntity, session) -> Dict[str, Any]:
        children_count = session.execute(
            select(func.count()).select_from(SchemaOrgEntity).where(SchemaOrgEntity.parent_id == row.id)
        ).scalar()
        return {
            "id": row.id,
            "identifier": row.identifier,
            "title": row.title,
            "definition": row.definition,
            "parent_identifier": row.parent_identifier,
            "parent_id": row.parent_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "children_count": int(children_count or 0),
            "raw": row.raw,
        }

    def _serialize_property(self, row: SchemaOrgProperty) -> Dict[str, Any]:
        return {
            "id": row.id,
            "identifier": row.identifier,
            "title": row.title,
            "definition": row.definition,
            "contributors": row.contributors,
            "domain_includes": row.domain_includes,
            "range_includes": row.range_includes,
            "inverse_of": row.inverse_of,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "raw": row.raw,
        }

    def search_entities(self, query: Optional[str] = None, parent_id: Optional[str] = None,
                        limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """Search entities with simple text matching and pagination.

        This uses SQL LIKE fallback; FTS5 or vector indexes are preferred when available.
        """
        logger.debug("search_entities called (query=%s parent_id=%s limit=%s offset=%s)", query, parent_id, limit, offset)
        if limit <= 0 or offset < 0:
            logger.warning("Invalid pagination parameters: limit=%s offset=%s", limit, offset)
            raise ValidationError("invalid_pagination")

        SessionLocal = self.manager.get_session_local()
        session = SessionLocal()
        try:
            stmt = select(SchemaOrgEntity)
            if query:
                q = f"%{query}%"
                stmt = stmt.where((SchemaOrgEntity.title.ilike(q)) | (SchemaOrgEntity.definition.ilike(q)))
            if parent_id:
                stmt = stmt.where(SchemaOrgEntity.parent_id == parent_id)

            total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar()
            rows = session.execute(stmt.order_by(SchemaOrgEntity.title).limit(limit).offset(offset)).scalars().all()
            items = [self._serialize_entity(r, session) for r in rows]
            return {"items": items, "total_count": int(total or 0), "limit": limit, "offset": offset}
        finally:
            session.close()

    def get_entity(self, identifier: str) -> Optional[Dict[str, Any]]:
        logger.debug("get_entity called (identifier=%s)", identifier)
        SessionLocal = self.manager.get_session_local()
        session = SessionLocal()
        try:
            row = session.execute(select(SchemaOrgEntity).where(SchemaOrgEntity.identifier == identifier)).scalar_one_or_none()
            if not row:
                return None
            return self._serialize_entity(row, session)
        finally:
            session.close()

    def search_properties(self, query: Optional[str] = None, domain_includes: Optional[str] = None,
                          range_includes: Optional[str] = None, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        logger.debug("search_properties called (query=%s domain=%s range=%s)", query, domain_includes, range_includes)
        if limit <= 0 or offset < 0:
            logger.warning("Invalid pagination parameters for properties: limit=%s offset=%s", limit, offset)
            raise ValidationError("invalid_pagination")

        SessionLocal = self.manager.get_session_local()
        session = SessionLocal()
        try:
            stmt = select(SchemaOrgProperty)
            if query:
                q = f"%{query}%"
                stmt = stmt.where((SchemaOrgProperty.title.ilike(q)) | (SchemaOrgProperty.definition.ilike(q)))
            if domain_includes:
                stmt = stmt.where(func.json_extract(SchemaOrgProperty.domain_includes, '$') != None)
                # lightweight filter; more sophisticated JSON checks can be added
            if range_includes:
                stmt = stmt.where(func.json_extract(SchemaOrgProperty.range_includes, '$') != None)

            total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar()
            rows = session.execute(stmt.order_by(SchemaOrgProperty.title).limit(limit).offset(offset)).scalars().all()
            items = [self._serialize_property(r) for r in rows]
            return {"items": items, "total_count": int(total or 0), "limit": limit, "offset": offset}
        finally:
            session.close()

    def get_property(self, identifier: str) -> Optional[Dict[str, Any]]:
        logger.debug("get_property called (identifier=%s)", identifier)
        SessionLocal = self.manager.get_session_local()
        session = SessionLocal()
        try:
            row = session.execute(select(SchemaOrgProperty).where(SchemaOrgProperty.identifier == identifier)).scalar_one_or_none()
            if not row:
                return None
            return self._serialize_property(row)
        finally:
            session.close()

    def invalidate_cache(self):
        """Clear embedding cache after refresh/populate operations."""
        logger.info("Invalidating schema_org embedding cache")
        self._embedding_cache = {"entities": {}, "properties": {}}

    def semantic_search(self, query: str, search_type: str = "both", limit: int = 20,
                        similarity_threshold: float = 0.7) -> Dict[str, Any]:
        """Perform a semantic search by generating an embedding for `query` and
        comparing against stored embeddings in the database.

        This is a Python-side fallback when sqlite-vec vector tables are not present.
        It loads embeddings into memory (title and definition) and computes cosine
        similarity, returning top results above the threshold.
        """
        logger.debug("semantic_search called (query=%s search_type=%s)", query, search_type)
        q_emb_bytes = None
        if not query or not query.strip():
            logger.warning("Empty semantic search query")
            raise ValidationError("empty_query")

        try:
            from embeddings.generate_embeddings import generate_embedding
            q_emb_bytes = generate_embedding(query)
        except Exception as e:
            logger.exception("Failed to generate query embedding: %s", e)
            raise SearchError("embedding_generation_failed")

        q_emb = _deserialize_embedding(q_emb_bytes)
        if q_emb is None:
            logger.error("Query embedding deserialization failed")
            raise SearchError("invalid_query_embedding")
        # Try to use sqlite-vec SQL-level search if vec virtual tables exist
        engine = self.manager.get_engine()
        try:
            with engine.connect() as conn:
                # check for vec0 virtual tables (sqlite-vec) - user migrations may create them
                has_vec = False
                try:
                    # Check for the vec tables created by the manager: schema_org_entities_vec or schema_org_properties_vec
                    res_ent = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_org_entities_vec' LIMIT 1")).fetchone()
                    res_prop = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_org_properties_vec' LIMIT 1")).fetchone()
                    has_vec = bool(res_ent or res_prop)
                except Exception:
                    has_vec = False

                results: List[Tuple[float, Dict[str, Any]]] = []
                if has_vec:
                    logger.debug("Using SQL-level vec index for semantic search")
                    # Format embedding param the same way other APIs do (e.g., domains/terms)
                    try:
                        emb_list = [float(x) for x in q_emb.tolist()]
                        emb_param = "[" + ", ".join(f"{x:.6f}" for x in emb_list) + "]"
                    except Exception:
                        emb_param = None

                    # We'll run SQL KNN against vec virtual tables that follow the pattern <table>_vec
                    seen_ids = set()
                    SessionLocal = self.manager.get_session_local()

                    # Helper to run a vec KNN and materialize ORM objects for serialization
                    def _run_vec_knn(vec_table: str, main_table: str, model_cls, emb_col: str):
                        nonlocal results
                        if not emb_param:
                            return
                        sql = text(
                            f"""
                            SELECT m.id
                            FROM (
                                SELECT id, distance
                                FROM {vec_table}
                                WHERE {emb_col} match :emb_param
                                ORDER BY distance
                                LIMIT :limit
                            ) v
                            JOIN {main_table} m ON m.id = v.id
                            """
                        )
                        try:
                            # execute via engine connection to use sqlite-vec
                            rows = conn.execute(sql, {"emb_param": emb_param, "limit": limit}).fetchall()
                        except Exception as e:
                            logger.warning("sqlite-vec KNN query failed for %s: %s", vec_table, e)
                            return

                        if not rows:
                            return

                        session = SessionLocal()
                        try:
                            for r in rows:
                                rid = r[0]
                                if rid in seen_ids:
                                    continue
                                # load ORM object for consistent serialization
                                orm_row = session.execute(select(model_cls).where(model_cls.id == rid)).scalar_one_or_none()
                                if not orm_row:
                                    continue
                                # choose which embedding column to compare
                                if emb_col == 'title_embedding':
                                    stored = _deserialize_embedding(orm_row.title_embedding)
                                else:
                                    stored = _deserialize_embedding(orm_row.definition_embedding)

                                score = _cosine_similarity(q_emb, stored)
                                if score >= similarity_threshold:
                                    # serialize entity/property appropriately
                                    if model_cls.__name__ == 'SchemaOrgEntity':
                                        payload = self._serialize_entity(orm_row, session)
                                    else:
                                        payload = self._serialize_property(orm_row)
                                    results.append((score, payload))
                                    seen_ids.add(rid)
                        finally:
                            session.close()

                    # Run vec KNN for entities and properties when requested
                    if search_type in ("both", "entities"):
                        # check specific vec table exists
                        ent_tbl = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_org_entities_vec'")).fetchone()
                        if ent_tbl:
                            _run_vec_knn('schema_org_entities_vec', 'schema_org_entities', SchemaOrgEntity, 'title_embedding')
                            _run_vec_knn('schema_org_entities_vec', 'schema_org_entities', SchemaOrgEntity, 'definition_embedding')

                    if search_type in ("both", "properties"):
                        prop_tbl = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_org_properties_vec'")).fetchone()
                        if prop_tbl:
                            _run_vec_knn('schema_org_properties_vec', 'schema_org_properties', SchemaOrgProperty, 'title_embedding')
                            _run_vec_knn('schema_org_properties_vec', 'schema_org_properties', SchemaOrgProperty, 'definition_embedding')

                    # If vec produced results, sort and return top-N
                    if results:
                        results.sort(key=lambda x: x[0], reverse=True)
                        items = [item for _, item in results[:limit]]
                        return {"items": items, "total_count": len(results), "limit": limit, "offset": 0}
                # Fallback path: in-memory scan with cached embeddings
                SessionLocal = self.manager.get_session_local()
                session = SessionLocal()
                try:
                    # Load entities/properties embeddings into cache if empty
                    if search_type in ("both", "entities"):
                        if not self._embedding_cache["entities"]:
                            rows = session.execute(select(SchemaOrgEntity).where(SchemaOrgEntity.title_embedding != None)).scalars().all()
                            for r in rows:
                                t_emb = _deserialize_embedding(r.title_embedding)
                                d_emb = _deserialize_embedding(r.definition_embedding)
                                self._embedding_cache["entities"][r.identifier] = (t_emb, d_emb, r)

                        for identifier, (t_emb, d_emb, row) in self._embedding_cache["entities"].items():
                            scores = []
                            if t_emb is not None:
                                scores.append(_cosine_similarity(q_emb, t_emb))
                            if d_emb is not None:
                                scores.append(_cosine_similarity(q_emb, d_emb))
                            score = max(scores) if scores else -1.0
                            if score >= similarity_threshold:
                                results.append((score, self._serialize_entity(row, session)))

                    if search_type in ("both", "properties"):
                        if not self._embedding_cache["properties"]:
                            rows = session.execute(select(SchemaOrgProperty).where(SchemaOrgProperty.title_embedding != None)).scalars().all()
                            for r in rows:
                                t_emb = _deserialize_embedding(r.title_embedding)
                                d_emb = _deserialize_embedding(r.definition_embedding)
                                self._embedding_cache["properties"][r.identifier] = (t_emb, d_emb, r)

                        for identifier, (t_emb, d_emb, row) in self._embedding_cache["properties"].items():
                            scores = []
                            if t_emb is not None:
                                scores.append(_cosine_similarity(q_emb, t_emb))
                            if d_emb is not None:
                                scores.append(_cosine_similarity(q_emb, d_emb))
                            score = max(scores) if scores else -1.0
                            if score >= similarity_threshold:
                                results.append((score, self._serialize_property(row)))

                    results.sort(key=lambda x: x[0], reverse=True)
                    items = [item for _, item in results[:limit]]
                    return {"items": items, "total_count": len(results), "limit": limit, "offset": 0}
                finally:
                    session.close()
        except Exception as e:
            logger.exception("Semantic search failed: %s", e)
            raise SearchError(str(e))
