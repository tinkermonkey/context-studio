"""Integration tests for SklearnClusterer (ClusteringPort implementation)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from adapters.clustering.sklearn_clusterer import SklearnClusterer
from domain.extraction.ports import ClusterAssignment

# Two vectors near the x-axis, one near the y-axis: cosine distance separates them.
_NEAR_X_A = [1.0, 0.0, 0.0]
_NEAR_X_B = [0.98, 0.02, 0.0]
_NEAR_Y = [0.0, 1.0, 0.0]


def test_cluster_empty_returns_empty():
    assert SklearnClusterer().cluster([], distance_threshold=0.3) == []


def test_cluster_single_point():
    result = SklearnClusterer().cluster([_NEAR_X_A], distance_threshold=0.3)
    assert result == [ClusterAssignment(index=0, label=0)]


def test_cluster_single_point_collapses_to_noise_when_min_size_high():
    result = SklearnClusterer().cluster(
        [_NEAR_X_A], distance_threshold=0.3, min_cluster_size=2
    )
    assert result == [ClusterAssignment(index=0, label=-1)]


def test_agglomerative_groups_near_separates_far():
    result = SklearnClusterer().cluster(
        [_NEAR_X_A, _NEAR_X_B, _NEAR_Y], distance_threshold=0.3
    )
    labels = [a.label for a in result]
    # Indices preserved, in input order.
    assert [a.index for a in result] == [0, 1, 2]
    # The two near-x vectors share a cluster; the near-y vector is separate.
    assert labels[0] == labels[1]
    assert labels[2] != labels[0]


def test_agglomerative_min_cluster_size_collapses_singletons():
    result = SklearnClusterer().cluster(
        [_NEAR_X_A, _NEAR_X_B, _NEAR_Y], distance_threshold=0.3, min_cluster_size=2
    )
    labels = {a.index: a.label for a in result}
    # The {0,1} cluster survives; the singleton {2} collapses to noise.
    assert labels[0] == labels[1] >= 0
    assert labels[2] == -1


def test_dbscan_algorithm_path():
    clusterer = SklearnClusterer(algorithm="dbscan")
    result = clusterer.cluster(
        [_NEAR_X_A, _NEAR_X_B, _NEAR_Y], distance_threshold=0.1, min_cluster_size=2
    )
    labels = {a.index: a.label for a in result}
    # Near-x pair clusters together; isolated near-y point is DBSCAN noise.
    assert labels[0] == labels[1] >= 0
    assert labels[2] == -1
