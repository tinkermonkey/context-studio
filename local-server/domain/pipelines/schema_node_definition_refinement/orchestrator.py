"""
Orchestrator for schema node definition refinement pipeline.

Two modes:
- one node (input node_id): refines the definition of a class or a property
  definition from its neighborhood (for a class: parent, siblings, properties;
  for a property: domain and range classes, sibling properties) and extraction
  examples. Uses LLM to generate up to 3 candidate refined definitions with
  rationale citing inputs; the drawer's Suggest Definition applies the one a
  person picks.
- scoped (input taxonomy_id and scope): definition enrichment (#1517), each
  class's operational definition proposed as one change proposal; see
  enrichment.py.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field, replace
from typing import Any

from domain.ontology.ports import OntologyRepository
from domain.pipelines.entities import PipelineRunStatus
from domain.pipelines.exceptions import PipelineExecutionError, PipelineInputError
from domain.pipelines.orchestration.base import (
    PipelineOrchestrator,
    PipelineState,
    llm_parameters,
)
from domain.pipelines.ports import LLMProvider, PipelineRunStatusWriter
from domain.pipelines.refinement.neighborhood import (
    ClassNeighborhood,
    PropertyNeighborhood,
    SchemaNeighborhoodTraversal,
)
from domain.pipelines.requested_via import ensure_may_propose_to
from domain.versioning.proposal_service import ProposalService

from .enrichment import DefinitionEnrichment

_logger = logging.getLogger(__name__)


@dataclass
class DefinitionRefinementState(PipelineState):
    """State for definition refinement pipeline execution."""

    node_id: str = ""
    node_type: str = "Class"
    node_label: str = ""
    current_definition: str = ""
    candidates: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class DefinitionRefinementOrchestrator(PipelineOrchestrator):
    """
    Orchestrator for schema node definition refinement.

    Coordinates:
    1. Context assembly — pull neighborhood, groundings, usages
    2. Variant generation — produce up to 3 candidate definitions via LLM
    3. Rationale attachment — explain which inputs drove each variant
    4. Confidence scoring — assess confidence in each variant
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        traversal: SchemaNeighborhoodTraversal,
        config: dict[str, Any] | None = None,
        run_id: str | None = None,
        status_writer: PipelineRunStatusWriter | None = None,
        ontology_repo: OntologyRepository | None = None,
        proposal_service: ProposalService | None = None,
    ) -> None:
        """
        Initialize the definition refinement orchestrator.

        Args:
            llm_provider: LLM provider for generating definitions
            traversal: SchemaNeighborhoodTraversal for context assembly
            config: Configuration dict with model, temperature, etc.
            ontology_repo, proposal_service: For the scoped mode (definition
                enrichment), which proposes its changes
            run_id: Pipeline run ID for writing RUNNING status
            status_writer: Optional port for writing run status to persistence
        """
        super().__init__(llm_provider, run_id, status_writer)
        self._traversal = traversal
        self._config = config or {}
        self._repo = ontology_repo
        self._proposals = proposal_service

    async def execute(self, state: PipelineState) -> PipelineState:
        """
        Execute the definition refinement pipeline.

        Args:
            state: DefinitionRefinementState with:
                - input_data containing node_id, current_definition
                - llm_provider for LLM calls

        Returns:
            Updated DefinitionRefinementState with candidates populated

        Raises:
            PipelineInputError: If required input fields are missing
            PipelineExecutionError: If pipeline execution fails
        """
        self._write_running_status()

        if not isinstance(state, DefinitionRefinementState):
            state = DefinitionRefinementState(
                run_id=state.run_id,
                pipeline_type=state.pipeline_type,
                input_data=state.input_data,
                current_status=state.current_status,
                llm_provider=state.llm_provider,
                result=state.result,
            )

        if state.input_data.get("taxonomy_id") and not state.input_data.get("node_id"):
            return await self._enrich(state)

        node_id = state.input_data.get("node_id", "")
        current_definition = state.input_data.get("current_definition", "")
        groundings = state.input_data.get("groundings", [])
        extraction_usages = state.input_data.get("extraction_usages", [])

        if not node_id:
            exc = PipelineInputError("node_id is required and cannot be empty")
            state = replace(
                state,
                current_status=PipelineRunStatus.FAILED,
                result={"error": str(exc)},
            )
            raise exc

        state = replace(
            state,
            node_id=node_id,
            current_definition=current_definition,
            current_status=PipelineRunStatus.RUNNING,
        )

        try:
            # Step 1: Assemble context
            try:
                neighborhood = self._traversal.get_node_neighborhood(node_id)
            except ValueError as exc:
                raise PipelineInputError(
                    f"No class or property definition with id '{node_id}'"
                ) from exc
            if isinstance(neighborhood, PropertyNeighborhood):
                state = replace(
                    state,
                    node_type="PropertyDefinition",
                    node_label=neighborhood.property_label,
                )
            else:
                state = replace(state, node_type="Class", node_label=neighborhood.class_label)

            # Step 2-4: Generate and score candidates
            candidates = await self._generate_candidates(
                neighborhood,
                current_definition,
                groundings,
                extraction_usages,
                model=state.input_data.get("model"),
                temperature=state.input_data.get("temperature"),
                max_tokens=state.input_data.get("max_tokens"),
            )
            state = replace(state, candidates=candidates)

            state = replace(
                state,
                current_status=PipelineRunStatus.COMPLETED,
                result={
                    "node_id": node_id,
                    "node_type": state.node_type,
                    "node_label": state.node_label,
                    "candidates": [
                        {
                            "definition": c["definition"],
                            "rationale": c["rationale"],
                            "sources_used": c["sources_used"],
                            "confidence": c["confidence"],
                        }
                        for c in candidates
                    ],
                    "total_candidates": len(candidates),
                },
            )

        except PipelineInputError:
            state = replace(state, current_status=PipelineRunStatus.FAILED)
            raise
        except PipelineExecutionError:
            state = replace(state, current_status=PipelineRunStatus.FAILED)
            raise
        except ValueError as exc:
            state = replace(state, current_status=PipelineRunStatus.FAILED)
            raise PipelineExecutionError(
                "Definition refinement encountered an unexpected error"
            ) from exc
        except Exception as exc:
            _logger.error(f"Unexpected error during definition refinement: {exc}", exc_info=True)
            state = replace(
                state,
                current_status=PipelineRunStatus.FAILED,
                result={"error": "Definition refinement encountered an unexpected error"},
            )
            raise PipelineExecutionError(
                "Definition refinement encountered an unexpected error"
            ) from exc

        return state

    async def _enrich(self, state: DefinitionRefinementState) -> DefinitionRefinementState:
        """The scoped mode: definition enrichment of a taxonomy's classes, proposed."""
        if self._repo is None or self._proposals is None:
            raise PipelineExecutionError("Definition enrichment needs the ontology and proposals")
        taxonomy_id = state.input_data["taxonomy_id"]
        taxonomy = self._repo.get_taxonomy(taxonomy_id)
        if taxonomy is None:
            raise PipelineInputError(f"No taxonomy {taxonomy_id}")
        ensure_may_propose_to(taxonomy, state.input_data)
        parameters = llm_parameters(state.input_data, self._config, 2000)
        model = parameters["model"]

        async def call_llm(system: str, user: str):
            return await self._call_llm(
                system_prompt=system,
                user_prompt=user,
                **parameters,
                response_format="json",
            )

        enrichment = DefinitionEnrichment(
            self._repo,
            self._proposals,
            call_llm,
            self._report_progress,
            concurrency=int(self._config.get("concurrency", 4)),
        )
        scope = state.input_data.get("scope")
        classes = enrichment.scope(taxonomy, scope)
        outcome = await enrichment.run(taxonomy, classes, model, state.run_id)
        warnings = [{"stage": "enrich", "class": c, "error": e} for c, e in outcome.failed]
        warnings += [{"stage": "propose", **item} for item in outcome.refused]
        return replace(
            state,
            current_status=PipelineRunStatus.COMPLETED,
            result={
                "status": "completed_with_warnings" if warnings else "completed",
                "taxonomy_id": taxonomy.id,
                "scope": scope,
                "classes": outcome.classes,
                "proposed": outcome.proposed,
                "unchanged": outcome.unchanged,
                "proposal_id": outcome.proposal_id,
                "dropped_distinguish": outcome.dropped_distinguish,
                "errors": [f"{c}: {e}" for c, e in outcome.failed][:20],
                "error_count": len(outcome.failed),
                "refused": outcome.refused,
            },
            llm_metadata=outcome.llm_metadata,
            parse_warnings=[*state.parse_warnings, *warnings],
        )

    async def _generate_candidates(
        self,
        neighborhood: ClassNeighborhood | PropertyNeighborhood,
        current_definition: str,
        groundings: list[dict[str, Any]],
        extraction_usages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Generate up to 3 candidate refined definitions.

        Args:
            neighborhood: ClassNeighborhood or PropertyNeighborhood context
            current_definition: Current definition to refine
            groundings: External groundings (optional)
            extraction_usages: Extraction usage examples (optional)
            model, temperature, max_tokens: What the run's input names; what
                it leaves out is the configuration's (llm_parameters)

        Returns:
            List of candidate definitions with rationale and confidence (0-3 candidates)
        """
        parameters = llm_parameters(
            {"model": model, "temperature": temperature, "max_tokens": max_tokens},
            self._config,
            2000,
        )
        model, temperature, max_tokens = (
            parameters["model"],
            parameters["temperature"],
            parameters["max_tokens"],
        )

        # Build context prompt
        if isinstance(neighborhood, PropertyNeighborhood):
            context_parts = _property_context(neighborhood, current_definition)
            node_kind = "property"
            node_kind_detail = "property (a relationship type between classes)"
        else:
            context_parts = _class_context(neighborhood, current_definition)
            node_kind = "class"
            node_kind_detail = "schema class"

        if groundings:
            groundings_text = "\n".join(
                [f"- {g.get('label')}: {g.get('description')}" for g in groundings[:2]]
            )
            context_parts.append(f"External groundings:\n{groundings_text}")

        if extraction_usages:
            usages_text = "\n".join([f"- {u.get('extracted_text')}" for u in extraction_usages[:2]])
            context_parts.append(f"Extraction usages:\n{usages_text}")

        context_str = "\n".join(context_parts)

        system_prompt = (
            "You are an ontology refinement expert. Generate 2-3 alternative, improved "
            f"definitions for a {node_kind_detail}. Each definition should be grounded in specific "
            "inputs (parent class definitions, sibling patterns, external sources, or usage "
            "examples). For each variant, cite which inputs informed it."
        )

        user_prompt = (
            f"Refine this {node_kind} definition:\n\n{context_str}\n\n"
            f"Return exactly 2-3 alternative definitions as a JSON array with keys: "
            f"'definition', 'rationale' (which inputs drove this variant), "
            f"'sources_used' (list of input types), 'confidence' (0.0-1.0)."
        )

        response = await self._call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        candidates = []
        try:
            content = response.content.strip()
            # Remove code fences if present
            match = re.match(r"^```(?:json)?\n?(.*)\n?```$", content, re.DOTALL)
            if match:
                content = match.group(1).strip()

            data = json.loads(content)
            if isinstance(data, list):
                candidates = data
            elif isinstance(data, dict) and "definitions" in data:
                candidates = data["definitions"]

            # Ensure all required fields are present
            for c in candidates:
                c.setdefault("definition", "")
                c.setdefault("rationale", "")
                c.setdefault("sources_used", [])
                c.setdefault("confidence", 0.5)
                if not isinstance(c["confidence"], (int, float)):
                    c["confidence"] = 0.5

        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            error_type = "parse" if isinstance(exc, json.JSONDecodeError) else "structure"
            _logger.error(
                f"Failed to {error_type} LLM response for node {neighborhood.class_label}: {exc}",
                exc_info=True,
            )
            sanitized_msg = f"LLM response validation failed for {neighborhood.class_label}"
            raise PipelineExecutionError(sanitized_msg) from exc
        except Exception as exc:
            _logger.error(
                f"Unexpected error parsing LLM response for node {neighborhood.class_label}: {exc}",
                exc_info=True,
            )
            raise

        # Limit to 3 candidates
        return candidates[:3]


def _class_context(neighborhood: ClassNeighborhood, current_definition: str) -> list[str]:
    """Prompt lines describing a class and its neighbors."""
    context_parts = [
        f"Current definition: {current_definition}",
        f"Class label: {neighborhood.class_label}",
    ]

    if neighborhood.parent_class:
        context_parts.append(
            f"Parent class: {neighborhood.parent_class.title} "
            f"(definition: {neighborhood.parent_class.description or 'none'})"
        )

    if neighborhood.sibling_classes:
        sibling_info = ", ".join([f"{s.title}" for s in neighborhood.sibling_classes[:3]])
        context_parts.append(f"Sibling classes: {sibling_info}")

    if neighborhood.property_definitions:
        props_info = ", ".join([p.title for p in neighborhood.property_definitions[:3]])
        context_parts.append(f"Properties: {props_info}")

    return context_parts


def _property_context(neighborhood: PropertyNeighborhood, current_definition: str) -> list[str]:
    """Prompt lines describing a property definition, its domain and range, and siblings."""
    context_parts = [
        f"Current definition: {current_definition}",
        f"Property label: {neighborhood.property_label}",
    ]

    for role, class_neighborhood in (
        ("Domain class (subject)", neighborhood.domain_neighborhood),
        ("Range class (object)", neighborhood.range_neighborhood),
    ):
        if class_neighborhood:
            context_parts.append(
                f"{role}: {class_neighborhood.class_label} "
                f"(definition: {class_neighborhood.class_description or 'none'})"
            )

    if neighborhood.sibling_properties:
        siblings = ", ".join([p.title for p in neighborhood.sibling_properties[:3]])
        context_parts.append(f"Sibling properties: {siblings}")

    return context_parts
