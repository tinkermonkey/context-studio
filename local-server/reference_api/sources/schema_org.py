"""Schema.org source implementation using reference_db"""

from .base import BaseReferenceSource
from ..models import SchemaOrgEntityResponse, SchemaOrgPropertyResponse, SchemaOrgSearchResponse
from reference_db.manager import ReferenceManager
from reference_db.config import ReferenceConfig
from sqlalchemy import text
import json


class SchemaOrgSource(BaseReferenceSource):
    def __init__(self, source_type, config):
        super().__init__(source_type, config)
        self.ref_config = ReferenceConfig()

    def _get_default_base_url(self) -> str:
        # Schema.org is local; base_url not used for this source
        return ""

    def _get_proxy_domain_key(self) -> str:
        return "schema_org"

    async def get_entity(self, identifier: str, include_inherited: bool = True, include_children: bool = False) -> SchemaOrgEntityResponse:
        try:
            # Use reference_db to retrieve entity by identifier
            def _lookup():
                with ReferenceManager(self.ref_config) as ref_manager:
                    # Query reference_nodes for schema.org entity
                    result = ref_manager.session.execute(
                        text("""
                            SELECT id, title, definition, external_id, attributes
                            FROM reference_nodes
                            WHERE source = :source AND external_id = :identifier
                        """),
                        {"source": "schema.org", "identifier": identifier}
                    ).fetchone()

                    if not result:
                        return None

                    # Construct entity data from node
                    entity_data = {
                        "id": result[0],
                        "identifier": result[3],
                        "title": result[1],
                        "definition": result[2],
                        "attributes": json.loads(result[4]) if result[4] else {}
                    }
                    return entity_data

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
                with ReferenceManager(self.ref_config) as ref_manager:
                    # Query reference_nodes for schema.org property
                    result = ref_manager.session.execute(
                        text("""
                            SELECT id, title, definition, external_id, attributes
                            FROM reference_nodes
                            WHERE source = :source AND external_id = :identifier
                        """),
                        {"source": "schema.org", "identifier": identifier}
                    ).fetchone()

                    if not result:
                        return None

                    # Construct property data from node
                    property_data = {
                        "id": result[0],
                        "identifier": result[3],
                        "title": result[1],
                        "definition": result[2],
                        "attributes": json.loads(result[4]) if result[4] else {}
                    }
                    return property_data

            loop = __import__('asyncio').get_event_loop()
            data = await loop.run_in_executor(None, _lookup)
            if data is None:
                return SchemaOrgPropertyResponse(**self._create_base_response(success=False, error="not_found"))
            return SchemaOrgPropertyResponse(**self._create_base_response(), identifier=identifier, property=data)
        except Exception as e:
            return SchemaOrgPropertyResponse(**self._create_base_response(success=False, error=str(e)))

    async def search(self, query: str, search_type: str = "both", limit: int = 20, offset: int = 0, similarity_threshold: float = 0.7) -> SchemaOrgSearchResponse:
        try:
            # Use vector search
            def _search():
                import logging
                logger = logging.getLogger(__name__)

                with ReferenceManager(self.ref_config) as ref_manager:
                    try:
                        from embeddings.generate_embeddings import generate_embedding

                        # Create embedding generator function
                        def embedding_gen(text: str) -> bytes:
                            return generate_embedding(text)

                        # Search using vector similarity
                        results_with_scores = ref_manager.search_by_similarity(
                            query_text=query,
                            source="schema.org",
                            limit=limit,
                            threshold=similarity_threshold,
                            embedding_generator=embedding_gen
                        )

                        # Convert to response format
                        results = []
                        for node, score in results_with_scores:
                            # Determine type from attributes if available
                            node_type = "entity"  # default
                            if node.attributes:
                                try:
                                    attrs = json.loads(node.attributes) if isinstance(node.attributes, str) else node.attributes
                                    node_type = attrs.get("@type", "entity")
                                    # Check if it's a property type
                                    if "Property" in str(node_type):
                                        node_type = "property"
                                    else:
                                        node_type = "entity"
                                except Exception:
                                    pass

                            # Filter by search_type
                            if search_type == "entities" and node_type != "entity":
                                continue
                            if search_type == "properties" and node_type != "property":
                                continue

                            results.append({
                                "type": node_type,
                                "identifier": node.external_id,
                                "title": node.title,
                                "definition": node.definition,
                                "relevance_score": score
                            })

                        return results

                    except ImportError:
                        # If embeddings not available, return empty results
                        logger.warning("Vector search not available: embeddings module not found")
                        return []

            loop = __import__('asyncio').get_event_loop()
            results = await loop.run_in_executor(None, _search)
            return SchemaOrgSearchResponse(**self._create_base_response(), query=query, search_type=search_type, total_results=len(results), results=results)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Schema.org vector search failed: {e}")
            return SchemaOrgSearchResponse(**self._create_base_response(success=False, error=str(e)))
