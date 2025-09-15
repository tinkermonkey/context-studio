"""ConceptNet adapter for unified reference facade"""

from typing import List, Dict
from ..models import UnifiedNode, UnifiedLink, ReferenceSource
from .base import ReferenceAdapter
from ...sources.conceptnet import ConceptNetSource
from config import get_config_manager

class ConceptNetAdapter(ReferenceAdapter):
    """Adapter for ConceptNet source"""

    def _get_source_implementation(self):
        """Get ConceptNet source instance"""
        config_manager = get_config_manager()
        source_config = config_manager.settings.get_source_config("conceptnet")
        return ConceptNetSource("conceptnet", source_config)

    async def search_nodes(self, query: str, search_type: str = "title", limit: int = 20, offset: int = 0) -> List[UnifiedNode]:
        """Search ConceptNet for nodes"""
        normalized_query = self._normalize_query(query)

        # Convert to ConceptNet concept format
        concept_path = f"/c/en/{normalized_query.replace(' ', '_')}"

        async with self.source:
            # Query ConceptNet for edges containing this concept
            response = await self.source.query(
                node=concept_path,
                limit=limit,
                offset=offset
            )

        # Transform results
        nodes = []
        seen_concepts = set()

        if response.success and response.edges:
            for edge in response.edges:
                # Extract unique concepts from edges
                for node_key in ['start', 'end']:
                    node_data = getattr(edge, node_key, {})
                    if node_data and isinstance(node_data, dict):
                        concept_id = node_data.get('@id', '')
                        if concept_id and concept_id not in seen_concepts:
                            seen_concepts.add(concept_id)
                            node = self.transform_node(node_data)
                            # Filter for relevance to original query
                            if self._is_relevant_to_query(node.title, normalized_query):
                                nodes.append(node)

        return nodes[:limit]  # Ensure we don't exceed limit

    async def get_links(self, node_id: str, direction: str = "both") -> List[UnifiedLink]:
        """Get ConceptNet relationships for a node"""
        # Extract original concept path from unified ID
        if ':' in node_id:
            _, concept_path = node_id.split(':', 1)
            concept_path = f"/c/en/{concept_path}"
        else:
            concept_path = node_id

        async with self.source:
            if direction == "from":
                response = await self.source.query(start=concept_path, limit=100)
            elif direction == "to":
                response = await self.source.query(end=concept_path, limit=100)
            else:  # both
                response = await self.source.query(node=concept_path, limit=100)

        links = []
        if response.success and response.edges:
            for edge in response.edges:
                link = self.transform_link(edge)
                links.append(link)

        return links

    def transform_node(self, data: Dict) -> UnifiedNode:
        """Transform ConceptNet concept to unified node"""
        concept_id = data.get('@id', '')
        label = data.get('label', concept_id.split('/')[-1] if concept_id else '')

        # Extract language and term information
        language = data.get('language', 'en')
        term = data.get('term', label)

        return UnifiedNode(
            id=self._generate_id(concept_id),
            source=ReferenceSource.CONCEPTNET,
            source_id=concept_id,
            title=label,
            definition=None,  # ConceptNet doesn't provide definitions directly
            attributes={
                "language": language,
                "term": term,
                "sense_label": data.get('sense_label'),
                **self._extract_base_attributes(data)
            },
            source_url=f"http://conceptnet.io{concept_id}" if concept_id else None,
            confidence_score=1.0
        )

    def transform_link(self, data: Dict) -> UnifiedLink:
        """Transform ConceptNet edge to unified link"""
        edge_id = data.get('@id', '')
        start_node = data.get('start', {})
        rel_node = data.get('rel', {})
        end_node = data.get('end', {})

        # Generate IDs for start and end nodes
        start_id = self._generate_id(start_node.get('@id', '')) if start_node.get('@id') else ''
        end_id = self._generate_id(end_node.get('@id', '')) if end_node.get('@id') else ''

        return UnifiedLink(
            id=self._generate_id(edge_id),
            source=ReferenceSource.CONCEPTNET,
            subject=start_id,
            predicate=rel_node.get('label', rel_node.get('@id', '')),
            object=end_id,
            weight=data.get('weight', 1.0),
            attributes={
                "surface_text": data.get('surfaceText'),
                "dataset": data.get('dataset'),
                "sources": data.get('sources', []),
                **self._extract_base_attributes(data)
            }
        )

    def _is_relevant_to_query(self, title: str, query: str) -> bool:
        """Check if a concept title is relevant to the search query"""
        title_lower = title.lower()
        query_lower = query.lower()

        # Exact match
        if query_lower == title_lower:
            return True

        # Contains query
        if query_lower in title_lower:
            return True

        # Query words in title
        query_words = query_lower.split()
        title_words = title_lower.split()

        # Check if any query word matches any title word
        for query_word in query_words:
            for title_word in title_words:
                if query_word == title_word or query_word in title_word:
                    return True

        return False