"""
Pipeline run tools for the chat assistant and the MCP server: start a
refinement pass in the background, then check back on it.

A pass can take minutes to hours, so `run_refinement` returns the run id at
once and `get_run` reports status and progress. Agents still only propose: a
run never writes the ontology, and when it produces changes they arrive as a
change proposal (`get_run` returns its id) that a person reviews.
"""

from __future__ import annotations

from typing import Any, Sequence

from adapters.chat.proposal_tools import PROPOSAL_KIND
from adapters.chat.tools import (
    ToolArgumentError,
    ToolBase,
    dumps,
    error_outcome,
    required_str,
)
from adapters.factories.orchestrator_factory import build_run_specific_data
from adapters.persistence.sqlite.pipeline_run_repo import PipelineRepository
from adapters.pipelines.run_executor import BackgroundRunExecutor, UnknownPipelineError
from domain.chat.value_objects import EntityRef, ToolOutcome
from domain.ontology.exceptions import EntityNotFoundError
from domain.ontology.services import OntologyService
from domain.pipelines.entities import PipelineRun, PipelineType
from domain.pipelines.requested_via import REQUESTED_VIA, RequestedVia

PIPELINES = [t.value for t in PipelineType]
# Its defaults don't fit extraction (no configuration is registered as 'default', and
# it needs ontology_id and model), so clients extract a source instead (#1451).
INDIVIDUAL_EXTRACTION_REFUSED = (
    "run_refinement can't start individual_extraction. To extract from a document over"
    " MCP, add it with add_source, then call extract_source; get_run follows the runs it"
    " starts."
)


def run_payload(run: PipelineRun) -> dict[str, Any]:
    """
    A run's status, progress and outcome, as tools report it. A run that
    proposed nothing says why (no_proposal_reason) and how many candidates it
    skipped for each reason (skipped_by_reason).
    """
    summary = run.output_summary or {}
    return {
        "run_id": run.id,
        "pipeline": run.pipeline_type.value,
        "implementation_id": run.implementation_id,
        "status": run.status.value,
        "items_done": run.items_done,
        "items_total": run.items_total,
        "proposal_id": run.proposal_id,
        "no_proposal_reason": summary.get("no_proposal_reason"),
        "skipped_by_reason": summary.get("skipped_by_reason") or {},
        "failure_reason": run.failure_reason,
        "created_at": run.created_at,
        "started_at": run.started_at,
    }


def _references(run: PipelineRun) -> tuple[EntityRef, ...]:
    if not run.proposal_id:
        return ()
    return (EntityRef(id=run.proposal_id, kind=PROPOSAL_KIND, title="Proposal from run"),)


class RunRefinementTool(ToolBase):
    """Start a pipeline run in the background and return its id."""

    name = "run_refinement"
    description = (
        "Start a refinement pass (a pipeline run) over a taxonomy in the background and"
        " return its run_id at once; call get_run with it to follow status and progress."
        " A pass never changes the taxonomy: its changes come back as a change proposal"
        " for a person to review, and get_run returns that proposal_id when the run"
        " finishes. scope says what to refine (passed to the pipeline as is); options"
        " holds the pipeline's other inputs, plus implementation_id and"
        " configuration_ref (both default to 'default'). A taxonomy that mirrors a"
        " client's source only accepts passes its client starts over MCP. "
        + INDIVIDUAL_EXTRACTION_REFUSED
    )
    input_schema = {
        "type": "object",
        "properties": {
            "taxonomy_id": {"type": "string", "description": "Taxonomy to refine"},
            "pipeline": {
                "type": "string",
                "enum": PIPELINES,
                "description": "Pipeline type to run",
            },
            "scope": {
                "description": "What to refine, e.g. entity ids or a layer (pipeline-specific)",
            },
            "options": {
                "type": "object",
                "description": "Other pipeline inputs, implementation_id, configuration_ref",
            },
        },
        "required": ["taxonomy_id", "pipeline"],
    }

    def __init__(
        self,
        executor: BackgroundRunExecutor,
        ontology: OntologyService,
        requested_via: RequestedVia,
    ) -> None:
        self._executor = executor
        self._ontology = ontology
        self._requested_via = requested_via

    def run(self, args: dict[str, Any]) -> ToolOutcome:
        taxonomy_id = required_str(args, "taxonomy_id")
        pipeline = required_str(args, "pipeline")
        if pipeline not in PIPELINES:
            raise ToolArgumentError(f"'pipeline' must be one of {', '.join(PIPELINES)}")
        options = args.get("options") or {}
        if not isinstance(options, dict):
            raise ToolArgumentError("'options' must be an object")
        try:
            taxonomy = self._ontology.get_taxonomy(taxonomy_id)
        except EntityNotFoundError:
            return error_outcome(
                f"No taxonomy found with id {taxonomy_id!r}.", "Taxonomy not found"
            )

        ptype = PipelineType(pipeline)
        if ptype is PipelineType.INDIVIDUAL_EXTRACTION:
            return error_outcome(INDIVIDUAL_EXTRACTION_REFUSED, "Pipeline not started here")
        implementation_id = str(options.get("implementation_id") or "default")
        configuration_ref = str(options.get("configuration_ref") or "default")
        input_data = {
            **options,
            "taxonomy_id": taxonomy_id,
            "scope": args.get("scope"),
            "implementation_id": implementation_id,
            "configuration_ref": configuration_ref,
            # After the options, so a caller can't claim another entry point
            REQUESTED_VIA: self._requested_via.value,
        }
        try:
            run = self._executor.submit(
                ptype,
                implementation_id,
                configuration_ref,
                input_data,
                specific_data=build_run_specific_data(ptype, input_data),
            )
        except UnknownPipelineError as e:
            return error_outcome(str(e), "Pipeline not found")
        return ToolOutcome(
            content=dumps(run_payload(run)),
            summary=f"Started {pipeline} on {taxonomy.title}",
        )


class GetRunTool(ToolBase):
    """A run's status, progress and the proposal it produced."""

    name = "get_run"
    description = (
        "Get a pipeline run started with run_refinement or extract_source: its status"
        " (pending, running, completed, failed, cancelled, or interrupted by a server"
        " restart), progress (items_done of items_total), failure_reason, and the"
        " proposal_id of the change proposal it produced (null until then). A completed"
        " run with a null proposal_id proposed nothing and is done: no_proposal_reason"
        " says why, and skipped_by_reason counts the candidates it skipped for each"
        " reason. Review a proposal with get_proposal."
    )
    input_schema = {
        "type": "object",
        "properties": {"run_id": {"type": "string", "description": "Run id"}},
        "required": ["run_id"],
    }

    def __init__(self, runs: PipelineRepository) -> None:
        self._runs = runs

    def run(self, args: dict[str, Any]) -> ToolOutcome:
        run_id = required_str(args, "run_id")
        run = self._runs.get(run_id)
        if run is None:
            return error_outcome(f"No pipeline run found with id {run_id!r}.", "Run not found")
        payload = run_payload(run)
        progress = f" ({run.items_done}/{run.items_total})" if run.items_total else ""
        reason = payload["no_proposal_reason"]
        nothing = f", nothing proposed: {reason}" if reason and not run.proposal_id else ""
        return ToolOutcome(
            content=dumps(payload),
            summary=f"Run {run.status.value}{progress}{nothing}",
            entities=_references(run),
        )


def build_run_tools(
    executor: BackgroundRunExecutor,
    runs: PipelineRepository,
    ontology: OntologyService,
    requested_via: RequestedVia,
) -> Sequence[ToolBase]:
    """
    The run tools for one caller: the chat assistant or the MCP server.

    Runs they start record `requested_via`, which decides whether a run may
    propose changes to a mirrored taxonomy (only its client, over MCP, may).
    """
    return [RunRefinementTool(executor, ontology, requested_via), GetRunTool(runs)]
