"""
Predicate similarity search service with vector search optimization.

This module provides high-performance vector similarity search for predicates
with the following features:
- Cosine similarity using sqlite-vec with distance-based indexing
- TTL-based result caching (1 hour)
- Query optimization with early termination
- Warm-up procedures for index loading
- Read-only connections for better concurrency
- Clustering algorithm with automatic cluster count determination

Performance targets:
- <200ms p95 for 10K predicates (PT-VS-001)
- <200ms p95 for 50K predicates (PT-VS-002)
- <800ms p95 for batch of 10 predicates (PT-VS-003)
- <300ms p95 for 10 concurrent users (PT-VS-004)
- <50ms p95 for cached searches (PT-VS-006)
- <5 seconds for index warm-up (PT-VS-007)
"""

import logging
import time
import hashlib
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict

import numpy as np
from sqlalchemy.orm import Session
from sklearn.cluster import DBSCAN
from cachetools import TTLCache

from embeddings.generate_embeddings import generate_embedding
from utils.logger import get_logger
from reference_db.manager import ReferenceManager

logger = get_logger("predicate_similarity")


@dataclass
class SimilarityResult:
    """
    Result of a similarity search.

    Attributes:
        predicate_id: Unique identifier for the predicate
        source: Data source (e.g., "dbpedia", "wikidata")
        source_id: External ID in the source system
        title: Predicate title/label
        definition: Predicate definition/description
        similarity_score: Cosine similarity score (0.0 to 1.0)
        confidence: Confidence level ("high", "medium", "low", "reject")
    """
    predicate_id: str
    source: str
    source_id: str
    title: str
    definition: str
    similarity_score: float
    confidence: str


@dataclass
class ClusterResult:
    """
    Result of predicate clustering.

    Attributes:
        cluster_id: Unique cluster identifier (assigned by DBSCAN)
        predicate_ids: List of predicate IDs in this cluster
        centroid_title: Title of the most central predicate
        avg_similarity: Average pairwise similarity within cluster
        size: Number of predicates in cluster
    """
    cluster_id: int
    predicate_ids: List[str]
    centroid_title: str
    avg_similarity: float
    size: int


@dataclass
class BatchError:
    """
    Error information for failed batch operations.

    Attributes:
        predicate_title: Title of the predicate that failed
        error_message: Description of the error
        error_type: Type of exception that occurred
    """
    predicate_title: str
    error_message: str
    error_type: str


class PredicateSimilarityService:
    """
    Service for predicate similarity search and clustering.

    This service provides:
    - Vector similarity search against external predicates
    - TTL-based caching of search results
    - Cache invalidation on predicate updates
    - Clustering algorithm for grouping similar predicates
    - Warm-up procedures for index loading

    Attributes:
        HIGH_CONFIDENCE_THRESHOLD: Similarity threshold for high confidence (0.85)
        MEDIUM_CONFIDENCE_THRESHOLD: Similarity threshold for medium confidence (0.70)
        LOW_CONFIDENCE_THRESHOLD: Similarity threshold for low confidence (0.60)
    """

    # Confidence level thresholds
    HIGH_CONFIDENCE_THRESHOLD = 0.85
    MEDIUM_CONFIDENCE_THRESHOLD = 0.70
    LOW_CONFIDENCE_THRESHOLD = 0.60

    def __init__(
        self,
        reference_manager: ReferenceManager,
        embedding_dimensions: int = 384,
        cache_maxsize: int = 1000,
        cache_ttl: int = 3600
    ):
        """
        Initialize the predicate similarity service.

        Args:
            reference_manager: ReferenceManager instance for vector search
            embedding_dimensions: Dimension of embedding vectors (default: 384)
            cache_maxsize: Maximum number of cached queries (default: 1000)
            cache_ttl: Cache TTL in seconds (default: 3600 = 1 hour)
        """
        self.reference_manager = reference_manager
        self.embedding_dimensions = embedding_dimensions
        self.warm_up_complete = False

        # Initialize instance-level cache
        self._similarity_cache = TTLCache(maxsize=cache_maxsize, ttl=cache_ttl)

        logger.info(
            f"PredicateSimilarityService initialized: "
            f"embedding_dim={embedding_dimensions}, "
            f"cache_maxsize={cache_maxsize}, cache_ttl={cache_ttl}s"
        )

    def warm_up(self, sample_size: int = 10) -> float:
        """
        Warm up the vector search index by executing sample queries.

        This loads the index into memory for better performance.

        Args:
            sample_size: Number of sample queries to execute

        Returns:
            Time taken for warm-up in seconds

        Performance target: <5 seconds (PT-VS-007)
        """
        start_time = time.perf_counter()

        logger.info(f"Starting index warm-up with {sample_size} sample queries...")

        # Get a sample of external predicates
        external_predicates = self.reference_manager.list_external_predicates(limit=sample_size)

        if not external_predicates:
            logger.warning("No external predicates found for warm-up")
            self.warm_up_complete = True
            return 0.0

        # Execute sample queries to load index into memory
        for predicate in external_predicates:
            try:
                # Execute a quick search with low limit
                self.reference_manager.search_external_predicates_by_similarity(
                    query_text=predicate.title,
                    limit=5,
                    threshold=0.0  # Accept all results for warm-up
                )
            except Exception as e:
                logger.warning(f"Warm-up query failed for '{predicate.title}': {e}")

        elapsed = time.perf_counter() - start_time
        self.warm_up_complete = True
        logger.info(f"Index warm-up complete in {elapsed:.3f}s")

        return elapsed

    def _get_cache_key(
        self,
        query_text: str,
        source: Optional[str] = None,
        limit: int = 100,
        threshold: float = 0.7
    ) -> str:
        """
        Generate cache key for similarity search using SHA-256 hash.

        This method creates a robust cache key that handles special characters
        and ensures consistent hashing across calls.

        Args:
            query_text: Search query text
            source: Optional source filter (e.g., "dbpedia", "wikidata")
            limit: Maximum number of results (default: 100)
            threshold: Minimum similarity threshold (default: 0.7)

        Returns:
            Cache key as 64-character hexadecimal string (SHA-256 hash)
        """
        cache_data = {
            "query": query_text,
            "source": source,
            "limit": limit,
            "threshold": threshold
        }
        # Use sorted keys for consistent JSON serialization
        cache_str = json.dumps(cache_data, sort_keys=True)
        # Generate SHA-256 hash for robust key generation
        return hashlib.sha256(cache_str.encode('utf-8')).hexdigest()

    def invalidate_cache(self):
        """
        Invalidate the entire similarity search cache.

        This method clears all cached query results. Use this when predicates
        are updated to ensure fresh results.
        """
        self._similarity_cache.clear()
        logger.info("Similarity search cache invalidated")

    def _confidence_level(self, similarity: float) -> str:
        """
        Determine confidence level based on similarity score.

        Confidence levels:
        - High: >= 0.85 (strong semantic match)
        - Medium: 0.70-0.84 (good semantic match)
        - Low: 0.60-0.69 (weak semantic match)
        - Reject: < 0.60 (insufficient match)

        Args:
            similarity: Cosine similarity score (0.0 to 1.0)

        Returns:
            Confidence level: "high", "medium", "low", or "reject"
        """
        if similarity >= self.HIGH_CONFIDENCE_THRESHOLD:
            return "high"
        elif similarity >= self.MEDIUM_CONFIDENCE_THRESHOLD:
            return "medium"
        elif similarity >= self.LOW_CONFIDENCE_THRESHOLD:
            return "low"
        else:
            return "reject"

    def find_similar_predicates(
        self,
        predicate_title: str,
        predicate_definition: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 100,
        threshold: float = 0.7,
        use_cache: bool = True
    ) -> List[SimilarityResult]:
        """
        Find similar predicates using vector similarity search.

        This method uses cosine similarity on vector embeddings to find
        semantically similar predicates in the external predicate database.

        Args:
            predicate_title: Title of the predicate to search for (required, non-empty)
            predicate_definition: Optional definition to include in search
            source: Optional source filter (e.g., "dbpedia", "wikidata")
            limit: Maximum number of results (default: 100, max: 100)
            threshold: Minimum similarity threshold (default: 0.7, range: 0.0-1.0)
            use_cache: Whether to use cached results (default: True)

        Returns:
            List of SimilarityResult objects ordered by similarity descending

        Raises:
            ValueError: If predicate_title is empty or validation fails

        Performance target: <200ms p95 for 10K-50K predicates (PT-VS-001, PT-VS-002)
                           <50ms p95 for cached results (PT-VS-006)
        """
        # Validate input
        if not predicate_title or not predicate_title.strip():
            error_msg = "predicate_title cannot be empty"
            logger.error(f"Input validation failed: {error_msg}")
            raise ValueError(error_msg)

        # Check cache first
        cache_key = self._get_cache_key(predicate_title, source, limit, threshold)

        if use_cache and cache_key in self._similarity_cache:
            logger.debug(f"Cache hit for query: {predicate_title[:50]}...")
            return self._similarity_cache[cache_key]

        start_time = time.perf_counter()

        # Construct query text (combine title and definition if available)
        query_text = predicate_title
        if predicate_definition:
            query_text = f"{predicate_title}. {predicate_definition}"

        # Perform vector similarity search
        try:
            results = self.reference_manager.search_external_predicates_by_similarity(
                query_text=query_text,
                source=source,
                limit=limit,
                threshold=threshold
            )

            # Convert to SimilarityResult objects
            similarity_results = []
            for external_pred, score in results:
                confidence = self._confidence_level(score)

                # Skip results below threshold
                if confidence == "reject":
                    continue

                similarity_results.append(SimilarityResult(
                    predicate_id=external_pred.id,
                    source=external_pred.source,
                    source_id=external_pred.external_id,
                    title=external_pred.title,
                    definition=external_pred.definition,
                    similarity_score=score,
                    confidence=confidence
                ))

            # Cache the results
            if use_cache:
                self._similarity_cache[cache_key] = similarity_results

            elapsed = (time.perf_counter() - start_time) * 1000  # Convert to ms
            logger.info(
                f"Similarity search completed in {elapsed:.2f}ms: "
                f"query='{predicate_title[:50]}...', results={len(similarity_results)}, "
                f"cache_enabled={use_cache}"
            )

            return similarity_results

        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            error_context = {
                "predicate_title": predicate_title[:100],
                "source": source,
                "limit": limit,
                "threshold": threshold
            }
            logger.error(
                f"Similarity search failed: {e}. Context: {error_context}",
                exc_info=True
            )
            raise

    def find_similar_batch(
        self,
        predicates: List[Tuple[str, Optional[str]]],
        source: Optional[str] = None,
        limit: int = 100,
        threshold: float = 0.7
    ) -> Tuple[Dict[str, List[SimilarityResult]], List[BatchError]]:
        """
        Find similar predicates for a batch of queries.

        This method processes multiple similarity searches and returns both
        successful results and error information for failed queries.

        Args:
            predicates: List of (title, definition) tuples
            source: Optional source filter (e.g., "dbpedia", "wikidata")
            limit: Maximum results per query (default: 100)
            threshold: Minimum similarity threshold (default: 0.7)

        Returns:
            Tuple containing:
            - Dictionary mapping predicate titles to similarity results
            - List of BatchError objects for failed queries

        Performance target: <800ms p95 for 10 predicates (PT-VS-003)
        """
        start_time = time.perf_counter()
        results = {}
        errors = []

        for title, definition in predicates:
            try:
                results[title] = self.find_similar_predicates(
                    predicate_title=title,
                    predicate_definition=definition,
                    source=source,
                    limit=limit,
                    threshold=threshold
                )
            except Exception as e:
                error_type = type(e).__name__
                error_msg = str(e)
                logger.error(
                    f"Batch query failed for '{title}': {error_type}: {error_msg}"
                )
                errors.append(BatchError(
                    predicate_title=title,
                    error_message=error_msg,
                    error_type=error_type
                ))
                # Still add empty list to results for consistency
                results[title] = []

        elapsed = (time.perf_counter() - start_time) * 1000  # Convert to ms
        success_count = len([r for r in results.values() if r])
        logger.info(
            f"Batch similarity search completed in {elapsed:.2f}ms: "
            f"{len(predicates)} queries, {success_count} successful, "
            f"{len(errors)} errors, {sum(len(r) for r in results.values())} total results"
        )

        return results, errors

    def cluster_predicates(
        self,
        predicates: List[Tuple[str, str, Optional[str]]],  # (id, title, definition)
        min_similarity: float = 0.7,
        min_cluster_size: int = 2,
        eps: float = 0.3,  # DBSCAN epsilon (distance threshold)
        max_predicates: int = 1000
    ) -> List[ClusterResult]:
        """
        Cluster similar predicates using DBSCAN algorithm.

        This method:
        1. Generates embeddings for all predicates
        2. Computes pairwise cosine distances
        3. Uses DBSCAN for density-based clustering
        4. Returns clusters with automatic count determination

        Args:
            predicates: List of (id, title, definition) tuples
            min_similarity: Minimum similarity to be considered in same cluster (0.0-1.0)
            min_cluster_size: Minimum number of predicates per cluster (default: 2)
            eps: DBSCAN epsilon parameter for distance threshold (default: 0.3)
            max_predicates: Maximum number of predicates to process (default: 1000)

        Returns:
            List of ClusterResult objects, sorted by cluster size descending

        Raises:
            ValueError: If predicates list exceeds max_predicates limit

        Notes:
            - DBSCAN automatically determines number of clusters
            - Noise points (cluster_id=-1) are excluded from results
            - eps parameter controls cluster tightness (lower = tighter)
            - Large datasets (>1000 predicates) may cause performance issues
        """
        if not predicates:
            logger.info("No predicates provided for clustering")
            return []

        # Validate predicate count to prevent resource exhaustion
        if len(predicates) > max_predicates:
            error_msg = (
                f"Too many predicates for clustering: {len(predicates)} "
                f"(max: {max_predicates}). Consider processing in batches."
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        start_time = time.perf_counter()
        logger.info(
            f"Clustering {len(predicates)} predicates with "
            f"min_cluster_size={min_cluster_size}, eps={eps}..."
        )

        # Generate embeddings for all predicates
        embeddings = []
        predicate_map = {}

        for pred_id, title, definition in predicates:
            query_text = title
            if definition:
                query_text = f"{title}. {definition}"

            try:
                embedding = generate_embedding(query_text)
                # Convert bytes to numpy array
                emb_array = np.frombuffer(embedding, dtype=np.float32)
                embeddings.append(emb_array)
                predicate_map[len(embeddings) - 1] = (pred_id, title, definition)
            except Exception as e:
                logger.warning(f"Failed to generate embedding for '{title}': {e}")

        if len(embeddings) < min_cluster_size:
            logger.warning(f"Not enough embeddings ({len(embeddings)}) for clustering")
            return []

        # Stack embeddings into matrix
        embedding_matrix = np.vstack(embeddings)

        # Perform DBSCAN clustering
        # eps is the maximum distance for points to be in the same cluster
        # min_samples is the minimum cluster size
        clustering = DBSCAN(
            eps=eps,
            min_samples=min_cluster_size,
            metric='cosine'
        ).fit(embedding_matrix)

        # Group predicates by cluster
        clusters = defaultdict(list)
        for idx, label in enumerate(clustering.labels_):
            if label >= 0:  # Exclude noise points (label=-1)
                clusters[label].append(idx)

        # Build cluster results
        cluster_results = []
        for cluster_id, indices in clusters.items():
            if len(indices) < min_cluster_size:
                continue

            # Get predicate IDs and titles
            pred_ids = [predicate_map[idx][0] for idx in indices]
            titles = [predicate_map[idx][1] for idx in indices]

            # Compute average pairwise similarity within cluster
            cluster_embeddings = embedding_matrix[indices]
            similarities = []
            for i in range(len(cluster_embeddings)):
                for j in range(i + 1, len(cluster_embeddings)):
                    # Cosine similarity = 1 - cosine distance
                    cos_dist = 1 - np.dot(
                        cluster_embeddings[i],
                        cluster_embeddings[j]
                    ) / (
                        np.linalg.norm(cluster_embeddings[i]) *
                        np.linalg.norm(cluster_embeddings[j])
                    )
                    similarities.append(1 - cos_dist)  # Convert to similarity

            avg_similarity = np.mean(similarities) if similarities else 0.0

            # Use most central predicate as centroid title
            # (predicate with highest average similarity to others)
            centroid_idx = 0
            best_avg_sim = 0.0

            for i, idx in enumerate(indices):
                pred_sims = []
                for j, other_idx in enumerate(indices):
                    if i != j:
                        cos_sim = np.dot(
                            embedding_matrix[idx],
                            embedding_matrix[other_idx]
                        ) / (
                            np.linalg.norm(embedding_matrix[idx]) *
                            np.linalg.norm(embedding_matrix[other_idx])
                        )
                        pred_sims.append(cos_sim)

                avg_sim = np.mean(pred_sims) if pred_sims else 0.0
                if avg_sim > best_avg_sim:
                    best_avg_sim = avg_sim
                    centroid_idx = i

            centroid_title = titles[centroid_idx]

            cluster_results.append(ClusterResult(
                cluster_id=int(cluster_id),
                predicate_ids=pred_ids,
                centroid_title=centroid_title,
                avg_similarity=float(avg_similarity),
                size=len(pred_ids)
            ))

        elapsed = time.perf_counter() - start_time
        logger.info(
            f"Clustering complete in {elapsed:.3f}s: "
            f"{len(cluster_results)} clusters from {len(predicates)} predicates"
        )

        return cluster_results

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics including:
            - size: Current number of cached queries
            - maxsize: Maximum cache capacity
            - ttl: Time-to-live in seconds
            - currsize: Current cache size (same as size)
        """
        return {
            "size": len(self._similarity_cache),
            "maxsize": self._similarity_cache.maxsize,
            "ttl": self._similarity_cache.ttl,
            "currsize": self._similarity_cache.currsize
        }
