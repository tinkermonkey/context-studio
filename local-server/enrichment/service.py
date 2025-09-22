"""Core enrichment service coordinating all reference API sources"""

from typing import Dict, Any, Optional, List, Tuple
import asyncio
from datetime import datetime, UTC

from config import get_config_manager, ConfigurationManager
from .exceptions import EnrichmentError
from .models import *
import time
from .sources import DBpediaSource, ConceptNetSource, WikidataSource, SchemaOrgSource
from utils.logger import get_logger

logger = get_logger(__name__)


class EnrichmentService:
    """Core enrichment service coordinating all reference API sources"""

    def __init__(self, config_manager: ConfigurationManager = None):
        self.config_manager = config_manager or get_config_manager()
        self.settings = self.config_manager.settings
        self._sources = {}  # Cache for source instances

    def _get_source(self, source_type: SourceType):
        """Get or create source instance"""
        if source_type not in self._sources:
            source_config = self.settings.get_source_config(source_type.value)

            if source_type == SourceType.DBPEDIA:
                self._sources[source_type] = DBpediaSource(source_type, source_config)
            elif source_type == SourceType.CONCEPTNET:
                self._sources[source_type] = ConceptNetSource(source_type, source_config)
            elif source_type == SourceType.WIKIDATA:
                self._sources[source_type] = WikidataSource(source_type, source_config)
            elif source_type == SourceType.SCHEMA_ORG:
                self._sources[source_type] = SchemaOrgSource(source_type, source_config)
            else:
                raise EnrichmentError(f"Unknown source type: {source_type}")

        return self._sources[source_type]

    # DBpedia methods
    async def dbpedia_get_resource(self, request: DBpediaResourceRequest) -> DBpediaResourceResponse:
        """Get DBpedia resource data"""
        source = self._get_source(SourceType.DBPEDIA)
        async with source:
            return await source.get_resource_data(request.resource_url, request.format.value)

    async def dbpedia_search(self, request: DBpediaSearchRequest) -> DBpediaSearchResponse:
        """Search DBpedia"""
        source = self._get_source(SourceType.DBPEDIA)
        async with source:
            return await source.search(request.query, request.limit, request.offset, request.format.value)

    async def dbpedia_sparql(self, request: DBpediaSparqlRequest) -> DBpediaSparqlResponse:
        """Execute DBpedia SPARQL query"""
        source = self._get_source(SourceType.DBPEDIA)
        async with source:
            return await source.sparql_query(request.query, request.format.value)

    # ConceptNet methods
    async def conceptnet_query(self, request: ConceptNetQueryRequest) -> ConceptNetQueryResponse:
        """Query ConceptNet"""
        source = self._get_source(SourceType.CONCEPTNET)
        async with source:
            return await source.query(
                start=request.start,
                end=request.end,
                node=request.node,
                rel=request.rel,
                limit=request.limit,
                offset=request.offset,
            )

    async def conceptnet_get_concept(self, concept_path: str) -> ConceptNetConceptResponse:
        """Get ConceptNet concept"""
        source = self._get_source(SourceType.CONCEPTNET)
        async with source:
            return await source.get_concept(concept_path)

    async def conceptnet_get_related(self, concept_path: str, filter: Optional[str] = None, limit: int = 20) -> ConceptNetRelatedResponse:
        """Get ConceptNet related concepts"""
        source = self._get_source(SourceType.CONCEPTNET)
        async with source:
            return await source.get_related(concept_path, filter, limit)

    # Wikidata methods
    async def wikidata_sparql(self, request: WikidataSparqlRequest) -> WikidataSparqlResponse:
        """Execute Wikidata SPARQL query"""
        source = self._get_source(SourceType.WIKIDATA)
        async with source:
            return await source.sparql_query(request.query, request.format.value)

    async def wikidata_get_entity(self, request: WikidataEntityRequest) -> WikidataEntityResponse:
        """Get Wikidata entity data"""
        source = self._get_source(SourceType.WIKIDATA)
        async with source:
            return await source.get_entity_data(request.entity_url, request.properties, request.format.value)

    # Schema.org methods
    async def schema_org_get_entity(self, request: SchemaOrgEntityRequest) -> SchemaOrgEntityResponse:
        """Get Schema.org entity"""
        source = self._get_source(SourceType.SCHEMA_ORG)
        async with source:
            return await source.get_entity(request.identifier, request.include_inherited, request.include_children)

    async def schema_org_get_property(self, request: SchemaOrgPropertyRequest) -> SchemaOrgPropertyResponse:
        """Get Schema.org property"""
        source = self._get_source(SourceType.SCHEMA_ORG)
        async with source:
            return await source.get_property(request.identifier, request.include_usage)

    async def schema_org_search(self, request: SchemaOrgSearchRequest) -> SchemaOrgSearchResponse:
        """Search Schema.org entities and properties"""
        source = self._get_source(SourceType.SCHEMA_ORG)
        async with source:
            return await source.search(
                query=request.query,
                search_type=request.search_type,
                limit=request.limit,
                offset=request.offset,
                similarity_threshold=request.similarity_threshold,
            )

    # Multi-source search method
    async def search(self, request: MultiSourceSearchRequest) -> MultiSourceSearchResponse:
        """
        Search across multiple reference sources

        Args:
            request: Multi-source search request

        Returns:
            Aggregated search results from all requested sources
        """
        start_time = time.time()
        logger.info(f"Starting multi-source search for query: '{request.query}'")

        # Determine which sources to query
        sources_to_query = request.sources or [
            SourceType.DBPEDIA,
            SourceType.CONCEPTNET,
            SourceType.WIKIDATA,
            SourceType.SCHEMA_ORG
        ]

        # Filter to only enabled sources
        enabled_sources = []
        for source_type in sources_to_query:
            try:
                # Check if source is enabled in configuration
                source_config = self.settings.get_source_config(source_type.value)
                if source_config.enabled:
                    enabled_sources.append(source_type)
                else:
                    logger.debug(f"Skipping disabled source: {source_type.value}")
            except Exception as e:
                logger.warning(f"Error checking source {source_type.value}: {e}")

        search_timeout = self.settings.reference_sources.search_timeout
        logger.info(f"Querying {len(enabled_sources)} enabled sources: {[s.value for s in enabled_sources]} (timeout: {search_timeout}s)")

        # Search each source in parallel
        search_tasks = []
        for source_type in enabled_sources:
            task = self._search_single_source(source_type, request.query, request.limit, request.offset)
            search_tasks.append((source_type, task))

        # Execute all searches in parallel
        results = await self._gather_search_results(search_tasks, search_timeout)

        # Aggregate results with deduplication
        all_nodes = []
        all_links = []
        source_errors = {}
        sources_queried = []
        seen_node_ids = set()
        seen_link_ids = set()

        for source_type, result in results:
            sources_queried.append(source_type.value)

            if isinstance(result, Exception):
                source_errors[source_type.value] = str(result)
                logger.warning(f"Search failed for {source_type.value}: {result}")
            elif result:
                nodes, links = result

                # Deduplicate nodes by ID
                unique_nodes = []
                for node in nodes:
                    if node.id not in seen_node_ids:
                        seen_node_ids.add(node.id)
                        unique_nodes.append(node)

                # Deduplicate links by ID and filter to only include links between nodes in our results
                unique_links = []
                for link in links:
                    if link.id not in seen_link_ids:
                        # Only include links where both subject and object nodes are in our results
                        if link.subject in seen_node_ids and link.object in seen_node_ids:
                            seen_link_ids.add(link.id)
                            unique_links.append(link)

                all_nodes.extend(unique_nodes)
                all_links.extend(unique_links)
                logger.info(f"Source {source_type.value}: added {len(unique_nodes)} unique nodes and {len(unique_links)} unique links (filtered from {len(nodes)} nodes, {len(links)} links)")
            else:
                logger.info(f"Source {source_type.value}: no results")

        # Simple result aggregation (no deduplication or ranking)
        total_results = len(all_nodes)
        total_links = len(all_links)

        # Create response
        search_time_ms = (time.time() - start_time) * 1000
        response = MultiSourceSearchResponse(
            query=request.query,
            results=all_nodes,
            links=all_links,
            total_results=total_results,
            total_links=total_links,
            sources_queried=sources_queried,
            source_errors=source_errors,
            offset=request.offset,
            limit=request.limit,
            search_time_ms=search_time_ms
        )

        # Post-process to discover cross-references between sources
        cross_links = self._discover_cross_references(all_nodes)

        # Filter cross-links to ensure both nodes exist in our results
        filtered_cross_links = []
        for cross_link in cross_links:
            if cross_link.subject in seen_node_ids and cross_link.object in seen_node_ids:
                if cross_link.id not in seen_link_ids:
                    seen_link_ids.add(cross_link.id)
                    filtered_cross_links.append(cross_link)

        all_links.extend(filtered_cross_links)
        total_links = len(all_links)

        # Update response with cross-links
        response.links = all_links
        response.total_links = total_links

        logger.info(f"Multi-source search completed: '{request.query}' returned {total_results} nodes, {total_links} links ({len(cross_links)} cross-references) in {search_time_ms:.2f}ms")
        return response

    async def _search_single_source(self, source_type: SourceType, query: str, limit: int, offset: int) -> Tuple[List[SearchNode], List[SearchLink]]:
        """Search a single source and convert results to SearchNode and SearchLink format"""
        try:
            logger.debug(f"Searching {source_type.value} for '{query}'")

            if source_type == SourceType.DBPEDIA:
                # Note: DBpedia Lookup API currently only supports English
                # Using the configurable language for future compatibility
                default_language = self.settings.reference_sources.default_language
                if default_language != "en":
                    logger.warning(f"DBpedia Lookup API only supports English, but configured language is '{default_language}'")

                request = DBpediaSearchRequest(query=query, limit=limit, offset=offset)
                response = await self.dbpedia_search(request)
                # Normalize DBpedia scores to 0-1 range
                max_score = max((result.score for result in response.results), default=1.0)
                nodes = [
                    SearchNode(
                        id=f"dbpedia:{result.uri}",
                        source=SourceType.DBPEDIA,
                        title=result.label,
                        definition=result.description,
                        attributes={"types": result.types, "uri": result.uri, "raw_score": result.score},
                        source_url=result.uri,
                        relevance_score=min(result.score / max_score, 1.0)
                    )
                    for result in response.results
                ]
                # DBpedia search doesn't inherently provide relationship data, return empty links
                return nodes, []

            elif source_type == SourceType.CONCEPTNET:
                # Use higher limit to capture ExternalURL relations in single request
                extended_limit = min(max(limit * 3, 50), 100)  # Increase limit but respect ConceptNet's max of 100
                # Use configurable language for consistent results
                default_language = self.settings.reference_sources.default_language
                request = ConceptNetQueryRequest(node=f"/c/{default_language}/{query.lower().replace(' ', '_')}", limit=extended_limit, offset=offset)
                response = await self.conceptnet_query(request)
                nodes = []
                links = []
                seen_nodes = set()

                for edge in response.edges:
                    # Extract start node (only configured language concepts)
                    if edge.start and edge.start.get('@id'):
                        start_id = edge.start['@id']
                        # Only include concepts in the configured language
                        if f'/c/{default_language}/' in start_id and start_id not in seen_nodes:
                            seen_nodes.add(start_id)
                            nodes.append(SearchNode(
                                id=f"conceptnet:{start_id}",
                                source=SourceType.CONCEPTNET,
                                title=edge.start.get('label', start_id.split('/')[-1]),
                                definition=None,  # ConceptNet doesn't provide definitions
                                attributes={
                                    "language": default_language,
                                    "concept_uri": start_id
                                },
                                source_url=f"http://conceptnet.io{start_id}",
                                relevance_score=min(edge.weight, 1.0)
                            ))

                    # Extract end node (only configured language concepts)
                    if edge.end and edge.end.get('@id'):
                        end_id = edge.end['@id']
                        # Only include concepts in the configured language
                        if f'/c/{default_language}/' in end_id and end_id not in seen_nodes:
                            seen_nodes.add(end_id)
                            nodes.append(SearchNode(
                                id=f"conceptnet:{end_id}",
                                source=SourceType.CONCEPTNET,
                                title=edge.end.get('label', end_id.split('/')[-1]),
                                definition=None,  # ConceptNet doesn't provide definitions
                                attributes={
                                    "language": default_language,
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
                                    continue  # Skip WordNet and others for now

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
                                        "source_dataset": edge.get('dataset', '')
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

                # If we didn't find external URLs in the main query, fetch them separately
                external_url_count = len([link for link in links if link.predicate == "externalURL"])
                if external_url_count == 0 and seen_nodes:
                    external_links = await self._fetch_conceptnet_external_urls(seen_nodes)
                    links.extend(external_links)

                return nodes, links

            elif source_type == SourceType.WIKIDATA:
                # Optimized single-query Wikidata search to include both entities and their statements
                # Escape query string to prevent SPARQL injection
                escaped_query = query.replace('"', '\\"').replace('\n', ' ').replace('\r', ' ')
                default_language = self.settings.reference_sources.default_language

                # Single combined query: Find entities and their statements in one request (configurable language)
                combined_sparql = f"""
                SELECT ?item ?itemLabel ?itemDescription ?property ?propertyEntity ?propertyLabel ?object ?objectLabel WHERE {{
                  # Find entities matching the search term (configurable language labels only)
                  ?item rdfs:label "{escaped_query}"@{default_language} .

                  # Optionally get their statements (using OPTIONAL to still return entities without statements)
                  OPTIONAL {{
                    ?item ?property ?object .
                    # Filter to actual properties (not schema/system properties)
                    FILTER(STRSTARTS(STR(?property), "http://www.wikidata.org/prop/direct/"))
                    # Only include object entities (not literals) to create meaningful links
                    FILTER(ISIRI(?object))
                    # Convert direct property URI to property entity URI for label resolution
                    BIND(IRI(REPLACE(STR(?property), "http://www.wikidata.org/prop/direct/", "http://www.wikidata.org/entity/")) AS ?propertyEntity)
                  }}

                  SERVICE wikibase:label {{
                    bd:serviceParam wikibase:language "{default_language}" .
                    ?item rdfs:label ?itemLabel .
                    ?item schema:description ?itemDescription .
                    ?propertyEntity rdfs:label ?propertyLabel .
                    ?object rdfs:label ?objectLabel .
                  }}
                  # Filter to prefer configured language content where possible
                  FILTER(lang(?itemLabel) = "{default_language}" || lang(?itemLabel) = "")
                }}
                LIMIT {min(limit * 3, 30)}
                OFFSET {offset}
                """

                request = WikidataSparqlRequest(query=combined_sparql)
                response = await self.wikidata_sparql(request)

                nodes = []
                links = []
                seen_entities = set()
                seen_objects = set()

                if response.success and response.results and 'results' in response.results and 'bindings' in response.results['results']:
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

            elif source_type == SourceType.SCHEMA_ORG:
                # Schema.org is primarily English by design
                request = SchemaOrgSearchRequest(query=query, limit=limit, offset=offset)
                response = await self.schema_org_search(request)
                nodes = [
                    SearchNode(
                        id=f"schema_org:{result.identifier}",
                        source=SourceType.SCHEMA_ORG,
                        title=result.title,
                        definition=result.definition,
                        attributes={"type": result.type, "identifier": result.identifier},
                        source_url=f"https://schema.org/{result.identifier}",
                        relevance_score=result.relevance_score
                    )
                    for result in response.results
                ]
                # Schema.org search doesn't inherently provide relationship data, return empty links
                return nodes, []

            else:
                logger.warning(f"Unknown source type: {source_type}")
                return [], []

        except Exception as e:
            logger.error(f"Error searching {source_type.value}: {e}")
            raise e

    async def _gather_search_results(self, search_tasks: List[tuple], search_timeout: int) -> List[tuple]:
        """Execute search tasks in parallel and gather results"""
        results = []

        # Extract tasks for parallel execution
        task_coroutines = [task for _, task in search_tasks]
        sources = [source for source, _ in search_tasks]

        try:
            # Run all tasks in parallel with configurable timeout
            completed_results = await asyncio.wait_for(
                asyncio.gather(*task_coroutines, return_exceptions=True),
                timeout=search_timeout
            )

            # Pair results back with sources
            for source, result in zip(sources, completed_results):
                results.append((source, result))

        except asyncio.TimeoutError:
            # Handle timeout - some sources may not have responded
            logger.warning("Some sources timed out during search")
            for source in sources:
                results.append((source, TimeoutError("Search timeout")))
        except Exception as e:
            logger.error(f"Error in parallel search execution: {e}")
            for source in sources:
                results.append((source, e))

        return results

    def _discover_cross_references(self, nodes: List[SearchNode]) -> List[SearchLink]:
        """
        Discover cross-references between nodes from different sources based on title matching.
        Creates 'sameAs' links when nodes from different sources likely refer to the same concept.
        """
        cross_links = []

        # Group nodes by normalized title for matching
        title_groups = {}
        for node in nodes:
            # Normalize title for matching (lowercase, remove common variations)
            normalized_title = self._normalize_title(node.title)
            if normalized_title not in title_groups:
                title_groups[normalized_title] = []
            title_groups[normalized_title].append(node)

        # Find groups with nodes from multiple sources
        for normalized_title, matching_nodes in title_groups.items():
            if len(matching_nodes) < 2:
                continue

            # Group by source
            sources_present = {}
            for node in matching_nodes:
                if node.source not in sources_present:
                    sources_present[node.source] = []
                sources_present[node.source].append(node)

            # Only create cross-references between different sources
            if len(sources_present) < 2:
                continue

            # Create cross-reference links between nodes from different sources
            source_pairs = []
            sources = list(sources_present.keys())
            for i in range(len(sources)):
                for j in range(i + 1, len(sources)):
                    source_pairs.append((sources[i], sources[j]))

            for source1, source2 in source_pairs:
                nodes1 = sources_present[source1]
                nodes2 = sources_present[source2]

                # Create links between the best matching nodes from each source
                for node1 in nodes1[:1]:  # Take best match from each source
                    for node2 in nodes2[:1]:
                        # Calculate confidence based on title similarity
                        confidence = self._calculate_title_similarity(node1.title, node2.title)

                        if confidence >= 0.8:  # High confidence threshold for cross-references
                            cross_links.append(SearchLink(
                                id=f"cross_ref:{node1.source.value}:{node2.source.value}:{hash(node1.id + node2.id)}",
                                source=SourceType.CONCEPTNET,  # Use ConceptNet as the source for cross-references
                                subject=node1.id,
                                predicate="sameAs",
                                object=node2.id,
                                weight=confidence,
                                attributes={
                                    "link_type": "cross_reference",
                                    "confidence": confidence,
                                    "matching_title": normalized_title,
                                    "source1": node1.source.value,
                                    "source2": node2.source.value
                                }
                            ))

        return cross_links

    def _normalize_title(self, title: str) -> str:
        """Normalize title for cross-reference matching"""
        if not title:
            return ""

        # Convert to lowercase and strip whitespace
        normalized = title.lower().strip()

        # Remove common variations and articles
        normalized = normalized.replace("the ", "").replace("a ", "").replace("an ", "")

        # Handle file extensions for file nodes
        if normalized in ["image file", "document file", "media file", "file"]:
            return normalized

        # Remove parenthetical content that might differ between sources
        import re
        normalized = re.sub(r'\([^)]*\)', '', normalized).strip()

        return normalized

    def _calculate_title_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between two titles (0.0 to 1.0)"""
        if not title1 or not title2:
            return 0.0

        title1_norm = self._normalize_title(title1)
        title2_norm = self._normalize_title(title2)

        if title1_norm == title2_norm:
            return 1.0

        # Use simple character-based similarity for now
        # Could be enhanced with more sophisticated matching
        shorter = min(len(title1_norm), len(title2_norm))
        longer = max(len(title1_norm), len(title2_norm))

        if longer == 0:
            return 1.0 if shorter == 0 else 0.0

        # Count matching characters
        matches = sum(1 for i in range(min(len(title1_norm), len(title2_norm)))
                     if title1_norm[i] == title2_norm[i])

        return matches / longer

    async def _fetch_conceptnet_external_urls(self, concept_ids: set) -> List[SearchLink]:
        """
        Fetch external URL relations from ConceptNet for the given concept IDs.
        Creates links to DBpedia, Wikidata, WordNet, and other external knowledge bases.
        """
        external_links = []

        # Process a limited number of concepts to avoid too many API calls
        limited_concepts = list(concept_ids)[:5]  # Limit to avoid timeout

        for concept_id in limited_concepts:
            try:
                # Query ConceptNet for ExternalURL relations from this concept
                source = self._get_source(SourceType.CONCEPTNET)
                async with source:
                    # Use the direct ConceptNet API to get external URLs
                    import aiohttp
                    url = "https://api.conceptnet.io/query"
                    params = {
                        "rel": "/r/ExternalURL",
                        "start": concept_id,
                        "limit": 10
                    }

                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, params=params) as response:
                            if response.status == 200:
                                data = await response.json()

                                for edge in data.get('edges', []):
                                    end_url = edge.get('end', {}).get('@id', '')

                                    if end_url and any(domain in end_url for domain in ['dbpedia.org', 'wikidata.org', 'wordnet']):
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
                                            continue  # Skip WordNet and others for now

                                        # Create external reference link
                                        external_links.append(SearchLink(
                                            id=f"conceptnet_external:{concept_id}:{end_url}",
                                            source=SourceType.CONCEPTNET,
                                            subject=f"conceptnet:{concept_id}",
                                            predicate="externalURL",
                                            object=target_id,
                                            weight=1.0,
                                            attributes={
                                                "link_type": "external_reference",
                                                "external_url": end_url,
                                                "target_source": target_source.value,
                                                "source_dataset": edge.get('dataset', '')
                                            }
                                        ))

            except Exception as e:
                logger.warning(f"Error fetching external URLs for {concept_id}: {e}")
                continue

        return external_links

    async def health_check(self) -> Dict[str, Any]:
        """Check health of all configured sources"""
        health_status = {
            "overall": "healthy",
            "sources": {},
            "timestamp": datetime.now(UTC),
            "language_config": {
                "default_language": self.settings.reference_sources.default_language
            }
        }

        for source_type in SourceType:
            source_config = self.settings.get_source_config(source_type.value)
            if source_config.enabled:
                try:
                    source = self._get_source(source_type)
                    # Special-case schema_org: use manager status (synchronous) instead of HTTP HEAD
                    if source_type == SourceType.SCHEMA_ORG and hasattr(source, 'manager'):
                        # run manager.get_status in threadpool to avoid blocking
                        loop = asyncio.get_event_loop()
                        status = await loop.run_in_executor(None, source.manager.get_status)
                        # consider healthy if populated or no errors
                        if status and status.get('is_populated'):
                            health_status['sources'][source_type.value] = 'healthy'
                        else:
                            health_status['sources'][source_type.value] = f"unhealthy: {status}"
                            health_status['overall'] = 'degraded'
                    else:
                        async with source:
                            # For Wikidata, include a User-Agent header to avoid 403 responses
                            headers = {}
                            if source_type == SourceType.WIKIDATA:
                                headers['User-Agent'] = 'ContextStudio/LocalServer (contact: devnull@example.com)'
                            # Perform a simple health check request
                            await source._make_request("HEAD", source._get_base_url(), headers=headers)
                    health_status["sources"][source_type.value] = "healthy"
                except Exception as e:
                    health_status["sources"][source_type.value] = f"unhealthy: {str(e)}"
                    health_status["overall"] = "degraded"
            else:
                health_status["sources"][source_type.value] = "disabled"

        return health_status

    def get_enabled_sources(self) -> List[str]:
        """Get list of enabled enrichment sources"""
        enabled_sources = []
        sources = ["conceptnet", "dbpedia", "dbpedia_spotlight", "wikidata", "schema_org"]
        
        for source_name in sources:
            config = getattr(self.settings.reference_sources, source_name)
            if config.enabled:
                enabled_sources.append(source_name)
                
        return enabled_sources
        
    async def get_source_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all reference sources"""
        status = {}
        for source_name in ["conceptnet", "dbpedia", "dbpedia_spotlight", "wikidata", "schema_org"]:
            config = getattr(self.settings.reference_sources, source_name)
            status[source_name] = {
                "enabled": config.enabled,
                "use_proxy": config.use_proxy,
                "upstream_url": config.upstream_url,
                "timeout": config.timeout,
                "rate_limit": config.rate_limit.requests_per_hour
            }
        return status
