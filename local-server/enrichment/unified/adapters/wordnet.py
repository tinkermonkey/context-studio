"""WordNet adapter for unified reference facade"""

from typing import List, Dict
from ..models import UnifiedNode, UnifiedLink, ReferenceSource
from .base import ReferenceAdapter
from ...sources.wordnet import WordNetSource
from config import get_config_manager

class WordNetAdapter(ReferenceAdapter):
    """Adapter for WordNet source"""

    def _get_source_implementation(self):
        """Get WordNet source instance"""
        config_manager = get_config_manager()
        # WordNet doesn't need network config, use minimal config
        from config import SourceConfig
        source_config = SourceConfig(
            enabled=True,
            base_url="nltk://wordnet",
            timeout=30,
            max_retries=0
        )
        return WordNetSource("wordnet", source_config)

    async def search_nodes(self, query: str, search_type: str = "title", limit: int = 20, offset: int = 0) -> List[UnifiedNode]:
        """Search WordNet for synsets"""
        normalized_query = self._normalize_query(query)

        # WordNet search doesn't support offset, so we'll get more and slice
        search_limit = min(limit + offset, 100)  # Cap at reasonable limit

        response = await self.source.search_synsets(
            word=normalized_query,
            pos=None,  # Search all parts of speech
            lang="eng",
            limit=search_limit
        )

        nodes = []
        if response.success and response.synsets:
            # Apply offset and limit
            synsets_slice = response.synsets[offset:offset + limit]

            for synset in synsets_slice:
                node = self.transform_node_from_synset(synset)
                nodes.append(node)

        return nodes

    async def get_links(self, node_id: str, direction: str = "both") -> List[UnifiedLink]:
        """Get WordNet semantic relations for a synset"""
        # Extract synset name from unified ID
        if ':' in node_id:
            source_prefix, synset_name = node_id.split(':', 1)
        else:
            synset_name = node_id

        # Get relations from WordNet
        response = await self.source.get_synset_relations(
            synset_name=synset_name,
            relation_types=None  # Get all relation types
        )

        links = []
        if response.success and response.relations:
            for relation in response.relations:
                link = self.transform_relation_to_link(synset_name, relation)
                links.append(link)

        return links

    def transform_node_from_synset(self, synset: Dict) -> UnifiedNode:
        """Transform WordNet synset to unified node"""
        synset_name = synset.get('name', '')
        synset_id = synset.get('id', synset_name)

        return UnifiedNode(
            id=self._generate_id(synset_id),
            source=ReferenceSource.WORDNET,
            source_id=synset_id,
            title=synset.get('name', ''),
            definition=synset.get('definition', ''),
            attributes={
                "pos": synset.get('pos', ''),
                "examples": synset.get('examples', []),
                "lemmas": synset.get('lemmas', []),
                "lexfile": synset.get('lexfile', ''),
                "offset": synset.get('offset'),
                **self._extract_base_attributes(synset)
            },
            source_url=f"http://wordnetweb.princeton.edu/perl/webwn?s={synset_name}",
            confidence_score=1.0
        )

    def transform_node(self, data: Dict) -> UnifiedNode:
        """Transform WordNet data to unified node"""
        # This handles direct synset data transformation
        synset_name = data.get('name', data.get('id', ''))

        return UnifiedNode(
            id=self._generate_id(synset_name),
            source=ReferenceSource.WORDNET,
            source_id=synset_name,
            title=synset_name,
            definition=data.get('definition', ''),
            attributes={
                "pos": data.get('pos', ''),
                "examples": data.get('examples', []),
                "lemmas": data.get('lemmas', []),
                "lexfile": data.get('lexfile', ''),
                "offset": data.get('offset'),
                **self._extract_base_attributes(data)
            },
            source_url=f"http://wordnetweb.princeton.edu/perl/webwn?s={synset_name}",
            confidence_score=1.0
        )

    def transform_relation_to_link(self, source_synset: str, relation: Dict) -> UnifiedLink:
        """Transform WordNet semantic relation to unified link"""
        relation_type = relation.get('relation_type', '')
        target_synset = relation.get('target_synset', {})
        target_synset_name = target_synset.get('name', '')

        return UnifiedLink(
            id=self._generate_id(f"{source_synset}-{relation_type}-{target_synset_name}"),
            source=ReferenceSource.WORDNET,
            subject=self._generate_id(source_synset),
            predicate=relation_type,
            object=self._generate_id(target_synset_name),
            weight=1.0,
            attributes={
                "relation_type": relation_type,
                "target_pos": target_synset.get('pos', ''),
                "target_definition": target_synset.get('definition', ''),
                **self._extract_base_attributes(relation)
            }
        )

    def transform_link(self, data: Dict) -> UnifiedLink:
        """Transform WordNet relationship to unified link"""
        subject = data.get('subject', '')
        predicate = data.get('predicate', '')
        obj = data.get('object', '')

        return UnifiedLink(
            id=self._generate_id(f"{subject}-{predicate}-{obj}"),
            source=ReferenceSource.WORDNET,
            subject=self._generate_id(subject),
            predicate=predicate,
            object=self._generate_id(obj),
            weight=1.0,
            attributes=self._extract_base_attributes(data)
        )