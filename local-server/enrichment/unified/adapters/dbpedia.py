"""DBpedia adapter for unified reference facade"""

from typing import List, Dict
from ..models import UnifiedNode, UnifiedLink, ReferenceSource
from .base import ReferenceAdapter
from ...sources.dbpedia import DBpediaSource
from config import get_config_manager

class DBpediaAdapter(ReferenceAdapter):
    """Adapter for DBpedia source"""

    def _get_source_implementation(self):
        """Get DBpedia source instance"""
        config_manager = get_config_manager()
        source_config = config_manager.settings.get_source_config("dbpedia")
        return DBpediaSource("dbpedia", source_config)

    async def search_nodes(self, query: str, search_type: str = "title", limit: int = 20, offset: int = 0) -> List[UnifiedNode]:
        """Search DBpedia for nodes"""
        normalized_query = self._normalize_query(query)

        async with self.source:
            response = await self.source.search(
                query=query,
                limit=limit,
                offset=offset,
                format="json"
            )

        nodes = []
        if response.success and response.results:
            for result in response.results:
                node = self.transform_node_from_search_result(result)
                nodes.append(node)

        return nodes

    async def get_links(self, node_id: str, direction: str = "both") -> List[UnifiedLink]:
        """Get DBpedia relationships for a node"""
        # Extract original resource URI from unified ID
        if ':' in node_id:
            source_prefix, resource_id = node_id.split(':', 1)
            # Reconstruct DBpedia URI
            resource_uri = f"http://dbpedia.org/resource/{resource_id}"
        else:
            resource_uri = node_id

        async with self.source:
            # Get resource data to extract relationships
            response = await self.source.get_resource_data(
                resource_url=resource_uri,
                format="json"
            )

        links = []
        if response.success and response.data:
            # Parse RDF-like data structure to extract relationships
            data = response.data
            if isinstance(data, dict):
                links.extend(self._extract_links_from_resource_data(data, resource_uri))

        return links

    def transform_node_from_search_result(self, result: Dict) -> UnifiedNode:
        """Transform DBpedia search result to unified node"""
        uri = result.get('uri', '')
        label = result.get('label', '')
        description = result.get('description', '')

        # Extract resource ID from URI
        resource_id = uri.split('/')[-1] if uri else ''

        return UnifiedNode(
            id=self._generate_id(uri),
            source=ReferenceSource.DBPEDIA,
            source_id=uri,
            title=label,
            definition=description,
            attributes={
                "types": result.get('types', []),
                "score": result.get('score', 0.0),
                **self._extract_base_attributes(result)
            },
            source_url=uri,
            confidence_score=min(result.get('score', 1.0), 1.0)
        )

    def transform_node(self, data: Dict) -> UnifiedNode:
        """Transform DBpedia resource data to unified node"""
        # This method handles direct resource data transformation
        resource_uri = data.get('resource_uri', data.get('@id', ''))

        # Extract label from various possible fields
        label = (
            data.get('rdfs:label') or
            data.get('label') or
            data.get('name') or
            resource_uri.split('/')[-1]
        )

        # Extract description
        description = (
            data.get('rdfs:comment') or
            data.get('dbo:abstract') or
            data.get('comment') or
            data.get('abstract')
        )

        return UnifiedNode(
            id=self._generate_id(resource_uri),
            source=ReferenceSource.DBPEDIA,
            source_id=resource_uri,
            title=str(label) if label else '',
            definition=str(description) if description else None,
            attributes={
                "types": data.get('rdf:type', []),
                **self._extract_base_attributes(data)
            },
            source_url=resource_uri,
            confidence_score=1.0
        )

    def transform_link(self, data: Dict) -> UnifiedLink:
        """Transform DBpedia relationship to unified link"""
        subject = data.get('subject', '')
        predicate = data.get('predicate', '')
        obj = data.get('object', '')

        return UnifiedLink(
            id=self._generate_id(f"{subject}-{predicate}-{obj}"),
            source=ReferenceSource.DBPEDIA,
            subject=self._generate_id(subject),
            predicate=predicate,
            object=self._generate_id(obj),
            weight=1.0,
            attributes=self._extract_base_attributes(data)
        )

    def _extract_links_from_resource_data(self, data: Dict, resource_uri: str) -> List[UnifiedLink]:
        """Extract relationships from DBpedia resource data"""
        links = []

        # Skip certain non-relationship properties
        skip_properties = {
            '@context', '@id', '@type', 'rdfs:label', 'rdfs:comment',
            'dbo:abstract', 'label', 'comment', 'abstract', 'name'
        }

        for predicate, values in data.items():
            if predicate in skip_properties:
                continue

            # Handle both single values and arrays
            if not isinstance(values, list):
                values = [values]

            for value in values:
                if isinstance(value, dict):
                    # Handle complex objects
                    obj_uri = value.get('@id', str(value))
                elif isinstance(value, str) and value.startswith('http'):
                    # Direct URI reference
                    obj_uri = value
                else:
                    # Skip literals that aren't URIs
                    continue

                link = UnifiedLink(
                    id=self._generate_id(f"{resource_uri}-{predicate}-{obj_uri}"),
                    source=ReferenceSource.DBPEDIA,
                    subject=self._generate_id(resource_uri),
                    predicate=predicate,
                    object=self._generate_id(obj_uri),
                    weight=1.0,
                    attributes={
                        "value_type": type(value).__name__,
                        **self._extract_base_attributes({'subject': resource_uri, 'predicate': predicate, 'object': obj_uri})
                    }
                )
                links.append(link)

        return links