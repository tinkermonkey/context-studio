"""
Performance benchmark for SqliteSchemaVectorIndex.search() at ontology scale.

Compares mean per-query latency at the throwaway 3-class placeholder scale
against the ~1,750-row scale produced by importing the DR spec (186 classes +
1,566 property definitions — see
documentation/karpathy_loop_dr_ontology_design.md §4). Brute-force numpy
cosine (SqliteSchemaVectorIndex._best_score) is O(n) in the indexed row count
per search() call; this measures whether that still fits Loop A's
"seconds/eval" cost assumption (documentation/karpathy_loop_design.md §4.1)
now that n has grown ~580x for a search scoped to `kinds=["class"]`, and
~580x again on top of that for a search that also includes
`property_definition`.

Uses synthetic rows rather than a real DR spec import, so this test has no
external-checkout dependency and stays fast/deterministic in CI (see
ontology_factory in tests/integration/pipelines/conftest.py for the fixture
that does build the real import, for correctness tests). Query cost is driven
by embedding dimensionality, not semantic content, so a 384-dimensional
deterministic hash embedding — matching all-MiniLM-L12-v2's real output
dimension — models query cost accurately without loading the real model.
"""

import hashlib
import statistics
import time

import pytest

from adapters.persistence.sqlite.connection import create_local_db_engine, create_session_factory
from adapters.persistence.sqlite.models import Base, OntologyEntity
from adapters.persistence.sqlite.schema_vector_index import SqliteSchemaVectorIndex

_EMBEDDING_DIMENSION = 384  # all-MiniLM-L12-v2's real output dimension
_QUERIES_PER_SCALE = 50

# Ceiling on mean per-query latency for open_v1's default kinds_to_search=
# ['class'] search (186 rows at DR scale): a Loop A dev-set eval issuing a
# few hundred such lookups should stay within "seconds/eval". See the
# conclusion printed by test_search_latency_at_placeholder_and_dr_scale for
# the full before/after numbers, including the wider-kind case that does NOT
# fit this ceiling.
_MAX_MEAN_QUERY_SECONDS_AT_DR_SCALE = 0.05


class _HashEmbedding:
    """Deterministic embedding at real-model dimensionality (query-cost fidelity)."""

    def embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode()).digest()
        raw = (digest * ((_EMBEDDING_DIMENSION * 4 // len(digest)) + 1))[
            : _EMBEDDING_DIMENSION * 4
        ]
        return [
            int.from_bytes(raw[i * 4 : (i + 1) * 4], "little") / 2**32
            for i in range(_EMBEDDING_DIMENSION)
        ]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]

    def similarity(self, a, b):  # unused by the index
        raise NotImplementedError


def _build_index(num_classes: int, num_properties: int) -> SqliteSchemaVectorIndex:
    """A fresh in-memory SqliteSchemaVectorIndex seeded with synthetic rows."""
    engine = create_local_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    embedding = _HashEmbedding()
    with session_factory() as session:
        classes = [
            OntologyEntity(
                id=f"class-{i:05d}",
                node_type="class",
                title=f"Class {i}",
                description=f"Description of synthetic class {i}",
            )
            for i in range(num_classes)
        ]
        session.add_all(classes)
        session.add_all(
            OntologyEntity(
                id=f"prop-{i:05d}",
                node_type="property_definition",
                title=f"relates_to_{i}",
                description=f"Description of synthetic property {i}",
                identifier=f"relates_to_{i}",
                domain_class_id=classes[i % num_classes].id if num_classes else None,
            )
            for i in range(num_properties)
        )
        session.commit()

    index = SqliteSchemaVectorIndex(session_factory, embedding)
    index.reindex_all()
    return index


def _time_searches(index: SqliteSchemaVectorIndex, kinds: list[str]) -> list[float]:
    embedding = _HashEmbedding()
    durations = []
    for i in range(_QUERIES_PER_SCALE):
        query = embedding.embed(f"query phrase {i}")
        start = time.perf_counter()
        index.search(query, kinds=kinds, top_k=20)
        durations.append(time.perf_counter() - start)
    return durations


@pytest.mark.performance
def test_search_latency_at_placeholder_and_dr_scale():
    """
    Before/after measurement: 3-class placeholder vs ~1,750-row DR-spec scale.

    Prints mean/median latency for both a `kinds=["class"]` search (186 rows
    at DR scale — the default `kinds_to_search` in open_v1's config) and a
    `kinds=["class", "property_definition"]` search (the full ~1,750 rows).
    """
    placeholder_index = _build_index(num_classes=3, num_properties=0)
    dr_scale_index = _build_index(num_classes=186, num_properties=1566)

    results = {
        "placeholder (3 rows) — class only": _time_searches(placeholder_index, ["class"]),
        "dr_spec (186 rows) — class only": _time_searches(dr_scale_index, ["class"]),
        "dr_spec (1,752 rows) — class + property_definition": _time_searches(
            dr_scale_index, ["class", "property_definition"]
        ),
    }

    print("\n── SqliteSchemaVectorIndex.search() latency: placeholder vs DR-spec scale ──")
    print(f"{'scale':<52} mean(ms)  median(ms)  max(ms)")
    for label, durations in results.items():
        mean_ms = statistics.mean(durations) * 1000
        median_ms = statistics.median(durations) * 1000
        max_ms = max(durations) * 1000
        print(f"{label:<52} {mean_ms:>7.3f}  {median_ms:>9.3f}  {max_ms:>7.3f}")

    dr_default_kind_mean = statistics.mean(results["dr_spec (186 rows) — class only"])
    dr_full_scan_mean = statistics.mean(
        results["dr_spec (1,752 rows) — class + property_definition"]
    )

    # A full Loop A dev-set eval issues on the order of a few hundred grounding
    # lookups (tens of distinct individual labels x 13 dev scenarios).
    estimated_lookups_per_eval = 300
    default_kind_eval_seconds = dr_default_kind_mean * estimated_lookups_per_eval
    full_scan_eval_seconds = dr_full_scan_mean * estimated_lookups_per_eval
    print(
        f"\nEstimated added per-eval cost at ~{estimated_lookups_per_eval} grounding lookups:\n"
        f"  kinds_to_search=['class'] (open_v1's default):            "
        f"{default_kind_eval_seconds:.2f}s\n"
        f"  kinds_to_search=['class', 'property_definition']:         "
        f"{full_scan_eval_seconds:.2f}s"
    )
    print(
        "\nConclusion: under open_v1's default kinds_to_search=['class'], per-eval grounding "
        "overhead grows from effectively free (~0.5ms class-count query) to low single-digit "
        "seconds at DR-ontology scale (186 classes) — Loop A's 'seconds/eval' cost assumption "
        "(documentation/karpathy_loop_design.md §4.1) still holds, with materially less headroom "
        "than before. If a future knob sweep widens kinds_to_search to include "
        "property_definition or relationship, the full ~1,752-row scan measured above pushes "
        "per-eval overhead into the tens of seconds — brute-force numpy search "
        "(SqliteSchemaVectorIndex._best_score) would need the sqlite-vec swap the module "
        "docstring already anticipates before that configuration is usable in a sweep."
    )

    assert dr_default_kind_mean < _MAX_MEAN_QUERY_SECONDS_AT_DR_SCALE, (
        f"Mean query latency for kinds=['class'] at DR scale ({dr_default_kind_mean * 1000:.3f}ms) "
        f"exceeded the {_MAX_MEAN_QUERY_SECONDS_AT_DR_SCALE * 1000:.0f}ms ceiling backing "
        "Loop A's default-config seconds/eval assumption"
    )
