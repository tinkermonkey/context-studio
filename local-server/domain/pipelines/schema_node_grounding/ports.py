"""
Port definitions for the schema node grounding pipeline.
"""

from __future__ import annotations

from typing import Protocol

from domain.pipelines.schema_node_grounding.scoring import GroundingCandidate


class GroundingAdapterPort(Protocol):
    """Contract for external knowledge-source adapters used by the grounding orchestrator."""

    async def query_sources(
        self,
        label: str,
        sources: list[str],
    ) -> list[GroundingCandidate]:
        """
        Query one or more external sources for grounding candidates matching *label*.

        Args:
            label: Schema node label to ground
            sources: Source identifiers to query (e.g. ["DBpedia", "ConceptNet"])

        Returns:
            Normalised candidates from all requested sources
        """
        ...
