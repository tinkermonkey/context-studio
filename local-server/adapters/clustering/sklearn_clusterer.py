"""
scikit-learn clustering adapter implementing the ClusteringPort.

Distils many concept-candidate embeddings into a smaller set of clusters for the
open-extraction schema flow. Supports agglomerative clustering (default; a
data-driven cluster count via a cosine distance threshold) and DBSCAN (which
yields native noise labels), selectable as a closed-loop optimization knob.
"""

from collections import Counter

import numpy as np
from sklearn.cluster import DBSCAN, AgglomerativeClustering

from domain.extraction.ports import ClusterAssignment
from utils.logger import get_logger

logger = get_logger(__name__)


class SklearnClusterer:
    """
    Clustering adapter backed by scikit-learn.

    Args:
        algorithm: 'agglomerative' (default) or 'dbscan'.
        metric: Distance metric (default 'cosine').
        linkage: Linkage strategy for agglomerative clustering (default 'average';
            'ward' is incompatible with non-euclidean metrics).
    """

    def __init__(
        self,
        algorithm: str = "agglomerative",
        metric: str = "cosine",
        linkage: str = "average",
    ) -> None:
        self.algorithm = algorithm
        self.metric = metric
        self.linkage = linkage

    def cluster(
        self,
        vectors: list[list[float]],
        distance_threshold: float,
        min_cluster_size: int = 1,
    ) -> list[ClusterAssignment]:
        """
        Cluster embedding vectors.

        Args:
            vectors: Embedding vectors to cluster; all must share one dimensionality.
            distance_threshold: Maximum distance for two points to share a cluster
                (the agglomerative cut height / the DBSCAN eps).
            min_cluster_size: Clusters smaller than this collapse to noise (-1).

        Returns:
            One ClusterAssignment per input vector, in input order.
        """
        if not vectors:
            return []
        if len(vectors) == 1:
            # A lone point is its own cluster unless a larger size is required.
            label = 0 if min_cluster_size <= 1 else -1
            return [ClusterAssignment(index=0, label=label)]

        data = np.asarray(vectors, dtype=float)
        if self.algorithm == "dbscan":
            labels = self._dbscan(data, distance_threshold, min_cluster_size)
        else:
            labels = self._agglomerative(data, distance_threshold, min_cluster_size)

        return [ClusterAssignment(index=i, label=int(lbl)) for i, lbl in enumerate(labels)]

    def _agglomerative(
        self, data: np.ndarray, distance_threshold: float, min_cluster_size: int
    ) -> list[int]:
        """Agglomerative clustering with small clusters collapsed to noise."""
        model = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=distance_threshold,
            metric=self.metric,
            linkage=self.linkage,
        )
        labels = model.fit_predict(data).tolist()
        if min_cluster_size <= 1:
            return labels
        counts = Counter(labels)
        return [lbl if counts[lbl] >= min_cluster_size else -1 for lbl in labels]

    def _dbscan(
        self, data: np.ndarray, distance_threshold: float, min_cluster_size: int
    ) -> list[int]:
        """DBSCAN clustering; noise points are labelled -1 natively."""
        model = DBSCAN(
            eps=distance_threshold,
            min_samples=max(1, min_cluster_size),
            metric=self.metric,
        )
        return model.fit_predict(data).tolist()
