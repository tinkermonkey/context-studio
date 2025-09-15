"""Wikidata adapter for unified reference facade"""

from typing import List, Dict
from ..models import UnifiedNode, UnifiedLink, ReferenceSource
from .base import ReferenceAdapter
from ...sources.wikidata import WikidataSource
from config import get_config_manager

class WikidataAdapter(ReferenceAdapter):
    """Adapter for Wikidata source"""

    def _get_source_implementation(self):
        """Get Wikidata source instance"""
        config_manager = get_config_manager()
        source_config = config_manager.settings.get_source_config("wikidata")
        return WikidataSource("wikidata", source_config)

    async def search_nodes(self, query: str, search_type: str = "title", limit: int = 20, offset: int = 0) -> List[UnifiedNode]:
        """Search Wikidata for nodes using SPARQL"""
        normalized_query = self._normalize_query(query)

        # Build SPARQL query for entity search
        sparql_query = self._build_search_sparql(normalized_query, limit, offset)

        async with self.source:
            response = await self.source.sparql_query(
                query=sparql_query,
                format="json"
            )

        nodes = []
        if response.success and response.results:
            bindings = response.results.get('results', {}).get('bindings', [])
            for binding in bindings:
                node = self.transform_node_from_sparql_binding(binding)
                if node:
                    nodes.append(node)

        return nodes

    async def get_links(self, node_id: str, direction: str = "both") -> List[UnifiedLink]:
        """Get Wikidata relationships for a node"""
        # Extract entity ID from unified ID
        if ':' in node_id:
            source_prefix, entity_id = node_id.split(':', 1)
        else:
            entity_id = node_id

        # Ensure entity ID format
        if not entity_id.startswith('Q'):
            return []

        entity_uri = f"http://www.wikidata.org/entity/{entity_id}"

        # Build SPARQL query for relationships
        sparql_query = self._build_links_sparql(entity_uri, direction)

        async with self.source:
            response = await self.source.sparql_query(
                query=sparql_query,
                format="json"
            )

        links = []
        if response.success and response.results:
            bindings = response.results.get('results', {}).get('bindings', [])
            for binding in bindings:
                link = self.transform_link_from_sparql_binding(binding)
                if link:
                    links.append(link)

        return links

    def transform_node_from_sparql_binding(self, binding: Dict) -> UnifiedNode:
        """Transform SPARQL binding to unified node"""
        entity_uri = binding.get('entity', {}).get('value', '')
        label = binding.get('entityLabel', {}).get('value', '')
        description = binding.get('entityDescription', {}).get('value', '')

        if not entity_uri:
            return None

        # Extract entity ID
        entity_id = entity_uri.split('/')[-1]

        return UnifiedNode(
            id=self._generate_id(entity_uri),
            source=ReferenceSource.WIKIDATA,
            source_id=entity_uri,
            title=label or entity_id,
            definition=description or None,
            attributes={
                "entity_id": entity_id,
                "types": binding.get('instanceOf', {}).get('value', '').split(',') if binding.get('instanceOf') else [],
                **self._extract_base_attributes(binding)
            },
            source_url=entity_uri,
            confidence_score=1.0
        )

    def transform_node(self, data: Dict) -> UnifiedNode:
        """Transform Wikidata entity data to unified node"""
        entity_uri = data.get('entity_url', data.get('@id', ''))
        entity_data = data.get('data', {})

        # Extract labels and descriptions
        labels = entity_data.get('labels', {})
        descriptions = entity_data.get('descriptions', {})

        # Get English label/description or fallback to first available
        label = ''
        description = ''

        if 'en' in labels:
            label = labels['en'].get('value', '')
        elif labels:
            label = next(iter(labels.values())).get('value', '')

        if 'en' in descriptions:
            description = descriptions['en'].get('value', '')
        elif descriptions:
            description = next(iter(descriptions.values())).get('value', '')

        # Extract entity ID
        entity_id = entity_uri.split('/')[-1] if entity_uri else ''

        return UnifiedNode(
            id=self._generate_id(entity_uri),
            source=ReferenceSource.WIKIDATA,
            source_id=entity_uri,
            title=label or entity_id,
            definition=description or None,
            attributes={
                "entity_id": entity_id,
                "claims": entity_data.get('claims', {}),
                **self._extract_base_attributes(data)
            },
            source_url=entity_uri,
            confidence_score=1.0
        )

    def transform_link_from_sparql_binding(self, binding: Dict) -> UnifiedLink:
        """Transform SPARQL binding to unified link"""
        subject_uri = binding.get('subject', {}).get('value', '')
        predicate_uri = binding.get('predicate', {}).get('value', '')
        object_uri = binding.get('object', {}).get('value', '')
        predicate_label = binding.get('predicateLabel', {}).get('value', predicate_uri)

        if not all([subject_uri, predicate_uri, object_uri]):
            return None

        return UnifiedLink(
            id=self._generate_id(f"{subject_uri}-{predicate_uri}-{object_uri}"),
            source=ReferenceSource.WIKIDATA,
            subject=self._generate_id(subject_uri),
            predicate=predicate_label,
            object=self._generate_id(object_uri),
            weight=1.0,
            attributes={
                "predicate_uri": predicate_uri,
                **self._extract_base_attributes(binding)
            }
        )

    def transform_link(self, data: Dict) -> UnifiedLink:
        """Transform Wikidata relationship to unified link"""
        # This method handles direct relationship data
        subject = data.get('subject', '')
        predicate = data.get('predicate', '')
        obj = data.get('object', '')

        return UnifiedLink(
            id=self._generate_id(f"{subject}-{predicate}-{obj}"),
            source=ReferenceSource.WIKIDATA,
            subject=self._generate_id(subject),
            predicate=predicate,
            object=self._generate_id(obj),
            weight=1.0,
            attributes=self._extract_base_attributes(data)
        )

    def _build_search_sparql(self, query: str, limit: int, offset: int) -> str:
        """Build SPARQL query for entity search"""
        return f"""
        SELECT DISTINCT ?entity ?entityLabel ?entityDescription WHERE {{
            ?entity rdfs:label ?label .
            ?entity schema:description ?entityDescription .
            FILTER(LANG(?label) = "en" && LANG(?entityDescription) = "en")
            FILTER(CONTAINS(LCASE(?label), "{query.lower()}"))
            SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
        }}
        LIMIT {limit}
        OFFSET {offset}
        """

    def _build_links_sparql(self, entity_uri: str, direction: str) -> str:
        """Build SPARQL query for entity relationships"""
        if direction == "from":
            return f"""
            SELECT ?predicate ?predicateLabel ?object WHERE {{
                <{entity_uri}> ?predicate ?object .
                FILTER(STRSTARTS(STR(?predicate), "http://www.wikidata.org/prop/direct/"))
                SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
            }}
            LIMIT 100
            """
        elif direction == "to":
            return f"""
            SELECT ?subject ?predicate ?predicateLabel WHERE {{
                ?subject ?predicate <{entity_uri}> .
                FILTER(STRSTARTS(STR(?predicate), "http://www.wikidata.org/prop/direct/"))
                SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
            }}
            LIMIT 100
            """
        else:  # both
            return f"""
            SELECT ?subject ?predicate ?predicateLabel ?object WHERE {{
                {{
                    <{entity_uri}> ?predicate ?object .
                    BIND(<{entity_uri}> AS ?subject)
                }}
                UNION
                {{
                    ?subject ?predicate <{entity_uri}> .
                    BIND(<{entity_uri}> AS ?object)
                }}
                FILTER(STRSTARTS(STR(?predicate), "http://www.wikidata.org/prop/direct/"))
                SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
            }}
            LIMIT 100
            """