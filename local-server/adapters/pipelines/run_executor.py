"""
In-process background executor for pipeline runs.

Long pipeline runs (refinement passes over hundreds of entities) do not fit in
an HTTP request. A run submitted here is stored PENDING with its input; worker
threads claim pending runs one at a time, execute them through the
orchestrator factory and record status, progress and errors on the run.

Each worker is a thread with its own event loop, so a pipeline that does
synchronous work (NLP, embeddings) never blocks the API's event loop. Runs
left RUNNING when the server stopped are marked INTERRUPTED at startup; the
batch resume endpoint re-queues them.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Callable

from adapters.factories.orchestrator_factory import (
    build_orchestrator_services,
    create_orchestrator,
    create_pipeline_state,
)
from adapters.persistence.sqlite.batch_repo import BatchRepository
from adapters.persistence.sqlite.pipeline_run_repo import PipelineRepository
from domain.pipelines.entities import PipelineRun, PipelineRunStatus, PipelineType
from domain.pipelines.ports import LLMProvider
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from utils.logger import get_logger

_logger = get_logger(__name__)


class UnknownPipelineError(LookupError):
    """The requested pipeline implementation or configuration is not registered."""


class BackgroundRunExecutor:
    """
    Runs pending pipeline runs on background worker threads.

    Args:
        runs: Pipeline run repository (also the orchestrators' status writer)
        batches: Batch repository, for batch timestamps and aggregate status
        implementations: Registered pipeline implementations
        configurations: Registered pipeline configurations
        llm_provider: LLM provider handed to orchestrators
        app_state: Holder of the wired adapters orchestrators draw on (app.state)
        workers: Number of worker threads (runs executed at once)
        poll_seconds: How often an idle worker looks for runs submitted elsewhere
    """

    def __init__(
        self,
        runs: PipelineRepository,
        batches: BatchRepository,
        implementations: PipelineImplementationRegistry,
        configurations: PipelineConfigurationRegistry,
        llm_provider: LLMProvider,
        app_state: Any,
        workers: int = 1,
        poll_seconds: float = 2.0,
    ) -> None:
        self._runs = runs
        self._batches = batches
        self._implementations = implementations
        self._configurations = configurations
        self._llm_provider = llm_provider
        self._app_state = app_state
        self._workers = max(1, workers)
        self._poll_seconds = poll_seconds
        self._wake = threading.Event()
        self._stopping = threading.Event()
        self._threads: list[threading.Thread] = []
        self._active: dict[str, tuple[asyncio.AbstractEventLoop, asyncio.Task]] = {}
        self._lock = threading.Lock()

    # ==================== Lifecycle ====================

    def start(self) -> None:
        """Mark runs left RUNNING as INTERRUPTED, then start the workers."""
        for batch_id in self._runs.mark_running_interrupted():
            _logger.warning("Pipeline runs in batch %s were interrupted by a restart", batch_id)
            self._refresh_batch(batch_id)
        self._stopping.clear()
        for index in range(self._workers):
            thread = threading.Thread(
                target=self._worker, name=f"pipeline-run-worker-{index}", daemon=True
            )
            thread.start()
            self._threads.append(thread)
        _logger.info("Background run executor started with %d worker(s)", self._workers)

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the workers; a run still executing is marked INTERRUPTED."""
        self._stopping.set()
        self._wake.set()
        with self._lock:
            for loop, task in self._active.values():
                loop.call_soon_threadsafe(task.cancel)
        for thread in self._threads:
            thread.join(timeout)
        self._threads = []

    # ==================== Submitting and cancelling ====================

    def submit(
        self,
        pipeline_type: PipelineType,
        implementation_id: str,
        configuration_ref: str,
        input_data: dict[str, Any],
        specific_data: dict[str, Any] | None = None,
    ) -> PipelineRun:
        """
        Store a PENDING run with its input for a worker to execute.

        Args:
            pipeline_type: The pipeline type
            implementation_id: Registered implementation
            configuration_ref: Registered configuration (its latest version is pinned)
            input_data: The pipeline's input
            specific_data: Type-specific run fields (see build_run_specific_data)

        Returns:
            The PENDING run

        Raises:
            UnknownPipelineError: The implementation or configuration is not registered
            PipelineStorageError: The run could not be stored
        """
        if self._implementations.get(pipeline_type, implementation_id) is None:
            raise UnknownPipelineError(
                f"Implementation not found: {pipeline_type.value}:{implementation_id}"
            )
        config_version = self._configurations.get_latest(
            pipeline_type, implementation_id, configuration_ref
        )
        if config_version is None:
            raise UnknownPipelineError(f"Configuration not found: {configuration_ref}")

        batch = self._batches.create()
        run = self._runs.create(
            batch_run_id=batch.id,
            pipeline_type=pipeline_type,
            implementation_id=implementation_id,
            configuration_ref=configuration_ref,
            configuration_slug=config_version.config_ref,
            configuration_version=config_version.version,
            specific_data=specific_data or None,
            input_data=input_data,
        )
        self._configurations.mark_version_referenced(
            pipeline_type, implementation_id, config_version.config_ref, config_version.version
        )
        self._batches.update_started_at(batch.id)
        self.wake()
        return run

    def wake(self) -> None:
        """Tell idle workers there is a pending run to claim."""
        self._wake.set()

    def cancel(self, run_id: str) -> bool:
        """
        Cancel a run: a PENDING run at once, a RUNNING one at its next await.

        Returns:
            True if the run was cancelled or its cancellation requested; False if
            it is not pending and not executing in this process
        """
        run = self._runs.get(run_id)
        if run is None:
            return False
        if self._runs.cancel_if_pending(run_id):
            self._refresh_batch(run.batch_run_id, finished=True)
            return True
        with self._lock:
            active = self._active.get(run_id)
        if active is None:
            return False
        loop, task = active
        loop.call_soon_threadsafe(task.cancel)
        return True

    # ==================== Workers ====================

    def _worker(self) -> None:
        asyncio.run(self._work_loop())

    async def _work_loop(self) -> None:
        while not self._stopping.is_set():
            try:
                claimed = self._runs.claim_next_pending()
            except Exception:
                _logger.exception("Could not claim a pending pipeline run")
                claimed = None
            if claimed is None:
                self._wake.wait(self._poll_seconds)
                self._wake.clear()
                continue
            run, input_data = claimed
            await self._execute(run, input_data)

    async def _execute(self, run: PipelineRun, input_data: dict[str, Any]) -> None:
        self._refresh_batch(run.batch_run_id)
        task = asyncio.ensure_future(self._run_pipeline(run, input_data))
        with self._lock:
            self._active[run.id] = (asyncio.get_running_loop(), task)
        try:
            await task
        except asyncio.CancelledError:
            status = (
                PipelineRunStatus.INTERRUPTED
                if self._stopping.is_set()
                else PipelineRunStatus.CANCELLED
            )
            self._record(lambda: self._runs.update_status(run.id, status))
            _logger.info("Pipeline run %s %s", run.id, status.value)
        except Exception as exc:
            _logger.exception("Pipeline run %s failed", run.id)
            reason = str(exc) or type(exc).__name__
            self._record(
                lambda: self._runs.update_failure_info(
                    run.id, reason, output_summary={"error": reason}
                )
            )
        finally:
            with self._lock:
                self._active.pop(run.id, None)
            self._refresh_batch(run.batch_run_id, finished=True)

    async def _run_pipeline(self, run: PipelineRun, input_data: dict[str, Any]) -> None:
        impl_class = self._implementations.get(run.pipeline_type, run.implementation_id)
        config_version = self._configurations.get_version(
            run.pipeline_type,
            run.implementation_id,
            run.configuration_slug,
            run.configuration_version,
        )
        if impl_class is None or config_version is None:
            raise UnknownPipelineError(
                f"Pipeline {run.pipeline_type.value}:{run.implementation_id} with configuration "
                f"{run.configuration_slug} v{run.configuration_version} is no longer registered"
            )
        services = build_orchestrator_services(
            self._app_state, config_version.config, run.id, self._runs
        )
        orchestrator = create_orchestrator(impl_class, self._llm_provider, services)
        state = create_pipeline_state(run.id, run.pipeline_type, input_data, self._llm_provider)

        result_state = await orchestrator.execute(state)

        output_summary = dict(result_state.result or {})
        if result_state.parse_warnings:
            output_summary["warnings"] = result_state.parse_warnings
        self._runs.update_summaries(run_id=run.id, output_summary=output_summary, llm_metadata={})
        proposal_id = output_summary.get("proposal_id")
        if isinstance(proposal_id, str) and proposal_id:
            self._runs.set_proposal_id(run.id, proposal_id)
        self._runs.update_status(run.id, result_state.current_status)

    # ==================== Bookkeeping ====================

    def _refresh_batch(self, batch_id: str, finished: bool = False) -> None:
        """Recompute the batch's aggregate status (and completed_at when a run ended)."""

        def refresh() -> None:
            if finished:
                self._batches.update_completed_at(batch_id)
            self._batches.update_status(batch_id, self._batches.compute_aggregate_status(batch_id))

        self._record(refresh)

    @staticmethod
    def _record(write: Callable[[], Any]) -> None:
        """Run a bookkeeping write, logging (not raising) a storage failure."""
        try:
            write()
        except Exception:
            _logger.exception("Could not record pipeline run state")
