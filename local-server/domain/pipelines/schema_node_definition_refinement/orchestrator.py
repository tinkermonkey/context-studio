"""
Orchestrator for schema node definition refinement pipeline.

Refines schema node definitions based on neighborhood context (parent,
siblings, properties) and extraction examples. Uses LLM to generate
up to 3 candidate refined definitions with rationale citing inputs.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from domain.pipeline.exceptions import PipelineExecutionError, PipelineInputError
from domain.pipeline.ports import LLMProvider
from domain.pipelines.entities import PipelineRunStatus
from domain.pipelines.orchestration.base import PipelineOrchestrator, PipelineState
from domain.pipelines.refinement.neighborhood import SchemaNeighborhoodTraversal

_logger = logging.getLogger(__name__)


@dataclass
class DefinitionRefinementState(PipelineState):
    """State for definition refinement pipeline execution."""

    node_id: str = ""
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
    ) -> None:
        """
        Initialize the definition refinement orchestrator.

        Args:
            llm_provider: LLM provider for generating definitions
            traversal: SchemaNeighborhoodTraversal for context assembly
            config: Configuration dict with model, temperature, etc.
        """
        super().__init__(llm_provider)
        self._traversal = traversal
        self._config = config or {}

    def build_graph(self) -> Any:
        """
        Build and return the LangGraph state graph.

        For this single-node implementation, returns None.

        Returns:
            None (single-node execution)
        """
        return None

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
            ValueError: If required input fields are missing
        """
        if not isinstance(state, DefinitionRefinementState):
            state = DefinitionRefinementState(
                run_id=state.run_id,
                pipeline_type=state.pipeline_type,
                input_data=state.input_data,
                current_status=state.current_status,
                llm_provider=state.llm_provider,
                result=state.result,
            )

        node_id = state.input_data.get("node_id", "")
        current_definition = state.input_data.get("current_definition", "")
        groundings = state.input_data.get("groundings", [])
        extraction_usages = state.input_data.get("extraction_usages", [])

        if not node_id:
            raise PipelineInputError("node_id is required and cannot be empty")

        state.node_id = node_id
        state.current_definition = current_definition
        state.current_status = PipelineRunStatus.RUNNING

        try:
            # Step 1: Assemble context
            neighborhood = self._traversal.get_class_neighborhood(node_id)
            state.node_label = neighborhood.class_label

            # Step 2-4: Generate and score candidates
            candidates = await self._generate_candidates(
                neighborhood,
                current_definition,
                groundings,
                extraction_usages,
            )
            state.candidates = candidates

            state.current_status = PipelineRunStatus.COMPLETED
            state.result = {
                "node_id": node_id,
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
            }

        except Exception as exc:
            state.current_status = PipelineRunStatus.FAILED
            state.errors.append(str(exc))
            state.result = {
                "node_id": node_id,
                "candidates": [],
                "errors": state.errors,
            }
            raise

        return state

    async def _generate_candidates(
        self,
        neighborhood: Any,
        current_definition: str,
        groundings: list[dict[str, Any]],
        extraction_usages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Generate up to 3 candidate refined definitions.

        Args:
            neighborhood: ClassNeighborhood context
            current_definition: Current definition to refine
            groundings: External groundings (optional)
            extraction_usages: Extraction usage examples (optional)

        Returns:
            List of candidate definitions with rationale and confidence (0-3 candidates)
        """
        model = self._config.get("model", "google/gemini-3-flash-preview")
        temperature = self._config.get("temperature", 0.0)
        max_tokens = self._config.get("max_tokens", 2000)

        # Build context prompt
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
            sibling_info = ", ".join(
                [f"{s.title}" for s in neighborhood.sibling_classes[:3]]
            )
            context_parts.append(f"Sibling classes: {sibling_info}")

        if neighborhood.property_definitions:
            props_info = ", ".join([p.title for p in neighborhood.property_definitions[:3]])
            context_parts.append(f"Properties: {props_info}")

        if groundings:
            groundings_text = "\n".join(
                [f"- {g.get('label')}: {g.get('description')}" for g in groundings[:2]]
            )
            context_parts.append(f"External groundings:\n{groundings_text}")

        if extraction_usages:
            usages_text = "\n".join(
                [f"- {u.get('extracted_text')}" for u in extraction_usages[:2]]
            )
            context_parts.append(f"Extraction usages:\n{usages_text}")

        context_str = "\n".join(context_parts)

        system_prompt = (
            "You are an ontology refinement expert. Generate 2-3 alternative, improved "
            "definitions for a schema class. Each definition should be grounded in specific "
            "inputs (parent class definitions, sibling patterns, external sources, or usage "
            "examples). For each variant, cite which inputs informed it."
        )

        user_prompt = (
            f"Refine this class definition:\n\n{context_str}\n\n"
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
            _logger.warning(
                f"Failed to {error_type} LLM response for node {neighborhood.class_label}: {exc}. "
                f"No candidates generated.",
                exc_info=True,
            )
            candidates = []
        except Exception as exc:
            _logger.error(
                f"Unexpected error parsing LLM response for node {neighborhood.class_label}: {exc}",
                exc_info=True,
            )
            raise

        # Limit to 3 candidates
        return candidates[:3]
