"""
Apply service for schema node grounding pipeline.

Applies grounding candidates from a completed grounding run to an existing ontology
Class by appending ExternalReference entries. Idempotent: groundings already present
(matched by URI) are skipped.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domain.ontology.value_objects import ExternalReference
from domain.pipelines.apply_result import ApplyResult

if TYPE_CHECKING:
    from domain.ontology.ports import OntologyRepository
    from domain.pipelines.entities import PipelineRun


class SchemaGroundingApplyService:
    """
    Applies schema node grounding results to an existing Class entity.

    Adds ExternalReference entries sourced from the grounding run output.
    """

    def __init__(self, ontology_repo: "OntologyRepository") -> None:
        self._repo = ontology_repo

    def apply(
        self,
        run: "PipelineRun",
        node_id: str,
        confidence_threshold: float = 0.0,
    ) -> ApplyResult:
        """
        Apply grounding results to the given class node.

        Args:
            run: Completed grounding PipelineRun with output_summary["groundings"]
            node_id: ID of the Class to apply groundings to
            confidence_threshold: Minimum match_confidence to include a grounding

        Returns:
            ApplyResult (relationships_created used as proxy for references_added)

        Raises:
            ValueError: If node_id is empty or the class does not exist
        """
        if not node_id:
            raise ValueError("node_id is required for grounding apply")

        cls = self._repo.get_class(node_id)
        if cls is None:
            raise ValueError(f"Class {node_id} not found")

        result = ApplyResult()
        groundings = run.output_summary.get("groundings", [])
        existing_uris = {ref.identifier for ref in cls.external_references}

        for grounding in groundings:
            uri = (grounding.get("uri") or "").strip()
            confidence = grounding.get("match_confidence", 0.0)
            if not uri or confidence < confidence_threshold:
                result.relationships_skipped += 1
                continue
            if uri in existing_uris:
                result.relationships_skipped += 1
                continue
            ref = ExternalReference(
                source=grounding.get("source", "unknown"),
                identifier=uri,
                uri=uri,
            )
            cls.external_references.append(ref)
            existing_uris.add(uri)
            result.relationships_created += 1

        if result.relationships_created > 0:
            self._repo.save_class(cls)

        return result
