"""
Integration tests for background pipeline runs (#1409): the in-process
executor claims pending runs, records progress, status and errors on them,
marks runs a restart left RUNNING as interrupted, and cancels pending and
executing runs. Real SQLite file database, the no-op pipeline, a fake LLM.
"""

import asyncio
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.persistence.sqlite.batch_repo import BatchRepository
from adapters.persistence.sqlite.connection import (
    create_local_db_engine,
    create_session_factory,
)
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.pipeline_run_repo import PipelineRepository
from adapters.pipelines.run_executor import BackgroundRunExecutor, UnknownPipelineError
from adapters.web.pipelines_routes import router
from domain.pipelines.entities import BatchStatus, PipelineRunStatus, PipelineType
from domain.pipelines.exceptions import PipelineExecutionError
from domain.pipelines.orchestration.noop import NoOpPipelineOrchestrator
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from tests.fakes.fake_llm_provider import FakeLLMProvider


@pytest.fixture
def session_factory():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_local_db_engine(f"sqlite:///{Path(tmpdir) / 'local.db'}")
        Base.metadata.create_all(engine)
        yield create_session_factory(engine)
        engine.dispose()


def make_executor(session_factory, llm=None, workers=1) -> BackgroundRunExecutor:
    """An executor over the no-op pipeline (default implementation and configuration)."""
    implementations = PipelineImplementationRegistry()
    implementations.register_impl(PipelineType.NO_OP, "default", NoOpPipelineOrchestrator)
    configurations = PipelineConfigurationRegistry()
    configurations.register(PipelineType.NO_OP, "default", "default", {"model": "test-model"})
    return BackgroundRunExecutor(
        runs=PipelineRepository(session_factory),
        batches=BatchRepository(session_factory),
        implementations=implementations,
        configurations=configurations,
        llm_provider=llm or FakeLLMProvider(),
        app_state=SimpleNamespace(),
        workers=workers,
        poll_seconds=0.05,
    )


@pytest.fixture
def executor(session_factory):
    executor = make_executor(session_factory)
    yield executor
    executor.stop()


def wait_for(predicate, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.02)
    raise AssertionError("condition not met in time")


def submit_noop(executor, items=0, item_seconds=0.0):
    return executor.submit(
        PipelineType.NO_OP,
        "default",
        "default",
        {"items": items, "item_seconds": item_seconds},
    )


def status_of(session_factory, run_id):
    return PipelineRepository(session_factory).get(run_id).status


class TestExecution:
    def test_submitted_run_is_pending_until_a_worker_claims_it(self, executor, session_factory):
        run = submit_noop(executor)

        assert run.status == PipelineRunStatus.PENDING
        assert status_of(session_factory, run.id) == PipelineRunStatus.PENDING

    def test_worker_executes_a_long_run_and_records_progress(self, executor, session_factory):
        repo = PipelineRepository(session_factory)
        run = submit_noop(executor, items=5, item_seconds=0.05)
        executor.start()

        seen_midway = wait_for(lambda: (r := repo.get(run.id)).items_done and r)
        assert seen_midway.items_total == 5
        done = wait_for(lambda: (r := repo.get(run.id)).status == PipelineRunStatus.COMPLETED and r)
        assert (done.items_done, done.items_total) == (5, 5)
        assert done.started_at is not None
        assert done.output_summary["status"] == "completed"
        # The batch status is written just after the run's
        batches = BatchRepository(session_factory)
        batch = wait_for(
            lambda: (b := batches.get(run.batch_run_id)).status == BatchStatus.COMPLETED and b
        )
        assert batch.completed_at is not None

    def test_failed_run_records_its_error(self, session_factory):
        executor = make_executor(session_factory, llm=FakeLLMProvider(should_fail=True))
        run = submit_noop(executor)
        executor.start()
        try:
            repo = PipelineRepository(session_factory)
            failed = wait_for(
                lambda: (r := repo.get(run.id)).status == PipelineRunStatus.FAILED and r
            )
            assert failed.failure_reason == "LLM provider error"
            batches = BatchRepository(session_factory)
            wait_for(lambda: batches.get(run.batch_run_id).status == BatchStatus.FAILED)
        finally:
            executor.stop()

    def test_runs_without_an_input_are_left_pending(self, executor, session_factory):
        repo = PipelineRepository(session_factory)
        batch = BatchRepository(session_factory).create()
        bare = repo.create(
            batch_run_id=batch.id,
            pipeline_type=PipelineType.NO_OP,
            implementation_id="default",
            configuration_ref="default",
            configuration_slug="default",
            configuration_version=1,
        )
        queued = submit_noop(executor)
        executor.start()

        wait_for(lambda: status_of(session_factory, queued.id) == PipelineRunStatus.COMPLETED)
        assert status_of(session_factory, bare.id) == PipelineRunStatus.PENDING

    def test_unknown_configuration_is_refused(self, executor):
        with pytest.raises(UnknownPipelineError):
            executor.submit(PipelineType.NO_OP, "default", "missing", {})
        with pytest.raises(UnknownPipelineError):
            executor.submit(PipelineType.SCHEMA_EXTRACTION, "default", "default", {})

    def test_two_workers_never_run_the_same_run_twice(self, session_factory):
        executor = make_executor(session_factory, workers=2)
        runs = [submit_noop(executor, items=2, item_seconds=0.01) for _ in range(6)]
        llm = executor._llm_provider
        executor.start()
        try:
            for run in runs:
                wait_for(
                    lambda run=run: (
                        status_of(session_factory, run.id) == PipelineRunStatus.COMPLETED
                    )
                )
            assert llm.call_count == len(runs)
        finally:
            executor.stop()


class TestRestartRecovery:
    def test_runs_left_running_become_interrupted_at_startup(self, session_factory):
        first = make_executor(session_factory)
        run = submit_noop(first)
        # A previous process claimed the run and died before finishing it
        assert PipelineRepository(session_factory).claim_next_pending()[0].id == run.id

        restarted = make_executor(session_factory)
        restarted.start()
        try:
            assert status_of(session_factory, run.id) == PipelineRunStatus.INTERRUPTED
            batch = BatchRepository(session_factory).get(run.batch_run_id)
            assert batch.status == BatchStatus.FAILED
        finally:
            restarted.stop()

    def test_stopping_marks_an_executing_run_interrupted(self, session_factory):
        executor = make_executor(session_factory)
        run = submit_noop(executor, items=500, item_seconds=0.02)
        executor.start()
        repo = PipelineRepository(session_factory)
        wait_for(lambda: repo.get(run.id).items_done)

        executor.stop()

        assert status_of(session_factory, run.id) == PipelineRunStatus.INTERRUPTED

    def test_resumed_interrupted_run_executes_again(self, session_factory):
        executor = make_executor(session_factory)
        run = submit_noop(executor, items=500, item_seconds=0.02)
        executor.start()
        repo = PipelineRepository(session_factory)
        wait_for(lambda: repo.get(run.id).items_done)
        executor.stop()

        app = FastAPI()
        app.include_router(router)
        app.state.pipeline_run_repo = repo
        app.state.batch_repo = BatchRepository(session_factory)
        restarted = make_executor(session_factory)
        app.state.run_executor = restarted
        restarted.start()
        try:
            client = TestClient(app)
            response = client.post(f"/api/pipelines/batches/{run.batch_run_id}/resume")
            assert response.json()["resumed_count"] == 1
            restarted.wake()
            # A worker claims the re-queued run and executes it from the start
            wait_for(lambda: status_of(session_factory, run.id) == PipelineRunStatus.RUNNING)
        finally:
            restarted.stop()


class TestCancel:
    def test_cancel_pending_run(self, executor, session_factory):
        run = submit_noop(executor)

        assert executor.cancel(run.id) is True

        assert status_of(session_factory, run.id) == PipelineRunStatus.CANCELLED
        batch = BatchRepository(session_factory).get(run.batch_run_id)
        assert batch.status == BatchStatus.CANCELLED

    def test_cancel_executing_run(self, executor, session_factory):
        run = submit_noop(executor, items=500, item_seconds=0.02)
        executor.start()
        repo = PipelineRepository(session_factory)
        wait_for(lambda: repo.get(run.id).items_done)

        assert executor.cancel(run.id) is True

        wait_for(lambda: status_of(session_factory, run.id) == PipelineRunStatus.CANCELLED)
        assert repo.get(run.id).items_done < 500

    def test_finished_or_unknown_run_cannot_be_cancelled(self, executor, session_factory):
        run = submit_noop(executor)
        executor.start()
        wait_for(lambda: status_of(session_factory, run.id) == PipelineRunStatus.COMPLETED)

        assert executor.cancel(run.id) is False
        assert executor.cancel("no-such-run") is False


class TestRoutes:
    @pytest.fixture
    def client(self, executor, session_factory):
        app = FastAPI()
        app.include_router(router)
        app.state.pipeline_run_repo = PipelineRepository(session_factory)
        app.state.batch_repo = BatchRepository(session_factory)
        app.state.implementation_registry = executor._implementations
        app.state.config_registry = executor._configurations
        app.state.llm_router = FakeLLMProvider()
        app.state.run_executor = executor
        executor.start()
        return TestClient(app)

    def test_async_run_returns_pending_run_at_once(self, client):
        response = client.post(
            "/api/pipelines/no_op/run",
            json={"async": True, "items": 3, "item_seconds": 0.02},
        )

        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "pending"
        assert body["items_done"] is None
        assert body["proposal_id"] is None

        done = wait_for(
            lambda: (
                (r := client.get(f"/api/pipelines/runs/{body['id']}").json())["status"]
                == "completed"
                and r
            )
        )
        assert (done["items_done"], done["items_total"]) == (3, 3)
        assert "async" not in done["output_summary"]["input_echo"]
        assert "run_async" not in done["output_summary"]["input_echo"]

    def test_runs_started_through_the_api_record_it(self, client):
        """A REST caller can't claim to be an MCP client (#1516)."""
        run = client.post(
            "/api/pipelines/no_op/run", json={"async": True, "requested_via": "mcp"}
        ).json()
        done = wait_for(
            lambda: (
                (r := client.get(f"/api/pipelines/runs/{run['id']}").json())["status"]
                == "completed"
                and r
            )
        )
        assert done["output_summary"]["input_echo"]["requested_via"] == "api"

        synchronous = client.post("/api/pipelines/no_op/run", json={"requested_via": "mcp"})
        assert synchronous.json()["output_summary"]["input_echo"]["requested_via"] == "api"

        batch = client.post("/api/pipelines/batches").json()
        enqueued = client.post(
            f"/api/pipelines/batches/{batch['id']}/runs",
            json={"runs": [{"pipeline_type": "no_op", "input_data": {"requested_via": "mcp"}}]},
        ).json()
        batch_run_id = enqueued["run_ids"][0]
        done = wait_for(
            lambda: (
                (r := client.get(f"/api/pipelines/runs/{batch_run_id}").json())["status"]
                == "completed"
                and r
            )
        )
        assert done["output_summary"]["input_echo"]["requested_via"] == "api"

    def test_async_run_with_unknown_configuration_returns_404(self, client):
        response = client.post(
            "/api/pipelines/no_op/run", json={"async": True, "configuration_ref": "nope"}
        )

        assert response.status_code == 404

    def test_cancel_route(self, client):
        started = client.post(
            "/api/pipelines/no_op/run",
            json={"async": True, "items": 500, "item_seconds": 0.02},
        ).json()
        wait_for(lambda: client.get(f"/api/pipelines/runs/{started['id']}").json()["items_done"])

        response = client.post(f"/api/pipelines/runs/{started['id']}/cancel")

        assert response.status_code == 200
        wait_for(
            lambda: (
                client.get(f"/api/pipelines/runs/{started['id']}").json()["status"] == "cancelled"
            )
        )
        assert client.post(f"/api/pipelines/runs/{started['id']}/cancel").status_code == 409
        assert client.post("/api/pipelines/runs/no-such-run/cancel").status_code == 404

    def test_enqueued_batch_runs_with_input_are_executed(self, client):
        batch = client.post("/api/pipelines/batches").json()
        enqueued = client.post(
            f"/api/pipelines/batches/{batch['id']}/runs",
            json={"runs": [{"pipeline_type": "no_op", "input_data": {"items": 1}}]},
        ).json()

        run_id = enqueued["run_ids"][0]
        wait_for(
            lambda: client.get(f"/api/pipelines/runs/{run_id}").json()["status"] == "completed"
        )
        wait_for(
            lambda: (
                client.get(f"/api/pipelines/batches/{batch['id']}").json()["status"] == "completed"
            )
        )

    def test_run_links_the_proposal_it_produced(self, client, session_factory):
        run = client.post("/api/pipelines/no_op/run", json={"async": True}).json()
        PipelineRepository(session_factory).set_proposal_id(run["id"], "proposal-1")

        assert client.get(f"/api/pipelines/runs/{run['id']}").json()["proposal_id"] == "proposal-1"

    def test_async_without_executor_returns_503(self, session_factory):
        app = FastAPI()
        app.include_router(router)
        response = TestClient(app).post("/api/pipelines/no_op/run", json={"async": True})

        assert response.status_code == 503


class TestBatchCancelAndResume:
    @pytest.fixture
    def client(self, executor, session_factory):
        app = FastAPI()
        app.include_router(router)
        app.state.pipeline_run_repo = PipelineRepository(session_factory)
        app.state.batch_repo = BatchRepository(session_factory)
        app.state.run_executor = executor
        return TestClient(app)

    def test_batch_cancel_cancels_an_executing_run(self, client, executor, session_factory):
        run = submit_noop(executor, items=500, item_seconds=0.02)
        executor.start()
        repo = PipelineRepository(session_factory)
        wait_for(lambda: repo.get(run.id).items_done)

        response = client.post(f"/api/pipelines/batches/{run.batch_run_id}/cancel")

        assert response.json()["cancelled_count"] == 1
        wait_for(lambda: status_of(session_factory, run.id) == PipelineRunStatus.CANCELLED)
        assert repo.get(run.id).items_done < 500

    def test_resume_requeues_with_fresh_progress_and_skips_runs_without_input(
        self, client, executor, session_factory
    ):
        repo = PipelineRepository(session_factory)
        run = submit_noop(executor)
        repo.update_progress(run.id, 3, 7)
        repo.set_proposal_id(run.id, "proposal-1")
        repo.update_failure_info(run.id, "boom")
        bare = repo.create(
            batch_run_id=run.batch_run_id,
            pipeline_type=PipelineType.NO_OP,
            implementation_id="default",
            configuration_ref="default",
            configuration_slug="default",
            configuration_version=1,
        )
        repo.update_failure_info(bare.id, "boom")

        response = client.post(f"/api/pipelines/batches/{run.batch_run_id}/resume")

        assert response.json()["resumed_count"] == 1
        resumed = repo.get(run.id)
        assert resumed.status == PipelineRunStatus.PENDING
        assert (resumed.items_done, resumed.items_total, resumed.proposal_id) == (None, None, None)
        assert resumed.failure_reason is None
        assert repo.get(bare.id).status == PipelineRunStatus.FAILED

    def test_a_resumed_mcp_run_records_the_api_as_its_caller(
        self, client, executor, session_factory
    ):
        """Resuming over REST can't replay an MCP client's right to propose (#1516)."""
        repo = PipelineRepository(session_factory)
        run = executor.submit(
            PipelineType.NO_OP, "default", "default", {"items": 0, "requested_via": "mcp"}
        )
        repo.update_failure_info(run.id, "boom")

        response = client.post(f"/api/pipelines/batches/{run.batch_run_id}/resume")

        assert response.json()["resumed_count"] == 1
        # The executor isn't started, so the run waits with its input
        claimed, input_data = repo.claim_next_pending()
        assert claimed.id == run.id
        assert input_data == {"items": 0, "requested_via": "api"}


class _ScriptedOrchestrator:
    """Plays one scripted attempt per execution of the run."""

    def __init__(self, attempts):
        self._attempts = iter(attempts)

    async def execute(self, state):
        return await next(self._attempts)(state)


def _fails(tokens_used, duration_ms):
    """An attempt that fails as an extraction does, carrying what its model calls cost."""

    async def attempt(state):
        raise PipelineExecutionError(
            "Extraction failed",
            llm_metadata={"model": "m", "tokens_used": tokens_used, "duration_ms": duration_ms},
        )

    return attempt


def _completes(llm_metadata=None):
    """An attempt that completes; its own tokens are in its output, as an extraction's are."""

    async def attempt(state):
        state.current_status = PipelineRunStatus.COMPLETED
        state.result = {"metadata": {"model": "m", "tokens_used": 40, "duration_ms": 3}}
        state.llm_metadata = llm_metadata or {}
        return state

    return attempt


async def _dies(state):
    raise RuntimeError("the worker hit a bug")


FIRST_ATTEMPT = {"model": "m", "tokens_used": 120, "duration_ms": 7}


class TestRequeuedRunSpend:
    """
    A re-queued run keeps what each earlier attempt's model calls cost in its
    llm_metadata's earlier_attempts; the rest of llm_metadata is its current
    attempt's alone.
    """

    @pytest.fixture
    def run_attempts(self, executor, session_factory, monkeypatch):
        """Submit a run whose executions play the given attempts; returns (run, repo)."""

        def start(*attempts):
            orchestrator = _ScriptedOrchestrator(attempts)
            monkeypatch.setattr(
                "adapters.pipelines.run_executor.create_orchestrator",
                lambda *args, **kwargs: orchestrator,
            )
            run = submit_noop(executor)
            executor.start()
            return run, PipelineRepository(session_factory)

        return start

    @staticmethod
    def _wait_for_status(repo, run, status):
        return wait_for(lambda: (r := repo.get(run.id)).status == status and r)

    def _fail_and_requeue(self, executor, repo, run):
        failed = self._wait_for_status(repo, run, PipelineRunStatus.FAILED)
        assert failed.llm_metadata == FIRST_ATTEMPT
        assert executor.requeue(run.id, {}) is True

    def test_requeue_sets_the_failed_attempts_spend_aside(self, executor, session_factory):
        repo = PipelineRepository(session_factory)
        run = submit_noop(executor)
        repo.update_summaries(run.id, llm_metadata=FIRST_ATTEMPT)
        repo.update_failure_info(run.id, "Extraction failed")

        assert executor.requeue(run.id, {}) is True

        requeued = repo.get(run.id)
        assert requeued.status == PipelineRunStatus.PENDING
        assert requeued.llm_metadata == {"earlier_attempts": [FIRST_ATTEMPT]}

    def test_requeue_of_a_run_that_recorded_nothing_leaves_llm_metadata_empty(
        self, executor, session_factory
    ):
        repo = PipelineRepository(session_factory)
        run = submit_noop(executor)
        assert executor.cancel(run.id) is True

        assert executor.requeue(run.id, {}) is True

        assert repo.get(run.id).llm_metadata == {}

    def test_failed_then_completed_keeps_the_failed_attempts_spend(self, executor, run_attempts):
        run, repo = run_attempts(_fails(120, 7), _completes())
        self._fail_and_requeue(executor, repo, run)

        done = self._wait_for_status(repo, run, PipelineRunStatus.COMPLETED)

        assert done.llm_metadata == {"earlier_attempts": [FIRST_ATTEMPT]}
        # The completed attempt's own tokens are where they always were, counted once
        assert done.output_summary["metadata"]["tokens_used"] == 40

    def test_a_completed_attempts_own_record_stands_beside_the_earlier_ones(
        self, executor, run_attempts
    ):
        triage_cost = {"decision_model": "d", "requests": 2, "cost_usd": 0.01}
        run, repo = run_attempts(_fails(120, 7), _completes(llm_metadata=triage_cost))
        self._fail_and_requeue(executor, repo, run)

        done = self._wait_for_status(repo, run, PipelineRunStatus.COMPLETED)

        assert done.llm_metadata == {**triage_cost, "earlier_attempts": [FIRST_ATTEMPT]}

    def test_failed_then_failed_records_each_attempts_spend(self, executor, run_attempts):
        run, repo = run_attempts(_fails(120, 7), _fails(300, 11))
        self._fail_and_requeue(executor, repo, run)

        second_attempt = {"model": "m", "tokens_used": 300, "duration_ms": 11}
        failed_again = wait_for(
            lambda: (
                (r := repo.get(run.id)).status == PipelineRunStatus.FAILED
                and r.llm_metadata.get("tokens_used") == 300
                and r
            )
        )
        assert failed_again.llm_metadata == {**second_attempt, "earlier_attempts": [FIRST_ATTEMPT]}

        # A third attempt starts with both set aside, oldest first
        executor.stop()
        assert executor.requeue(run.id, {}) is True
        assert repo.get(run.id).llm_metadata == {
            "earlier_attempts": [FIRST_ATTEMPT, second_attempt]
        }

    def test_failed_then_cancelled_does_not_pass_the_spend_off_as_the_cancelled_attempts(
        self, executor, run_attempts
    ):
        executing = threading.Event()

        async def hangs(state):
            executing.set()
            await asyncio.sleep(60)

        run, repo = run_attempts(_fails(120, 7), hangs)
        self._fail_and_requeue(executor, repo, run)
        wait_for(executing.is_set)

        assert executor.cancel(run.id) is True

        cancelled = self._wait_for_status(repo, run, PipelineRunStatus.CANCELLED)
        assert cancelled.llm_metadata == {"earlier_attempts": [FIRST_ATTEMPT]}

    def test_failed_then_an_unexpected_exception_does_not_pass_the_spend_off_either(
        self, executor, run_attempts
    ):
        run, repo = run_attempts(_fails(120, 7), _dies)
        self._fail_and_requeue(executor, repo, run)

        died = wait_for(
            lambda: (r := repo.get(run.id)).failure_reason == "the worker hit a bug" and r
        )
        assert died.status == PipelineRunStatus.FAILED
        assert died.llm_metadata == {"earlier_attempts": [FIRST_ATTEMPT]}


class TestStoredInput:
    def test_extraction_text_is_stored_once_and_restored_for_the_worker(
        self, session_factory, monkeypatch
    ):
        executor = make_executor(session_factory)
        executor._implementations.register_impl(
            PipelineType.INDIVIDUAL_EXTRACTION, "default", NoOpPipelineOrchestrator
        )
        executor._configurations.register(
            PipelineType.INDIVIDUAL_EXTRACTION, "default", "default", {"model": "test-model"}
        )
        seen = {}

        class RecordingOrchestrator:
            async def execute(self, state):
                seen.update(state.input_data)
                state.current_status = PipelineRunStatus.COMPLETED
                state.result = {}
                return state

        monkeypatch.setattr(
            "adapters.pipelines.run_executor.create_orchestrator",
            lambda *args, **kwargs: RecordingOrchestrator(),
        )
        text = "Alice works at Acme."
        run = executor.submit(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "default",
            "default",
            {"text": text, "ontology_id": "tax-1"},
            specific_data={"source_text": text, "source_text_hash": "x"},
        )
        repo = PipelineRepository(session_factory)
        _, stored = repo.claim_next_pending()
        assert "text" not in stored
        repo.update_status(run.id, PipelineRunStatus.PENDING)

        executor.start()
        try:
            wait_for(lambda: status_of(session_factory, run.id) == PipelineRunStatus.COMPLETED)
        finally:
            executor.stop()
        assert seen["text"] == text
        assert seen["ontology_id"] == "tax-1"
