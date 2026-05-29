"""
Canon-driven grounding tests.

The existing test files in this directory cover the orchestrator's plumbing
exhaustively (adapter wiring, scorer wiring, e2e flow, scoring math). The
tests here focus on a specific property: when the grounding adapter is fed
canon-aligned candidates (REST → DBpedia, CRDT → Wikidata), the orchestrator
surfaces them as state.result["groundings"] with the canon URIs intact.

This is the schema-level assertion that the iteration loop will eventually
optimise: did the pipeline ground the canon class against the right external
reference?
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.pipelines.entities import PipelineRunStatus, PipelineType
from domain.pipelines.schema_node_grounding.orchestrator import (
    SchemaGroundingOrchestrator,
    SchemaGroundingState,
)
from domain.pipelines.schema_node_grounding.scoring import (
    GroundingCandidate,
    ScoredCandidate,
)


_CANON_DIR = (
    Path(__file__).parent.parent.parent.parent.parent
    / "datafiles"
    / "canon"
    / "software_architecture"
)


def _canon_external_refs_for(class_identifier: str) -> list[dict]:
    """Walk paper_*.json files and collect expected_external_refs for a class."""
    refs: list[dict] = []
    for path in _CANON_DIR.glob("paper_*.json"):
        paper = json.loads(path.read_text(encoding="utf-8"))
        for ref in paper.get("expected_external_refs", []):
            if ref.get("class_identifier") == class_identifier:
                refs.append(ref)
    return refs


def _candidates_from_canon_refs(refs: list[dict]) -> list[GroundingCandidate]:
    """Materialize GroundingCandidate objects from canon external_ref entries."""
    return [
        GroundingCandidate(
            uri=ref.get("uri") or f"{ref['source']}://{ref['identifier']}",
            label=ref["identifier"],
            description=f"Canon-grounded {ref['identifier']} via {ref['source']}",
            source=ref["source"].capitalize(),
            source_score=0.9,
        )
        for ref in refs
    ]


@pytest.fixture
def canon_adapter_for(request):
    """
    Factory fixture: build a mock grounding adapter that returns canon-aligned
    candidates for any node label.

    Usage:
        adapter = canon_adapter_for("rest")
    """

    def _build(class_identifier: str):
        candidates = _candidates_from_canon_refs(
            _canon_external_refs_for(class_identifier)
        )
        mock = AsyncMock()
        mock.query_sources = AsyncMock(return_value=candidates)
        return mock

    return _build


@pytest.fixture
def passthrough_scorer():
    """Scorer that preserves source_score and computes a trivial match_confidence."""
    async def score_fn(candidates, node_label, node_type=None):
        return [
            ScoredCandidate(
                uri=c.uri,
                label=c.label,
                description=c.description,
                source=c.source,
                source_score=c.source_score,
                label_match_score=0.95,
                semantic_similarity_score=0.9,
                match_confidence=(c.source_score + 0.9) / 2,
                match_rationale="canon-aligned candidate; strong label match",
            )
            for c in candidates
        ]

    mock = MagicMock()
    mock.score_candidates = AsyncMock(side_effect=score_fn)
    return mock


def _state_for(label: str, sources: list[str]) -> SchemaGroundingState:
    return SchemaGroundingState(
        run_id=str(uuid4()),
        pipeline_type=PipelineType.SCHEMA_NODE_GROUNDING,
        input_data={
            "node_label": label,
            "node_type": "Class",
            "sources": sources,
        },
    )


class TestGroundingCanon:
    """Grounding against canon-aligned candidates."""

    def test_rest_class_grounded_to_dbpedia_and_wikidata(
        self, canon_adapter_for, passthrough_scorer
    ):
        adapter = canon_adapter_for("rest")
        orchestrator = SchemaGroundingOrchestrator(
            llm_provider=MagicMock(),
            grounding_adapter=adapter,
            scorer=passthrough_scorer,
        )
        result_state = asyncio.run(
            orchestrator.execute(_state_for("REST", ["DBpedia", "Wikidata"]))
        )
        assert result_state.current_status == PipelineRunStatus.COMPLETED

        groundings = (result_state.result or {}).get("groundings", [])
        sources_seen = {g["source"] for g in groundings}
        assert "Dbpedia" in sources_seen or "Wikidata" in sources_seen, (
            f"Expected DBpedia and/or Wikidata grounding for REST; got sources={sources_seen}"
        )

        # The DBpedia URI for REST (from canon paper_fielding_rest_dissertation_ch5)
        rest_uris = [g["uri"] for g in groundings]
        assert any("Representational_state_transfer" in u for u in rest_uris), (
            f"Expected DBpedia URI fragment 'Representational_state_transfer' "
            f"in groundings; got URIs={rest_uris}"
        )

    def test_crdt_class_grounded_to_wikidata(self, canon_adapter_for, passthrough_scorer):
        adapter = canon_adapter_for("crdt")
        orchestrator = SchemaGroundingOrchestrator(
            llm_provider=MagicMock(),
            grounding_adapter=adapter,
            scorer=passthrough_scorer,
        )
        result_state = asyncio.run(
            orchestrator.execute(_state_for("Conflict-free Replicated Data Type", ["Wikidata"]))
        )
        assert result_state.current_status == PipelineRunStatus.COMPLETED

        groundings = (result_state.result or {}).get("groundings", [])
        uris = [g["uri"] for g in groundings]
        assert any("Q17004988" in u for u in uris), (
            f"Expected Wikidata Q-id Q17004988 (CRDT) in groundings; got URIs={uris}"
        )

    def test_groundings_carry_match_confidence_and_rationale(
        self, canon_adapter_for, passthrough_scorer
    ):
        adapter = canon_adapter_for("rest")
        orchestrator = SchemaGroundingOrchestrator(
            llm_provider=MagicMock(),
            grounding_adapter=adapter,
            scorer=passthrough_scorer,
        )
        result_state = asyncio.run(
            orchestrator.execute(_state_for("REST", ["DBpedia"]))
        )
        groundings = (result_state.result or {}).get("groundings", [])
        assert groundings, "Expected at least one grounding for the REST canon class"
        for g in groundings:
            assert "match_confidence" in g
            assert 0.0 <= g["match_confidence"] <= 1.0
            assert g.get("match_rationale"), (
                f"Grounding missing rationale: {g}"
            )

    def test_empty_candidate_set_completes_with_empty_groundings(
        self, passthrough_scorer
    ):
        """If the adapter returns nothing, the pipeline completes cleanly with [] groundings."""
        empty_adapter = AsyncMock()
        empty_adapter.query_sources = AsyncMock(return_value=[])
        orchestrator = SchemaGroundingOrchestrator(
            llm_provider=MagicMock(),
            grounding_adapter=empty_adapter,
            scorer=passthrough_scorer,
        )
        result_state = asyncio.run(
            orchestrator.execute(_state_for("Nonexistent Concept", ["DBpedia"]))
        )
        assert result_state.current_status == PipelineRunStatus.COMPLETED
        assert (result_state.result or {}).get("groundings", []) == []
