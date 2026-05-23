"""
Orchestrator for schema node connection refinement pipeline.

Proposes connection deltas (add/remove/modify subclass-of and property-of
relationships) to maximize the value of connections given schema state,
external groundings, and extraction examples.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from domain.pipeline.ports import LLMProvider
from domain.pipelines.orchestration.base import PipelineOrchestrator, PipelineState
from domain.pipelines.refinement.neighborhood import SchemaNeighborhoodTraversal

logger = logging.getLogger(__name__)


@dataclass
class ConnectionRefinementState(PipelineState):
    """State for connection refinement pipeline execution."""

    scope_id: str = ""
    scope_label: str = ""
    current_connections: list[dict[str, Any]] = field(default_factory=list)
    deltas: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class ConnectionRefinementOrchestrator(PipelineOrchestrator):
    """
    Orchestrator for schema node connection refinement.

    Coordinates:
    1. Current-state assembly — enumerate current connections for scope
    2. Reference signal extraction — patterns from reference materials
    3. Grounding signal extraction — connections from groundings
    4. Delta proposal — propose adds/removes/modifies ranked by expected value
    5. Confidence scoring — assess confidence in each delta
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        traversal: SchemaNeighborhoodTraversal,
        config: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize the connection refinement orchestrator.

        Args:
            llm_provider: LLM provider for proposing deltas
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
        Execute the connection refinement pipeline.

        Args:
            state: ConnectionRefinementState with:
                - input_data containing scope_id, current_connections
                - llm_provider for LLM calls

        Returns:
            Updated ConnectionRefinementState with deltas populated

        Raises:
            ValueError: If required input fields are missing
        """
        if not isinstance(state, ConnectionRefinementState):
            state = ConnectionRefinementState(
                run_id=state.run_id,
                pipeline_type=state.pipeline_type,
                input_data=state.input_data,
                current_status=state.current_status,
                llm_provider=state.llm_provider,
                result=state.result,
            )

        scope_id = state.input_data.get("scope_id", "")
        current_connections = state.input_data.get("current_connections", [])
        groundings = state.input_data.get("groundings", [])
        extraction_usages = state.input_data.get("extraction_usages", [])

        if not scope_id:
            raise ValueError("scope_id is required and cannot be empty")

        state.scope_id = scope_id
        state.current_connections = current_connections
        state.current_status = "running"

        try:
            # Step 1: Assemble current state
            neighborhood = self._traversal.get_class_neighborhood(scope_id)
            state.scope_label = neighborhood.class_label

            # Step 2-5: Propose and rank deltas
            deltas = await self._propose_deltas(
                neighborhood,
                current_connections,
                groundings,
                extraction_usages,
            )
            state.deltas = deltas

            state.current_status = "completed"
            state.result = {
                "scope_id": scope_id,
                "scope_label": state.scope_label,
                "deltas": [
                    {
                        "operation": d["operation"],
                        "subject": d["subject"],
                        "predicate": d["predicate"],
                        "object": d["object"],
                        "rationale": d["rationale"],
                        "sources_cited": d["sources_cited"],
                        "confidence": d["confidence"],
                    }
                    for d in deltas
                ],
                "total_deltas": len(deltas),
            }

        except Exception as exc:
            state.current_status = "failed"
            state.errors.append(str(exc))
            state.result = {
                "scope_id": scope_id,
                "deltas": [],
                "errors": state.errors,
            }
            raise

        return state

    async def _propose_deltas(
        self,
        neighborhood: Any,
        current_connections: list[dict[str, Any]],
        groundings: list[dict[str, Any]],
        extraction_usages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Propose connection deltas.

        Args:
            neighborhood: ClassNeighborhood context
            current_connections: Existing connections
            groundings: External groundings (optional)
            extraction_usages: Extraction usage examples (optional)

        Returns:
            List of connection deltas with operation, subjects, and rationale
        """
        model = self._config.get("model", "google/gemini-3-flash-preview")
        temperature = self._config.get("temperature", 0.0)
        max_tokens = self._config.get("max_tokens", 2000)

        # Build context prompt
        context_parts = [
            f"Schema node: {neighborhood.class_label}",
        ]

        if neighborhood.parent_class:
            context_parts.append(
                f"Parent class: {neighborhood.parent_class.title}"
            )

        if neighborhood.sibling_classes:
            sibling_info = ", ".join(
                [f"{s.title}" for s in neighborhood.sibling_classes[:3]]
            )
            context_parts.append(f"Sibling classes: {sibling_info}")

        if neighborhood.child_classes:
            children_info = ", ".join(
                [f"{c.title}" for c in neighborhood.child_classes[:3]]
            )
            context_parts.append(f"Child classes: {children_info}")

        # Current connections
        if current_connections:
            conn_text = "\n".join(
                [
                    f"- {c.get('subject', 'unknown')} -> {c.get('object', 'unknown')}"
                    for c in current_connections[:5]
                ]
            )
            context_parts.append(f"Current connections:\n{conn_text}")

        if groundings:
            groundings_text = "\n".join(
                [f"- {g.get('label')}" for g in groundings[:2]]
            )
            context_parts.append(f"External groundings:\n{groundings_text}")

        if extraction_usages:
            usages_text = "\n".join(
                [f"- {u.get('extracted_text')}" for u in extraction_usages[:2]]
            )
            context_parts.append(f"Extraction usages:\n{usages_text}")

        context_str = "\n".join(context_parts)

        system_prompt = (
            "You are an ontology connection expert. Propose high-value connection deltas "
            "(add/remove/modify) to improve schema structure. Each delta should cite specific "
            "inputs (parent patterns, grounding sources, extraction usages) justifying the change. "
            "Focus on maximizing value while minimizing noise."
        )

        user_prompt = (
            f"Propose connection improvements for this schema node:\n\n{context_str}\n\n"
            f"Return deltas as a JSON array with keys: 'operation' (add|remove|modify), "
            f"'subject', 'predicate' (relationship type), 'object', 'rationale', "
            f"'sources_cited' (list of input types), 'confidence' (0.0-1.0). "
            f"Limit to top 3-5 most valuable deltas."
        )

        response = self._call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        deltas = []
        try:
            content = response.content.strip()
            # Remove code fences if present
            match = re.match(r"^```(?:json)?\n?(.*)\n?```$", content, re.DOTALL)
            if match:
                content = match.group(1).strip()

            data = json.loads(content)
            if isinstance(data, list):
                deltas = data
            elif isinstance(data, dict) and "deltas" in data:
                deltas = data["deltas"]

            # Ensure all required fields are present
            for d in deltas:
                d.setdefault("operation", "add")
                d.setdefault("subject", "")
                d.setdefault("predicate", "")
                d.setdefault("object", "")
                d.setdefault("rationale", "")
                d.setdefault("sources_cited", [])
                d.setdefault("confidence", 0.5)
                if not isinstance(d["confidence"], (int, float)):
                    d["confidence"] = 0.5

        except json.JSONDecodeError as exc:
            logger.warning(
                f"Failed to parse LLM response as JSON for node {neighborhood.class_label}: {exc}. "
                f"Response content: {response.content[:200]}. No deltas proposed.",
                exc_info=True,
            )
            deltas = []
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning(
                f"Unexpected structure in LLM response for node {neighborhood.class_label}: {exc}. "
                f"Expected array or dict with 'deltas' key. No deltas proposed.",
                exc_info=True,
            )
            deltas = []
        except Exception as exc:
            logger.error(
                f"Unexpected error parsing LLM response for node {neighborhood.class_label}: {exc}",
                exc_info=True,
            )
            raise

        # Ensure we have at least 1 delta
        if not deltas:
            deltas = [
                {
                    "operation": "add",
                    "subject": "",
                    "predicate": "",
                    "object": "",
                    "rationale": "No deltas proposed",
                    "sources_cited": [],
                    "confidence": 0.0,
                }
            ]

        # Limit to 5 deltas
        return deltas[:5]
