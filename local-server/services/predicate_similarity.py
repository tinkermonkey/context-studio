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
from datetime import datetime, timedelta, UTC
from collections import defaultdict

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session
from sklearn.cluster import DBSCAN
from cachetools import TTLCache

from embeddings.generate_embeddings import generate_embedding
from utils.logger import get_logger
from reference_db.manager import ReferenceManager
from reference_db.config import ReferenceConfig

logger = get_logger("predicate_similarity")


# TTL-based cache for similarity search results (1 hour)
# Stores up to 1000 queries
_similarity_cache = TTLCache(maxsize=1000, ttl=3600)


@dataclass
class SimilarityResult:
    """Result of a similarity search."""
    predicate_id: str
    source: str
    source_id: str
    title: str
    definition: str
    similarity_score: float
    confidence: str  # "high", "medium", "low", "reject"


@dataclass
class ClusterResult:
    """Result of predicate clustering."""
    cluster_id: int
    predicate_ids: List[str]
    centroid_title: str
    avg_similarity: float
    size: int


class PredicateSimilarityService:
    """
    Service for predicate similarity search and clustering.

    This service provides:
    - Vector similarity search against external predicates
    - TTL-based caching of search results
    - Cache invalidation on predicate updates
    - Clustering algorithm for grouping similar predicates
    - Warm-up procedures for index loading
    """

    def __init__(self, reference_manager: ReferenceManager):
        """
        Initialize the predicate similarity service.

        Args:
            reference_manager: ReferenceManager instance for vector search
        """
        self.reference_manager = reference_manager
        self.warm_up_complete = False
        logger.info("PredicateSimilarityService initialized")

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
        Generate cache key for similarity search.

        Args:
            query_text: Search query text
            source: Optional source filter
            limit: Result limit
            threshold: Similarity threshold

        Returns:
            Cache key as hex string
        """
        cache_data = {
            "query": query_text,
            "source": source,
            "limit": limit,
            "threshold": threshold
        }
        cache_str = json.dumps(cache_data, sort_keys=True)
        return hashlib.sha256(cache_str.encode()).hexdigest()

    def invalidate_cache(self):
        """Invalidate the entire similarity search cache."""
        global _similarity_cache
        _similarity_cache.clear()
        logger.info("Similarity search cache invalidated")

    def _confidence_level(self, similarity: float) -> str:
        """
        Determine confidence level based on similarity score.

        Args:
            similarity: Cosine similarity score (0.0 to 1.0)

        Returns:
            Confidence level: "high", "medium", "low", or "reject"
        """
        if similarity >= 0.85:
            return "high"
        elif similarity >= 0.70:
            return "medium"
        elif similarity >= 0.60:
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

        Args:
            predicate_title: Title of the predicate to search for
            predicate_definition: Optional definition to include in search
            source: Optional source filter (e.g., "dbpedia", "wikidata")
            limit: Maximum number of results (default: 100)
            threshold: Minimum similarity threshold (default: 0.7)
            use_cache: Whether to use cached results (default: True)

        Returns:
            List of SimilarityResult objects ordered by similarity descending

        Performance target: <200ms p95 for 10K-50K predicates (PT-VS-001, PT-VS-002)
                           <50ms p95 for cached results (PT-VS-006)
        """
        # Check cache first
        cache_key = self._get_cache_key(predicate_title, source, limit, threshold)

        if use_cache and cache_key in _similarity_cache:
            logger.debug(f"Cache hit for query: {predicate_title[:50]}...")
            return _similarity_cache[cache_key]

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
                _similarity_cache[cache_key] = similarity_results

            elapsed = (time.perf_counter() - start_time) * 1000  # Convert to ms
            logger.info(
                f"Similarity search completed in {elapsed:.2f}ms: "
                f"query='{predicate_title[:50]}...', results={len(similarity_results)}"
            )

            return similarity_results

        except Exception as e:
            logger.error(f"Similarity search failed: {e}", exc_info=True)
            raise

    def find_similar_batch(
        self,
        predicates: List[Tuple[str, Optional[str]]],
        source: Optional[str] = None,
        limit: int = 100,
        threshold: float = 0.7
    ) -> Dict[str, List[SimilarityResult]]:
        """
        Find similar predicates for a batch of queries.

        Args:
            predicates: List of (title, definition) tuples
            source: Optional source filter
            limit: Maximum results per query
            threshold: Minimum similarity threshold

        Returns:
            Dictionary mapping predicate titles to similarity results

        Performance target: <800ms p95 for 10 predicates (PT-VS-003)
        """
        start_time = time.perf_counter()
        results = {}

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
                logger.error(f"Batch query failed for '{title}': {e}")
                results[title] = []

        elapsed = (time.perf_counter() - start_time) * 1000  # Convert to ms
        logger.info(
            f"Batch similarity search completed in {elapsed:.2f}ms: "
            f"{len(predicates)} queries, {sum(len(r) for r in results.values())} total results"
        )

        return results

    def cluster_predicates(
        self,
        predicates: List[Tuple[str, str, Optional[str]]],  # (id, title, definition)
        min_similarity: float = 0.7,
        min_cluster_size: int = 2,
        eps: float = 0.3  # DBSCAN epsilon (distance threshold)
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
            min_similarity: Minimum similarity to be considered in same cluster
            min_cluster_size: Minimum number of predicates per cluster
            eps: DBSCAN epsilon parameter (distance threshold)

        Returns:
            List of ClusterResult objects

        Notes:
            - DBSCAN automatically determines number of clusters
            - Noise points (cluster_id=-1) are excluded from results
            - eps parameter controls cluster tightness (lower = tighter)
        """
        if not predicates:
            return []

        start_time = time.perf_counter()
        logger.info(f"Clustering {len(predicates)} predicates...")

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
            Dictionary with cache statistics
        """
        return {
            "size": len(_similarity_cache),
            "maxsize": _similarity_cache.maxsize,
            "ttl": _similarity_cache.ttl,
            "currsize": _similarity_cache.currsize
        }
