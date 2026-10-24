"""
Seed a COMPLETED pipeline run into the isolated E2E database without any LLM call.

Mirrors ``POST /api/pipelines/{pipeline_type}/run`` (adapters/web/pipelines_routes.py)
except that the orchestrator is replaced by a caller-supplied ``output_summary``:
a batch is created, the run row is written with the same type-specific data the
route derives from the request (``build_run_specific_data``), then the run is
marked completed with the given output.

Reads one JSON object on stdin and prints ``{"run_id": ..., "batch_id": ...}``:

    {
      "db_url": "sqlite:///./datafiles/e2e-test/local.db",
      "pipeline_type": "schema_extraction" | "individual_extraction",
      "request": { ...the PipelineRunRequest body the UI would POST... },
      "configuration_version": 1,
      "output_summary": { ...candidates/connections or triples... }
    }

Run from ``local-server/`` with the backend venv (see ux/e2e/fixtures/pipeline-runs.ts).
"""

import json
import os
import sys

sys.path.insert(0, os.getcwd())

from adapters.factories.orchestrator_factory import build_run_specific_data  # noqa: E402
from adapters.persistence.sqlite.batch_repo import BatchRepository  # noqa: E402
from adapters.persistence.sqlite.connection import (  # noqa: E402
    create_local_db_engine,
    create_session_factory,
)
from adapters.persistence.sqlite.pipeline_run_repo import PipelineRepository  # noqa: E402
from domain.pipelines.entities import PipelineRunStatus, PipelineType  # noqa: E402


def main() -> None:
    """Create the batch and completed run described on stdin."""
    payload = json.load(sys.stdin)
    pipeline_type = PipelineType(payload["pipeline_type"])
    request = payload["request"]

    engine = create_local_db_engine(payload["db_url"])
    session_factory = create_session_factory(engine)
    batch_repo = BatchRepository(session_factory)
    run_repo = PipelineRepository(session_factory)

    batch = batch_repo.create()
    batch_repo.update_started_at(batch.id)
    run = run_repo.create(
        batch_run_id=batch.id,
        pipeline_type=pipeline_type,
        implementation_id=request["implementation_id"],
        configuration_ref=request["configuration_ref"],
        configuration_slug=request["configuration_ref"],
        configuration_version=int(payload.get("configuration_version", 1)),
        specific_data=build_run_specific_data(pipeline_type, request) or None,
    )
    run_repo.update_summaries(run.id, output_summary=payload["output_summary"], llm_metadata={})
    run_repo.update_status(run.id, PipelineRunStatus.COMPLETED)
    batch_repo.update_completed_at(batch.id)
    batch_repo.update_status(batch.id, batch_repo.compute_aggregate_status(batch.id))
    engine.dispose()

    print(json.dumps({"run_id": run.id, "batch_id": batch.id}))


if __name__ == "__main__":
    main()
