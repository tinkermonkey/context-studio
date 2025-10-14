"""
Predicate discovery service for fetching predicate metadata from external sources.

This module provides functionality to discover and cache predicates from:
- ConceptNet (40 relations)
- DBpedia (760 properties via SPARQL)
- WikiData (10K properties via SPARQL)

All requests go through the existing reference_api infrastructure with
proper rate limiting and caching.
"""

import asyncio
import psutil
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, UTC, date
from uuid import uuid4

from reference_api.sources.conceptnet import ConceptNetSource
from reference_api.sources.dbpedia import DBpediaSource
from reference_api.sources.wikidata import WikidataSource
from reference_api.sources.base import BaseReferenceSource
from reference_db.manager import ReferenceManager
from reference_db.models import ExternalPredicate
from reference_db.config import ReferenceConfig
from embeddings.generate_embeddings import generate_embedding, get_model
from config import SourceType, SourceConfig
from utils.logger import get_logger

logger = get_logger(__name__)

# ConceptNet relation list (40 relations as per documentation)
CONCEPTNET_RELATIONS = [
    "RelatedTo", "FormOf", "IsA", "PartOf", "HasA", "UsedFor", "CapableOf",
    "AtLocation", "Causes", "HasSubevent", "HasFirstSubevent", "HasLastSubevent",
    "HasPrerequisite", "HasProperty", "MotivatedByGoal", "ObstructedBy", "Desires",
    "CreatedBy", "Synonym", "Antonym", "DistinctFrom", "DerivedFrom", "SymbolOf",
    "DefinedAs", "MannerOf", "LocatedNear", "HasContext", "SimilarTo",
    "EtymologicallyRelatedTo", "EtymologicallyDerivedFrom", "CausesDesire", "MadeOf",
    "ReceivesAction", "ExternalURL", "dbpedia", "NotCapableOf", "NotDesires",
    "NotHasProperty", "NotMadeOf", "NotUsedFor"
]

# Batch size calculation constants (in GB)
MEMORY_THRESHOLD_HIGH = 8
MEMORY_THRESHOLD_MEDIUM = 4
MEMORY_THRESHOLD_LOW = 2

# Wikidata pagination chunk size for memory efficiency
WIKIDATA_CHUNK_SIZE = 1000


class PredicateDiscoveryService:
    """
    Service for discovering predicates from external knowledge sources.

    This service:
    - Fetches predicate metadata from ConceptNet, DBpedia, and WikiData
    - Generates embeddings for semantic search
    - Stores predicates with duplicate handling (update vs insert)
    - Implements adaptive batch sizing based on available RAM
    - Uses existing reference_api infrastructure for rate limiting
    """

    def __init__(self, config: ReferenceConfig, source_configs: Dict[str, SourceConfig], db_path: str | None = None):
        """
        Initialize the predicate discovery service.

        Args:
            config: Reference database configuration
            source_configs: Dictionary mapping source names to their configurations
            db_path: Optional path to the database file (for testing)
        """
        self.config = config
        self.source_configs = source_configs
        self.db_path = db_path
        self.manager: Optional[ReferenceManager] = None

    def __enter__(self):
        """Context manager entry."""
        self.manager = ReferenceManager(self.config, self.db_path)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self.manager:
            self.manager.close()
            self.manager = None
        return False

    def _calculate_batch_size(self, min_size: int = 8, max_size: int = 128) -> int:
        """
        Calculate optimal batch size based on available RAM.

        Uses a heuristic based on available memory:
        - If >8GB available: use max_size (128)
        - If 4-8GB available: use 64
        - If 2-4GB available: use 32
        - If <2GB available: use min_size (8)

        Args:
            min_size: Minimum batch size (default: 8)
            max_size: Maximum batch size (default: 128)

        Returns:
            Optimal batch size for current system
        """
        try:
            memory = psutil.virtual_memory()
            available_gb = memory.available / (1024 ** 3)

            if available_gb > MEMORY_THRESHOLD_HIGH:
                batch_size = max_size
            elif available_gb > MEMORY_THRESHOLD_MEDIUM:
                batch_size = 64
            elif available_gb > MEMORY_THRESHOLD_LOW:
                batch_size = 32
            else:
                batch_size = min_size

            logger.info(
                f"Calculated batch size: {batch_size} "
                f"(available RAM: {available_gb:.2f}GB)"
            )
            return batch_size

        except Exception as e:
            logger.warning(f"Error calculating batch size: {e}, using default {min_size}")
            return min_size

    def _generate_embeddings_batch(
        self, texts: List[str], batch_size: Optional[int] = None
    ) -> List[bytes]:
        """
        Generate embeddings for a batch of texts with adaptive batch sizing.

        Uses the cached model from get_model() for efficiency.

        Args:
            texts: List of text strings to embed
            batch_size: Optional batch size (auto-calculated if None)

        Returns:
            List of embedding byte arrays
        """
        if not texts:
            return []

        if batch_size is None:
            batch_size = self._calculate_batch_size()

        logger.info(f"Generating embeddings for {len(texts)} texts with batch size {batch_size}")

        # Use cached model
        model = get_model()

        embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            logger.debug(f"Processing batch {i//batch_size + 1}/{(len(texts) + batch_size - 1)//batch_size}")

            # Generate embeddings for batch
            batch_embeddings = model.encode(batch)

            # Convert to bytes
            for emb in batch_embeddings:
                embeddings.append(np.array(emb, dtype=np.float32).tobytes())

        logger.info(f"Generated {len(embeddings)} embeddings")
        return embeddings

    def _upsert_predicate(
        self,
        title: str,
        definition: str,
        source: str,
        external_id: str,
        attributes: Dict[str, Any] | None = None
    ) -> ExternalPredicate:
        """
        Insert or update a single external predicate.

        If a predicate with the same (source, external_id) exists, it will be updated.
        Otherwise, a new predicate will be created.

        Args:
            title: Predicate title
            definition: Predicate definition
            source: Source identifier
            external_id: Source-specific identifier
            attributes: Optional dictionary of additional metadata

        Returns:
            The created or updated ExternalPredicate instance
        """
        # Check if predicate already exists
        existing = self.manager.get_external_predicate_by_source(source, external_id)

        if existing:
            # Update existing predicate
            logger.debug(f"Updating existing predicate: {source}/{external_id}")
            existing.title = title
            existing.definition = definition
            existing.attributes = str(attributes) if attributes is not None else None
            existing.title_embedding = generate_embedding(title)
            existing.definition_embedding = generate_embedding(definition)
            existing.updated_at = date.today().isoformat()
            self.manager.session.commit()
            return existing
        else:
            # Create new predicate
            logger.debug(f"Creating new predicate: {source}/{external_id}")
            return self.manager.add_external_predicate(
                title=title,
                definition=definition,
                source=source,
                external_id=external_id,
                attributes=attributes
            )

    def _upsert_predicates_batch(
        self,
        predicates: List[Dict[str, Any]],
        source: str,
        batch_size: Optional[int] = None
    ) -> Tuple[int, int]:
        """
        Insert or update a batch of external predicates with batch embedding generation.

        If a predicate with the same (source, external_id) exists, it will be updated.
        Otherwise, a new predicate will be created.

        This method generates embeddings in batches for efficiency.

        Args:
            predicates: List of predicate dictionaries with keys:
                       title, definition, external_id, attributes (optional)
            source: Source identifier
            batch_size: Optional batch size for embedding generation

        Returns:
            Tuple of (created_count, updated_count)
        """
        if not predicates:
            return (0, 0)

        logger.info(f"Batch upserting {len(predicates)} predicates from {source}")

        # Collect texts for batch embedding generation
        titles = [p['title'] for p in predicates]
        definitions = [p['definition'] for p in predicates]

        # Generate all embeddings in batches
        logger.debug("Generating title embeddings in batch")
        title_embeddings = self._generate_embeddings_batch(titles, batch_size)

        logger.debug("Generating definition embeddings in batch")
        definition_embeddings = self._generate_embeddings_batch(definitions, batch_size)

        # Perform upserts in a transaction
        created = 0
        updated = 0

        try:
            for i, predicate_data in enumerate(predicates):
                external_id = predicate_data['external_id']

                # Check if predicate already exists
                existing = self.manager.get_external_predicate_by_source(source, external_id)

                if existing:
                    # Update existing predicate
                    logger.debug(f"Updating existing predicate: {source}/{external_id}")
                    existing.title = predicate_data['title']
                    existing.definition = predicate_data['definition']
                    existing.attributes = str(predicate_data.get('attributes')) if predicate_data.get('attributes') else None
                    existing.title_embedding = title_embeddings[i]
                    existing.definition_embedding = definition_embeddings[i]
                    existing.updated_at = date.today().isoformat()
                    updated += 1
                else:
                    # Create new predicate
                    logger.debug(f"Creating new predicate: {source}/{external_id}")
                    self.manager.add_external_predicate(
                        title=predicate_data['title'],
                        definition=predicate_data['definition'],
                        source=source,
                        external_id=external_id,
                        attributes=predicate_data.get('attributes'),
                        title_embedding=title_embeddings[i],
                        definition_embedding=definition_embeddings[i]
                    )
                    created += 1

            # Commit all changes in one transaction
            self.manager.session.commit()
            logger.info(f"Batch upsert complete: {created} created, {updated} updated")

        except Exception as e:
            # Rollback on error
            self.manager.session.rollback()
            logger.error(f"Error in batch upsert, rolled back transaction: {e}", exc_info=True)
            raise

        return (created, updated)

    async def discover_conceptnet_predicates(self) -> Tuple[int, int, List[str]]:
        """
        Discover all ConceptNet relations (40 relations).

        Fetches relation metadata from ConceptNet API and stores them
        in the reference database with embeddings.

        Returns:
            Tuple of (created_count, updated_count, errors)
        """
        logger.info("Starting ConceptNet predicate discovery")
        start_time = datetime.now(UTC)

        errors = []
        predicates_to_upsert = []

        try:
            # Get source configuration
            source_config = self.source_configs.get('conceptnet')
            if not source_config or not source_config.enabled:
                error_msg = "ConceptNet source not enabled in configuration"
                logger.warning(error_msg)
                errors.append(error_msg)
                return (0, 0, errors)

            # Create source instance
            async with ConceptNetSource(SourceType.CONCEPTNET, source_config) as source:
                # Fetch relation definitions from ConceptNet
                # ConceptNet provides relation info at /r/{relation}
                
                # Define async function to fetch a single relation
                async def fetch_relation(relation: str):
                    try:
                        relation_path = f"/r/{relation}"
                        logger.debug(f"Fetching ConceptNet relation: {relation_path}")

                        # Get relation data
                        response = await source.get_concept(relation_path)

                        if response.success and response.data:
                            # Extract relation metadata
                            label = response.data.get('label', relation)

                            # ConceptNet uses @id format like /r/RelatedTo
                            external_id = response.data.get('@id', f"/r/{relation}")

                            # Try to get definition from various fields
                            definition = (
                                response.data.get('comment', '') or
                                response.data.get('description', '') or
                                f"ConceptNet relation: {label}"
                            )

                            # Prepare attributes
                            attributes = {
                                'relation_type': 'conceptnet_relation',
                                'source_data': response.data
                            }

                            # Return predicate data
                            return {
                                'title': label,
                                'definition': definition,
                                'external_id': external_id,
                                'attributes': attributes
                            }
                        else:
                            error_msg = f"Failed to fetch {relation}: {response.error}"
                            logger.warning(error_msg)
                            errors.append(error_msg)
                            return None

                    except Exception as e:
                        error_msg = f"Error processing relation {relation}: {str(e)}"
                        logger.error(error_msg, exc_info=True)
                        errors.append(error_msg)
                        return None

                # Fetch all relations concurrently
                logger.info(f"Fetching {len(CONCEPTNET_RELATIONS)} ConceptNet relations concurrently")
                results = await asyncio.gather(*[fetch_relation(rel) for rel in CONCEPTNET_RELATIONS])
                
                # Filter out None results and add to batch
                predicates_to_upsert.extend([r for r in results if r is not None])

            # Batch upsert all predicates
            created, updated = self._upsert_predicates_batch(
                predicates_to_upsert,
                source='conceptnet'
            )

            elapsed = (datetime.now(UTC) - start_time).total_seconds()
            logger.info(
                f"ConceptNet discovery complete: {created} created, {updated} updated, "
                f"{len(errors)} errors in {elapsed:.2f}s"
            )

        except Exception as e:
            error_msg = f"Fatal error in ConceptNet discovery: {str(e)}"
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)
            return (0, 0, errors)

        return (created, updated, errors)

    async def discover_dbpedia_predicates(self, limit: int = 760) -> Tuple[int, int, List[str]]:
        """
        Discover DBpedia properties via SPARQL query.

        Fetches property metadata (labels, comments) from DBpedia endpoint.

        Args:
            limit: Maximum number of properties to fetch (default: 760)

        Returns:
            Tuple of (created_count, updated_count, errors)
        """
        logger.info(f"Starting DBpedia predicate discovery (limit: {limit})")
        start_time = datetime.now(UTC)

        errors = []
        predicates_to_upsert = []

        try:
            # Validate limit parameter to prevent SPARQL injection
            if not isinstance(limit, int) or limit < 1 or limit > 100000:
                error_msg = f"Invalid limit parameter: {limit}. Must be integer between 1 and 100000"
                logger.error(error_msg)
                errors.append(error_msg)
                return (0, 0, errors)

            # Get source configuration
            source_config = self.source_configs.get('dbpedia')
            if not source_config or not source_config.enabled:
                error_msg = "DBpedia source not enabled in configuration"
                logger.warning(error_msg)
                errors.append(error_msg)
                return (0, 0, errors)

            # Create source instance
            async with DBpediaSource(SourceType.DBPEDIA, source_config) as source:
                # SPARQL query to fetch DBpedia properties with labels and comments
                # Limit is validated above, safe to interpolate
                sparql_query = f"""
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                PREFIX owl: <http://www.w3.org/2002/07/owl#>

                SELECT DISTINCT ?property ?label ?comment
                WHERE {{
                  ?property rdf:type rdf:Property .
                  OPTIONAL {{ ?property rdfs:label ?label . FILTER(lang(?label) = 'en') }}
                  OPTIONAL {{ ?property rdfs:comment ?comment . FILTER(lang(?comment) = 'en') }}
                }}
                LIMIT {limit}
                """

                logger.debug("Executing DBpedia SPARQL query")
                response = await source.sparql_query(sparql_query, format='json')

                if response.success and response.results:
                    bindings = response.results.get('results', {}).get('bindings', [])
                    logger.info(f"Fetched {len(bindings)} DBpedia properties")

                    for binding in bindings:
                        try:
                            property_uri = binding.get('property', {}).get('value', '')
                            label = binding.get('label', {}).get('value', '')
                            comment = binding.get('comment', {}).get('value', '')

                            if not property_uri:
                                continue

                            # Extract property name from URI
                            property_name = property_uri.split('/')[-1].split('#')[-1]

                            # Use label if available, otherwise use property name
                            title = label if label else property_name

                            # Use comment if available, otherwise create basic definition
                            definition = comment if comment else f"DBpedia property: {title}"

                            # Prepare attributes
                            attributes = {
                                'property_uri': property_uri,
                                'property_type': 'dbpedia_property'
                            }

                            # Add to batch
                            predicates_to_upsert.append({
                                'title': title,
                                'definition': definition,
                                'external_id': property_uri,
                                'attributes': attributes
                            })

                        except Exception as e:
                            error_msg = f"Error processing DBpedia property {property_uri}: {str(e)}"
                            logger.error(error_msg, exc_info=True)
                            errors.append(error_msg)

                else:
                    error_msg = f"DBpedia SPARQL query failed: {response.error}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            # Batch upsert all predicates
            created, updated = self._upsert_predicates_batch(
                predicates_to_upsert,
                source='dbpedia'
            )

            elapsed = (datetime.now(UTC) - start_time).total_seconds()
            logger.info(
                f"DBpedia discovery complete: {created} created, {updated} updated, "
                f"{len(errors)} errors in {elapsed:.2f}s"
            )

        except Exception as e:
            error_msg = f"Fatal error in DBpedia discovery: {str(e)}"
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)
            return (0, 0, errors)

        return (created, updated, errors)

    async def discover_wikidata_predicates(self, limit: int = 10000) -> Tuple[int, int, List[str]]:
        """
        Discover Wikidata properties via SPARQL query with pagination.

        Fetches property metadata (labels, descriptions) from Wikidata endpoint.
        Uses chunking to handle large result sets efficiently without loading
        all properties into memory at once.

        Args:
            limit: Maximum number of properties to fetch (default: 10000)

        Returns:
            Tuple of (created_count, updated_count, errors)
        """
        logger.info(f"Starting Wikidata predicate discovery (limit: {limit})")
        start_time = datetime.now(UTC)

        total_created = 0
        total_updated = 0
        errors = []

        try:
            # Validate limit parameter to prevent SPARQL injection
            if not isinstance(limit, int) or limit < 1 or limit > 100000:
                error_msg = f"Invalid limit parameter: {limit}. Must be integer between 1 and 100000"
                logger.error(error_msg)
                errors.append(error_msg)
                return (0, 0, errors)

            # Get source configuration
            source_config = self.source_configs.get('wikidata')
            if not source_config or not source_config.enabled:
                error_msg = "Wikidata source not enabled in configuration"
                logger.warning(error_msg)
                errors.append(error_msg)
                return (0, 0, errors)

            # Create source instance
            async with WikidataSource(SourceType.WIKIDATA, source_config) as source:
                # Process in chunks to avoid memory issues with large result sets
                chunk_size = WIKIDATA_CHUNK_SIZE
                num_chunks = (limit + chunk_size - 1) // chunk_size

                logger.info(f"Processing Wikidata discovery in {num_chunks} chunks of {chunk_size}")

                for chunk_idx in range(num_chunks):
                    offset = chunk_idx * chunk_size
                    chunk_limit = min(chunk_size, limit - offset)

                    logger.info(f"Processing chunk {chunk_idx + 1}/{num_chunks} (offset: {offset}, limit: {chunk_limit})")

                    predicates_to_upsert = []

                    # SPARQL query to fetch Wikidata properties with labels and descriptions
                    # Both offset and chunk_limit are validated integers, safe to interpolate
                    sparql_query = f"""
                    SELECT ?property ?propertyLabel ?propertyDescription
                    WHERE {{
                      ?property a wikibase:Property .
                      SERVICE wikibase:label {{
                        bd:serviceParam wikibase:language "en" .
                        ?property rdfs:label ?propertyLabel .
                        ?property schema:description ?propertyDescription .
                      }}
                    }}
                    LIMIT {chunk_limit}
                    OFFSET {offset}
                    """

                    logger.debug(f"Executing Wikidata SPARQL query (chunk {chunk_idx + 1})")
                    response = await source.sparql_query(sparql_query, format='json')

                    if response.success and response.results:
                        bindings = response.results.get('results', {}).get('bindings', [])
                        logger.info(f"Fetched {len(bindings)} Wikidata properties in chunk {chunk_idx + 1}")

                        if not bindings:
                            # No more results, stop pagination
                            logger.info("No more results, stopping pagination")
                            break

                        for binding in bindings:
                            try:
                                property_uri = binding.get('property', {}).get('value', '')
                                label = binding.get('propertyLabel', {}).get('value', '')
                                description = binding.get('propertyDescription', {}).get('value', '')

                                if not property_uri:
                                    continue

                                # Extract property ID from URI (e.g., P31 from http://www.wikidata.org/entity/P31)
                                property_id = property_uri.split('/')[-1]

                                # Use label if available, otherwise use property ID
                                title = label if label else property_id

                                # Use description if available, otherwise create basic definition
                                definition = description if description else f"Wikidata property: {title}"

                                # Prepare attributes
                                attributes = {
                                    'property_uri': property_uri,
                                    'property_id': property_id,
                                    'property_type': 'wikidata_property'
                                }

                                # Add to batch
                                predicates_to_upsert.append({
                                    'title': title,
                                    'definition': definition,
                                    'external_id': property_uri,
                                    'attributes': attributes
                                })

                            except Exception as e:
                                error_msg = f"Error processing Wikidata property {property_uri}: {str(e)}"
                                logger.error(error_msg, exc_info=True)
                                errors.append(error_msg)

                        # Batch upsert this chunk's predicates
                        created, updated = self._upsert_predicates_batch(
                            predicates_to_upsert,
                            source='wikidata'
                        )
                        total_created += created
                        total_updated += updated

                    else:
                        error_msg = f"Wikidata SPARQL query failed for chunk {chunk_idx + 1}: {response.error}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        # Continue with next chunk instead of stopping completely
                        continue

            elapsed = (datetime.now(UTC) - start_time).total_seconds()
            logger.info(
                f"Wikidata discovery complete: {total_created} created, {total_updated} updated, "
                f"{len(errors)} errors in {elapsed:.2f}s"
            )

        except Exception as e:
            error_msg = f"Fatal error in Wikidata discovery: {str(e)}"
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)
            return (total_created, total_updated, errors)

        return (total_created, total_updated, errors)

    async def discover_schema_org_predicates(self) -> Tuple[int, int, List[str]]:
        """
        Discover predicates from Schema.org by querying ExternalPredicates.
        
        Note: Schema.org properties are imported via the SchemaOrgImporter into the
        external_predicates table. This method simply ensures they exist and reports
        statistics. If no predicates are found, it suggests running the Schema.org import.
        
        Returns:
            Tuple of (created, updated, errors) where:
            - created: Number of new predicates (always 0, as they're imported separately)
            - updated: Number of existing predicates
            - errors: List of error messages
        """
        logger.info("Discovering Schema.org predicates")
        errors = []
        
        try:
            # Query existing Schema.org predicates
            existing_count = self.manager.session.query(ExternalPredicate).filter_by(
                source='schema.org'
            ).count()
            
            if existing_count == 0:
                error_msg = (
                    "No Schema.org predicates found in database. "
                    "Please run the Schema.org import first using the SchemaOrgImporter."
                )
                logger.warning(error_msg)
                errors.append(error_msg)
                return (0, 0, errors)
            
            logger.info(f"Found {existing_count} Schema.org predicates in database")
            
            # Schema.org predicates are imported via SchemaOrgImporter,
            # so we just report what exists
            return (0, existing_count, errors)
            
        except Exception as e:
            error_msg = f"Error discovering Schema.org predicates: {str(e)}"
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)
            return (0, 0, errors)

    async def discover_all_predicates(
        self,
        sources: Optional[List[str]] = None
    ) -> Dict[str, Tuple[int, int, List[str]]]:
        """
        Discover predicates from all enabled sources.

        Args:
            sources: Optional list of source names to discover from.
                    If None, discovers from all enabled sources.
                    Valid values: ['conceptnet', 'dbpedia', 'wikidata', 'schema_org']

        Returns:
            Dictionary mapping source name to (created, updated, errors) tuple
        """
        if sources is None:
            sources = ['conceptnet', 'dbpedia', 'wikidata', 'schema_org']

        logger.info(f"Starting discovery for sources: {sources}")
        results = {}

        for source in sources:
            if source == 'conceptnet':
                results['conceptnet'] = await self.discover_conceptnet_predicates()
            elif source == 'dbpedia':
                results['dbpedia'] = await self.discover_dbpedia_predicates()
            elif source == 'wikidata':
                results['wikidata'] = await self.discover_wikidata_predicates()
            elif source == 'schema_org':
                results['schema_org'] = await self.discover_schema_org_predicates()
            else:
                logger.warning(f"Unknown source: {source}")
                results[source] = (0, 0, [f"Unknown source: {source}"])

        return results
