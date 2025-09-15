"""Schema.org adapter for unified reference facade"""

from typing import List, Dict
from ..models import UnifiedNode, UnifiedLink, ReferenceSource
from .base import ReferenceAdapter
from ...sources.schema_org import SchemaOrgSource
from config import get_config_manager

class SchemaOrgAdapter(ReferenceAdapter):
    """Adapter for Schema.org source"""

    def _get_source_implementation(self):
        """Get Schema.org source instance"""
        config_manager = get_config_manager()
        source_config = config_manager.settings.get_source_config("schema_org")
        return SchemaOrgSource("schema_org", source_config)

    async def search_nodes(self, query: str, search_type: str = "title", limit: int = 20, offset: int = 0) -> List[UnifiedNode]:
        """Search Schema.org for nodes"""
        normalized_query = self._normalize_query(query)

        async with self.source:
            response = await self.source.search(
                query=query,
                search_type="both",  # Search both entities and properties
                limit=limit,
                offset=offset,
                similarity_threshold=0.7
            )

        nodes = []
        if response.success and response.results:
            for result in response.results:
                node = self.transform_node_from_search_result(result)
                nodes.append(node)

        return nodes

    async def get_links(self, node_id: str, direction: str = "both") -> List[UnifiedLink]:
        """Get Schema.org relationships for a node"""
        # Extract identifier from unified ID
        if ':' in node_id:
            source_prefix, identifier = node_id.split(':', 1)
        else:
            identifier = node_id

        links = []

        async with self.source:
            # Get entity details to extract properties and relationships
            if identifier:
                entity_response = await self.source.get_entity(
                    identifier=identifier,
                    include_inherited=True,
                    include_children=True
                )

                if entity_response.success and entity_response.entity:
                    entity = entity_response.entity

                    # Convert properties to links
                    for prop in entity.properties:
                        link = self._property_to_link(entity, prop, direction)
                        if link:
                            links.append(link)

                    # Convert child relationships to links
                    for child in entity.children:
                        link = self._child_to_link(entity, child)
                        if link:
                            links.append(link)

                    # Add parent relationship if exists
                    if entity.parent_identifier:
                        parent_link = self._parent_to_link(entity)
                        if parent_link:
                            links.append(parent_link)

        return links

    def transform_node_from_search_result(self, result: Dict) -> UnifiedNode:
        """Transform Schema.org search result to unified node"""
        identifier = result.get('identifier', '')
        title = result.get('title', '')
        definition = result.get('definition', '')
        result_type = result.get('type', 'entity')

        return UnifiedNode(
            id=self._generate_id(identifier),
            source=ReferenceSource.SCHEMA_ORG,
            source_id=identifier,
            title=title,
            definition=definition,
            attributes={
                "type": result_type,
                "relevance_score": result.get('relevance_score', 1.0),
                **self._extract_base_attributes(result)
            },
            source_url=f"https://schema.org/{identifier}",
            confidence_score=min(result.get('relevance_score', 1.0), 1.0)
        )

    def transform_node(self, data: Dict) -> UnifiedNode:
        """Transform Schema.org entity to unified node"""
        if 'entity' in data and data['entity']:
            entity = data['entity']
            identifier = entity.get('identifier', '')
            title = entity.get('title', '')
            definition = entity.get('definition', '')

            return UnifiedNode(
                id=self._generate_id(identifier),
                source=ReferenceSource.SCHEMA_ORG,
                source_id=identifier,
                title=title,
                definition=definition,
                attributes={
                    "parent_identifier": entity.get('parent_identifier'),
                    "properties_count": len(entity.get('properties', [])),
                    "children_count": len(entity.get('children', [])),
                    **self._extract_base_attributes(data)
                },
                source_url=f"https://schema.org/{identifier}",
                confidence_score=1.0
            )

        # Fallback for direct entity data
        identifier = data.get('identifier', '')
        title = data.get('title', '')
        definition = data.get('definition', '')

        return UnifiedNode(
            id=self._generate_id(identifier),
            source=ReferenceSource.SCHEMA_ORG,
            source_id=identifier,
            title=title,
            definition=definition,
            attributes=self._extract_base_attributes(data),
            source_url=f"https://schema.org/{identifier}",
            confidence_score=1.0
        )

    def transform_link(self, data: Dict) -> UnifiedLink:
        """Transform Schema.org relationship to unified link"""
        subject = data.get('subject', '')
        predicate = data.get('predicate', '')
        obj = data.get('object', '')

        return UnifiedLink(
            id=self._generate_id(f"{subject}-{predicate}-{obj}"),
            source=ReferenceSource.SCHEMA_ORG,
            subject=self._generate_id(subject),
            predicate=predicate,
            object=self._generate_id(obj),
            weight=1.0,
            attributes=self._extract_base_attributes(data)
        )

    def _property_to_link(self, entity, prop: Dict, direction: str) -> UnifiedLink:
        """Convert Schema.org property to unified link"""
        entity_id = self._generate_id(entity.identifier)
        prop_id = self._generate_id(prop.get('identifier', ''))

        # Property relationships can be viewed in different directions
        if direction == "from" or direction == "both":
            return UnifiedLink(
                id=self._generate_id(f"{entity.identifier}-hasProperty-{prop.get('identifier', '')}"),
                source=ReferenceSource.SCHEMA_ORG,
                subject=entity_id,
                predicate="hasProperty",
                object=prop_id,
                weight=1.0,
                attributes={
                    "property_type": "property",
                    "expected_types": prop.get('expected_types', []),
                    "inherited": prop.get('inherited', False),
                    "inherited_from": prop.get('inherited_from'),
                    **self._extract_base_attributes(prop)
                }
            )

        return None

    def _child_to_link(self, entity, child: Dict) -> UnifiedLink:
        """Convert Schema.org child relationship to unified link"""
        entity_id = self._generate_id(entity.identifier)
        child_id = self._generate_id(child.get('identifier', ''))

        return UnifiedLink(
            id=self._generate_id(f"{entity.identifier}-hasChild-{child.get('identifier', '')}"),
            source=ReferenceSource.SCHEMA_ORG,
            subject=entity_id,
            predicate="hasChild",
            object=child_id,
            weight=1.0,
            attributes={
                "relationship_type": "child",
                **self._extract_base_attributes(child)
            }
        )

    def _parent_to_link(self, entity) -> UnifiedLink:
        """Convert Schema.org parent relationship to unified link"""
        entity_id = self._generate_id(entity.identifier)
        parent_id = self._generate_id(entity.parent_identifier)

        return UnifiedLink(
            id=self._generate_id(f"{entity.identifier}-hasParent-{entity.parent_identifier}"),
            source=ReferenceSource.SCHEMA_ORG,
            subject=entity_id,
            predicate="hasParent",
            object=parent_id,
            weight=1.0,
            attributes={
                "relationship_type": "parent",
                **self._extract_base_attributes({"parent": entity.parent_identifier})
            }
        )