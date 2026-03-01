"""Result normalization utilities for reference service.

This module provides normalization logic to convert source-specific responses
into standardized SearchNode and SearchLink objects.
"""

from typing import List, Tuple

from .models import (
    SourceType, SearchNode, SearchLink,
    DBpediaSearchResponse, ConceptNetQueryResponse, WikidataSparqlResponse, SchemaOrgSearchResponse,
    DBpediaResourceResponse, DBpediaSparqlResponse, WikidataEntityResponse, SchemaOrgEntityResponse,
    ConceptNetConceptResponse, ConceptNetRelatedResponse, SchemaOrgPropertyResponse
)
from utils.logger import get_logger

logger = get_logger(__name__)


class ResultNormalizer:
    """Normalizes source-specific responses to standardized SearchNode and SearchLink format."""

    def __init__(self, settings):
        self.settings = settings
        self.default_language = settings.reference_sources.default_language

    def normalize_dbpedia_search_response(self, response: DBpediaSearchResponse, query: str = "") -> Tuple[List[SearchNode], List[SearchLink]]:
        """Normalize DBpedia search response to SearchNode format."""
        if not response.success or not response.results:
            return [], []

        # Normalize DBpedia scores to 0-1 range
        max_score = max((result.score for result in response.results), default=1.0)

        nodes = [
            SearchNode(
                id=f"dbpedia:{result.uri}",
                source=SourceType.DBPEDIA,
                title=result.label,
                definition=result.description,
                attributes={
                    "types": result.types,
                    "uri": result.uri,
                    "raw_score": result.score
                },
                source_url=result.uri,
                relevance_score=min(result.score / max_score, 1.0) if max_score > 0 else 1.0
            )
            for result in response.results
        ]

        # DBpedia search doesn't inherently provide relationship data
        return nodes, []

    def normalize_dbpedia_resource_response(self, response: DBpediaResourceResponse, query: str = "") -> Tuple[List[SearchNode], List[SearchLink]]:
        """Normalize DBpedia resource response to SearchNode format."""
        if not response.success or not response.resource_uri:
            return [], []

        # Extract basic info from the resource data
        data = response.data or {}
        title = response.resource_uri.split('/')[-1].replace('_', ' ')
        definition = None

        # Try to extract title and definition from the data
        if isinstance(data, dict):
            # Look for common DBpedia properties
            for key, value in data.items():
                if 'label' in key.lower() and isinstance(value, list) and value:
                    title = value[0].get('value', title) if isinstance(value[0], dict) else str(value[0])
                elif 'abstract' in key.lower() and isinstance(value, list) and value:
                    definition = value[0].get('value', None) if isinstance(value[0], dict) else str(value[0])

        node = SearchNode(
            id=f"dbpedia:{response.resource_uri}",
            source=SourceType.DBPEDIA,
            title=title,
            definition=definition,
            attributes={
                "uri": response.resource_uri,
                "data_url": response.data_url,
                "raw_data": data
            },
            source_url=response.resource_uri,
            relevance_score=1.0
        )

        return [node], []

    def normalize_dbpedia_sparql_response(self, response: DBpediaSparqlResponse, query: str = "") -> Tuple[List[SearchNode], List[SearchLink]]:
        """Normalize DBpedia SPARQL response to SearchNode and SearchLink format."""
        if not response.success or not response.results:
            return [], []

        nodes = []
        links = []
        seen_entities = set()

        # Parse SPARQL results
        if isinstance(response.results, dict) and 'results' in response.results:
            bindings = response.results.get('results', {}).get('bindings', [])

            for binding in bindings:
                # Extract entity information
                if 'item' in binding:
                    item_uri = binding['item'].get('value', '')
                    if item_uri and item_uri not in seen_entities:
                        seen_entities.add(item_uri)

                        label = binding.get('itemLabel', {}).get('value', item_uri.split('/')[-1])
                        description = binding.get('itemDescription', {}).get('value', '')

                        nodes.append(SearchNode(
                            id=f"dbpedia:{item_uri}",
                            source=SourceType.DBPEDIA,
                            title=label,
                            definition=description,
                            attributes={"uri": item_uri},
                            source_url=item_uri,
                            relevance_score=1.0
                        ))

        return nodes, links

    def normalize_conceptnet_query_response(self, response: ConceptNetQueryResponse, query: str = "") -> Tuple[List[SearchNode], List[SearchLink]]:
        """Normalize ConceptNet query response to SearchNode and SearchLink format."""
        if not response.success or not response.edges:
            return [], []

        nodes = []
        links = []
        seen_nodes = set()

        for edge in response.edges:
            # Extract start node (only configured language concepts)
            if edge.start and edge.start.get('@id'):
                start_id = edge.start['@id']
                if f'/c/{self.default_language}/' in start_id and start_id not in seen_nodes:
                    seen_nodes.add(start_id)
                    nodes.append(SearchNode(
                        id=f"conceptnet:{start_id}",
                        source=SourceType.CONCEPTNET,
                        title=edge.start.get('label', start_id.split('/')[-1]),
                        definition=None,  # ConceptNet doesn't provide definitions
                        attributes={
                            "language": self.default_language,
                            "concept_uri": start_id
                        },
                        source_url=f"http://conceptnet.io{start_id}",
                        relevance_score=min(edge.weight, 1.0)
                    ))

            # Extract end node (only configured language concepts)
            if edge.end and edge.end.get('@id'):
                end_id = edge.end['@id']
                if f'/c/{self.default_language}/' in end_id and end_id not in seen_nodes:
                    seen_nodes.add(end_id)
                    nodes.append(SearchNode(
                        id=f"conceptnet:{end_id}",
                        source=SourceType.CONCEPTNET,
                        title=edge.end.get('label', end_id.split('/')[-1]),
                        definition=None,  # ConceptNet doesn't provide definitions
                        attributes={
                            "language": self.default_language,
                            "concept_uri": end_id
                        },
                        source_url=f"http://conceptnet.io{end_id}",
                        relevance_score=min(edge.weight, 1.0)
                    ))

            # Create link
            if edge.start and edge.end and edge.rel:
                # Handle ExternalURL relations specially
                if edge.rel.get('@id') == '/r/ExternalURL':
                    end_url = edge.end.get('@id', '')

                    if end_url and any(domain in end_url for domain in ['dbpedia.org', 'wikidata.org']):
                        # Determine the target source type
                        if 'dbpedia.org' in end_url:
                            target_source = SourceType.DBPEDIA
                            target_id = f"dbpedia:{end_url}"
                        elif 'wikidata.org' in end_url or 'wikidata.dbpedia.org' in end_url:
                            target_source = SourceType.WIKIDATA
                            # Extract Wikidata Q-ID
                            if '/Q' in end_url:
                                q_id = end_url.split('/Q')[-1].rstrip('/')
                                target_id = f"wikidata:http://www.wikidata.org/entity/Q{q_id}"
                            else:
                                target_id = f"wikidata:{end_url}"
                        else:
                            continue  # Skip other domains for now

                        # Create external reference link
                        links.append(SearchLink(
                            id=f"conceptnet_external:{edge.start['@id']}:{end_url}",
                            source=SourceType.CONCEPTNET,
                            subject=f"conceptnet:{edge.start['@id']}",
                            predicate="externalURL",
                            object=target_id,
                            weight=1.0,
                            attributes={
                                "link_type": "external_reference",
                                "external_url": end_url,
                                "target_source": target_source.value,
                                "source_dataset": getattr(edge, 'dataset', '')
                            }
                        ))
                else:
                    # Regular ConceptNet relation
                    links.append(SearchLink(
                        id=f"conceptnet:{edge.id}",
                        source=SourceType.CONCEPTNET,
                        subject=f"conceptnet:{edge.start['@id']}",
                        predicate=edge.rel.get('label', edge.rel.get('@id', '')),
                        object=f"conceptnet:{edge.end['@id']}",
                        weight=edge.weight,
                        attributes={
                            "edge_uri": edge.id,
                            "relation_uri": edge.rel.get('@id', ''),
                            "sources": edge.sources or []
                        }
                    ))

        return nodes, links

    def normalize_conceptnet_concept_response(self, response: ConceptNetConceptResponse, query: str = "") -> Tuple[List[SearchNode], List[SearchLink]]:
        """Normalize ConceptNet concept response to SearchNode format."""
        if not response.success or not response.concept:
            return [], []

        # Extract concept information
        concept_id = response.concept
        title = concept_id.split('/')[-1].replace('_', ' ')

        # Try to extract additional info from data
        data = response.data or {}
        if isinstance(data, dict):
            # Look for label or other descriptive fields
            title = data.get('label', title)

        node = SearchNode(
            id=f"conceptnet:{concept_id}",
            source=SourceType.CONCEPTNET,
            title=title,
            definition=None,  # ConceptNet concepts don't have definitions
            attributes={
                "language": self.default_language,
                "concept_uri": concept_id,
                "raw_data": data
            },
            source_url=f"http://conceptnet.io{concept_id}",
            relevance_score=1.0
        )

        return [node], []

    def normalize_conceptnet_related_response(self, response: ConceptNetRelatedResponse, query: str = "") -> Tuple[List[SearchNode], List[SearchLink]]:
        """Normalize ConceptNet related concepts response to SearchNode format."""
        if not response.success or not response.related:
            return [], []

        nodes = [
            SearchNode(
                id=f"conceptnet:{concept.id}",
                source=SourceType.CONCEPTNET,
                title=concept.label,
                definition=None,  # ConceptNet doesn't provide definitions
                attributes={
                    "language": self.default_language,
                    "concept_uri": concept.id
                },
                source_url=f"http://conceptnet.io{concept.id}",
                relevance_score=min(concept.weight, 1.0)
            )
            for concept in response.related
        ]

        return nodes, []

    def normalize_wikidata_sparql_response(self, response: WikidataSparqlResponse, query: str = "") -> Tuple[List[SearchNode], List[SearchLink]]:
        """Normalize Wikidata SPARQL response to SearchNode and SearchLink format."""
        if not response.success or not response.results:
            return [], []

        nodes = []
        links = []
        seen_entities = set()
        seen_objects = set()

        if 'results' in response.results and 'bindings' in response.results['results']:
            for binding in response.results['results']['bindings']:
                # Process main entity
                if 'item' in binding:
                    item_uri = binding['item'].get('value', '')
                    if item_uri not in seen_entities:
                        seen_entities.add(item_uri)
                        label = binding.get('itemLabel', {}).get('value', item_uri.split('/')[-1])
                        description = binding.get('itemDescription', {}).get('value', '')
                        nodes.append(SearchNode(
                            id=f"wikidata:{item_uri}",
                            source=SourceType.WIKIDATA,
                            title=label,
                            definition=description,
                            attributes={"uri": item_uri},
                            source_url=item_uri,
                            relevance_score=1.0
                        ))

                # Process statements (if present)
                if all(key in binding for key in ['item', 'property', 'object']):
                    subject_uri = binding['item'].get('value', '')
                    property_uri = binding['property'].get('value', '')
                    object_uri = binding['object'].get('value', '')

                    # Extract property ID from URI for cleaner predicate
                    property_id = property_uri.split('/')[-1] if property_uri else ''
                    property_label = binding.get('propertyLabel', {}).get('value', property_id)

                    # Add object entity as a node if not already present
                    object_label = binding.get('objectLabel', {}).get('value', object_uri.split('/')[-1])
                    object_node_id = f"wikidata:{object_uri}"

                    if object_uri not in seen_objects:
                        seen_objects.add(object_uri)
                        # Detect and handle file URLs (images, documents, etc.)
                        title = object_label
                        attributes = {"uri": object_uri}

                        if object_uri and any(domain in object_uri for domain in ['commons.wikimedia.org', 'upload.wikimedia.org']):
                            # This is likely a file URL
                            file_path = object_uri.split('/')[-1] if '/' in object_uri else object_uri

                            # Determine file type from extension or path
                            if any(ext in file_path.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp']):
                                title = "image file"
                                attributes["file_type"] = "image"
                            elif any(ext in file_path.lower() for ext in ['.pdf', '.doc', '.docx', '.txt']):
                                title = "document file"
                                attributes["file_type"] = "document"
                            elif any(ext in file_path.lower() for ext in ['.mp3', '.wav', '.ogg', '.mp4', '.avi']):
                                title = "media file"
                                attributes["file_type"] = "media"
                            else:
                                title = "file"
                                attributes["file_type"] = "unknown"

                            attributes["file_url"] = object_uri
                            attributes["file_name"] = file_path

                        nodes.append(SearchNode(
                            id=object_node_id,
                            source=SourceType.WIKIDATA,
                            title=title,
                            definition=None,  # Would need additional query for description
                            attributes=attributes,
                            source_url=object_uri,
                            relevance_score=0.8  # Lower relevance for inferred objects
                        ))

                    # Create the link
                    links.append(SearchLink(
                        id=f"wikidata:{subject_uri}#{property_id}#{object_uri}",
                        source=SourceType.WIKIDATA,
                        subject=f"wikidata:{subject_uri}",
                        predicate=property_label or property_id,
                        object=object_node_id,
                        weight=1.0,  # Wikidata statements are factual
                        attributes={
                            "property_uri": property_uri,
                            "property_id": property_id,
                            "statement_type": "direct"
                        }
                    ))

        return nodes, links

    def normalize_wikidata_entity_response(self, response: WikidataEntityResponse, query: str = "") -> Tuple[List[SearchNode], List[SearchLink]]:
        """Normalize Wikidata entity response to SearchNode format."""
        if not response.success or not response.entity_id:
            return [], []

        # Extract basic information
        entity_id = response.entity_id
        entity_url = response.entity_url or f"http://www.wikidata.org/entity/{entity_id}"

        # Try to extract title and description from data
        data = response.data or {}
        title = entity_id
        definition = None

        if isinstance(data, dict):
            # Look for labels and descriptions
            labels = data.get('labels', {})
            descriptions = data.get('descriptions', {})

            # Try to get label in configured language
            if self.default_language in labels:
                title = labels[self.default_language].get('value', title)
            elif 'en' in labels:  # Fallback to English
                title = labels['en'].get('value', title)

            # Try to get description in configured language
            if self.default_language in descriptions:
                definition = descriptions[self.default_language].get('value', None)
            elif 'en' in descriptions:  # Fallback to English
                definition = descriptions['en'].get('value', None)

        node = SearchNode(
            id=f"wikidata:{entity_url}",
            source=SourceType.WIKIDATA,
            title=title,
            definition=definition,
            attributes={
                "entity_id": entity_id,
                "uri": entity_url,
                "raw_data": data
            },
            source_url=entity_url,
            relevance_score=1.0
        )

        return [node], []

    def normalize_schema_org_search_response(self, response: SchemaOrgSearchResponse, query: str = "") -> Tuple[List[SearchNode], List[SearchLink]]:
        """Normalize Schema.org search response to SearchNode format."""
        if not response.success or not response.results:
            return [], []

        nodes = [
            SearchNode(
                id=f"schema_org:{result.identifier}",
                source=SourceType.SCHEMA_ORG,
                title=result.title,
                definition=result.definition,
                attributes={
                    "type": result.type,
                    "identifier": result.identifier
                },
                source_url=f"https://schema.org/{result.identifier}",
                relevance_score=result.relevance_score
            )
            for result in response.results
        ]

        # Schema.org search doesn't inherently provide relationship data
        return nodes, []

    def normalize_schema_org_entity_response(self, response: SchemaOrgEntityResponse, query: str = "") -> Tuple[List[SearchNode], List[SearchLink]]:
        """Normalize Schema.org entity response to SearchNode format."""
        if not response.success or not response.entity:
            return [], []

        entity = response.entity
        node = SearchNode(
            id=f"schema_org:{entity.identifier}",
            source=SourceType.SCHEMA_ORG,
            title=entity.title,
            definition=entity.definition,
            attributes={
                "identifier": entity.identifier,
                "parent_identifier": entity.parent_identifier,
                "properties": [prop.dict() for prop in entity.properties],
                "children": [child.dict() for child in entity.children]
            },
            source_url=f"https://schema.org/{entity.identifier}",
            relevance_score=1.0
        )

        return [node], []

    def normalize_schema_org_property_response(self, response: SchemaOrgPropertyResponse, query: str = "") -> Tuple[List[SearchNode], List[SearchLink]]:
        """Normalize Schema.org property response to SearchNode format."""
        if not response.success or not response.property:
            return [], []

        prop = response.property
        node = SearchNode(
            id=f"schema_org:{prop.identifier}",
            source=SourceType.SCHEMA_ORG,
            title=prop.title,
            definition=prop.definition,
            attributes={
                "identifier": prop.identifier,
                "domain_includes": prop.domain_includes,
                "range_includes": prop.range_includes,
                "inverse_of": prop.inverse_of,
                "used_by_entities": prop.used_by_entities
            },
            source_url=f"https://schema.org/{prop.identifier}",
            relevance_score=1.0
        )

        return [node], []