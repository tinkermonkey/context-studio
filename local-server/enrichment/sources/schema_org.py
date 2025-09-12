"""Schema.org source implementation that leverages the existing SchemaOrgManager"""

from .base import BaseReferenceSource
from ..models import SchemaOrgEntityResponse, SchemaOrgPropertyResponse, SchemaOrgSearchResponse
from schema_org.manager import SchemaOrgManager


class SchemaOrgSource(BaseReferenceSource):
    def __init__(self, source_type, config):
        super().__init__(source_type, config)
        self.manager = SchemaOrgManager()

    def _get_default_base_url(self) -> str:
        # Schema.org is local; base_url not used for this source
        return ""

    def _get_proxy_domain_key(self) -> str:
        return "schema_org"

    async def get_entity(self, identifier: str, include_inherited: bool = True, include_children: bool = False) -> SchemaOrgEntityResponse:
        try:
            # Use manager's DB to retrieve entity by identifier
            # The manager is synchronous; run in thread to avoid blocking
            def _lookup():
                sess_maker = self.manager.get_session_local()
                session = sess_maker()
                try:
                    # Minimal query that returns raw JSON columns; implementation may vary
                    row = session.execute("SELECT raw FROM schema_org_entities WHERE identifier = :id", {"id": identifier}).fetchone()
                    if not row:
                        return None
                    return row[0]
                finally:
                    session.close()

            loop = __import__('asyncio').get_event_loop()
            data = await loop.run_in_executor(None, _lookup)
            if data is None:
                return SchemaOrgEntityResponse(**self._create_base_response(success=False, error="not_found"))
            return SchemaOrgEntityResponse(**self._create_base_response(), identifier=identifier, entity=data)
        except Exception as e:
            return SchemaOrgEntityResponse(**self._create_base_response(success=False, error=str(e)))

    async def get_property(self, identifier: str, include_usage: bool = True) -> SchemaOrgPropertyResponse:
        try:
            def _lookup():
                sess_maker = self.manager.get_session_local()
                session = sess_maker()
                try:
                    row = session.execute("SELECT raw FROM schema_org_properties WHERE identifier = :id", {"id": identifier}).fetchone()
                    if not row:
                        return None
                    return row[0]
                finally:
                    session.close()

            loop = __import__('asyncio').get_event_loop()
            data = await loop.run_in_executor(None, _lookup)
            if data is None:
                return SchemaOrgPropertyResponse(**self._create_base_response(success=False, error="not_found"))
            return SchemaOrgPropertyResponse(**self._create_base_response(), identifier=identifier, property=data)
        except Exception as e:
            return SchemaOrgPropertyResponse(**self._create_base_response(success=False, error=str(e)))

    async def search(self, query: str, search_type: str = "both", limit: int = 20, offset: int = 0, similarity_threshold: float = 0.7) -> SchemaOrgSearchResponse:
        try:
            # Simple search against FTS tables if available; fallback to empty
            def _search():
                sess_maker = self.manager.get_session_local()
                session = sess_maker()
                try:
                    sql = []
                    results = []
                    if search_type in ("entities", "both"):
                        q = session.execute("SELECT identifier, title, definition FROM schema_org_entities_fts WHERE schema_org_entities_fts MATCH :q LIMIT :lim", {"q": query, "lim": limit}).fetchall() if session.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_org_entities_fts'").fetchone() else []
                        for r in q:
                            results.append({"type": "entity", "identifier": r[0], "title": r[1], "definition": r[2], "relevance_score": 1.0})
                    if search_type in ("properties", "both"):
                        q = session.execute("SELECT identifier, title, definition FROM schema_org_properties_fts WHERE schema_org_properties_fts MATCH :q LIMIT :lim", {"q": query, "lim": limit}).fetchall() if session.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_org_properties_fts'").fetchone() else []
                        for r in q:
                            results.append({"type": "property", "identifier": r[0], "title": r[1], "definition": r[2], "relevance_score": 1.0})
                    return results
                finally:
                    session.close()

            loop = __import__('asyncio').get_event_loop()
            results = await loop.run_in_executor(None, _search)
            return SchemaOrgSearchResponse(**self._create_base_response(), query=query, search_type=search_type, total_results=len(results), results=results)
        except Exception as e:
            return SchemaOrgSearchResponse(**self._create_base_response(success=False, error=str(e)))
