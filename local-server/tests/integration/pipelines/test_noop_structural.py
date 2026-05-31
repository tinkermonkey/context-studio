"""Structural tests for NoOp pipeline.

Tests verify:
1. NoOp calls _call_llm with assertable call count via test-fake
2. NoOp apply path emits at least one sentinel change_event
3. NoOp run is fully revertable via RevertService
4. Harness self-test: loads fixture, runs NoOp, compares output
"""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.events.change_recorder import ChangeEventRecorder
from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.models import Base, ChangeEvent
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.interchange.services import set_batch_run_context
from domain.ontology.events import TaxonomyCreated
from domain.ontology.services import OntologyService
from domain.pipelines.entities import NoOpPipelineRun, PipelineRunStatus, PipelineType
from domain.pipelines.orchestration.noop import NoOpPipelineOrchestrator, NoOpPipelineState
from domain.pipelines.orchestration.noop_apply_service import NoOpApplyService
from domain.versioning.revert_service import RevertService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_llm_provider import FakeLLMProvider
from tests.integration.fixtures.pipelines.harness import compare_output, run_pipeline_against_fixture


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for integration tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session_factory(temp_db):
    """Create a session factory for the temporary database."""
    return sessionmaker(bind=temp_db)


@pytest.fixture
def event_publisher():
    """Create an in-process event publisher."""
    return InProcessEventPublisher()


@pytest.fixture
def ontology_repo(session_factory):
    """Create an ontology repository instance."""
    return SQLiteOntologyRepository(session_factory)


@pytest.fixture
def change_repo(session_factory):
    """Create a change repository instance."""
    return SQLiteChangeRepository(session_factory)


@pytest.fixture
def change_recorder(change_repo, event_publisher):
    """Create and wire up the change event recorder."""
    recorder = ChangeEventRecorder(change_repo)
    event_publisher.subscribe(TaxonomyCreated, recorder.on_taxonomy_created)
    return recorder


@pytest.fixture
def embedding_service():
    """Create a lightweight fake embedding service."""
    return FakeEmbeddingService()


@pytest.fixture
def ontology_service(change_recorder, ontology_repo, embedding_service, event_publisher):
    """Create the ontology service with all dependencies."""
    return OntologyService(ontology_repo, embedding_service, event_publisher)


@pytest.fixture
def llm_provider():
    """Create a counting fake LLM provider."""
    return FakeLLMProvider(
        response_content="Test LLM response",
        tokens_in=10,
        tokens_out=20,
    )


@pytest.fixture
def noop_orchestrator(llm_provider):
    """Create a NoOp orchestrator with the counting LLM provider."""
    return NoOpPipelineOrchestrator(llm_provider)


class TestNoOpLLMCalling:
    """Test that NoOp calls _call_llm with a counting provider."""

    @pytest.mark.asyncio
    async def test_noop_calls_llm_provider_once(self, noop_orchestrator, llm_provider):
        """Executing NoOp should call _call_llm exactly once."""
        state = NoOpPipelineState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.NO_OP,
            input_data={"text": "test input"},
        )

        # Initially, no calls made
        assert llm_provider.call_count == 0

        # Execute orchestrator
        result_state = await noop_orchestrator.execute(state)

        # Verify LLM was called exactly once
        assert llm_provider.call_count == 1
        assert result_state.current_status == "completed"

    @pytest.mark.asyncio
    async def test_noop_llm_call_includes_call_llm_in_steps(self, noop_orchestrator, llm_provider):
        """NoOp execution should include 'call_llm' in steps_completed."""
        state = NoOpPipelineState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.NO_OP,
            input_data={"text": "test input"},
        )

        result_state = await noop_orchestrator.execute(state)

        assert "call_llm" in result_state.steps_completed
        assert "initialize" in result_state.steps_completed
        assert "process" in result_state.steps_completed
        assert "finalize" in result_state.steps_completed

    @pytest.mark.asyncio
    async def test_noop_result_includes_llm_metadata(self, noop_orchestrator, llm_provider):
        """NoOp result should include LLM metadata from the call."""
        state = NoOpPipelineState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.NO_OP,
            input_data={"text": "test input"},
        )

        result_state = await noop_orchestrator.execute(state)

        assert result_state.result is not None
        assert "llm_model" in result_state.result
        assert "llm_tokens_in" in result_state.result
        assert "llm_tokens_out" in result_state.result
        assert result_state.result["llm_tokens_in"] == 10
        assert result_state.result["llm_tokens_out"] == 20


class TestNoOpChangeEvents:
    """Test that NoOp apply path emits sentinel change events."""

    @pytest.mark.asyncio
    async def test_noop_apply_emits_change_events(
        self, noop_orchestrator, ontology_service, change_repo, session_factory
    ):
        """NoOp apply should emit at least one sentinel change_event."""
        run_id = str(uuid4())

        # Set batch run context so change events are correlated with this run
        set_batch_run_context(run_id)

        try:
            # Execute NoOp pipeline orchestrator
            state = NoOpPipelineState(
                run_id=run_id,
                pipeline_type=PipelineType.NO_OP,
                input_data={"text": "test input"},
            )
            result_state = await noop_orchestrator.execute(state)

            # Verify NoOp executed successfully
            assert result_state.current_status == PipelineRunStatus.COMPLETED
            assert result_state.result is not None

            # Create a PipelineRun entity for the apply phase
            run = NoOpPipelineRun(
                id=run_id,
                batch_run_id=run_id,
                implementation_id="noop",
                configuration_slug="noop-v1",
                configuration_version=1,
                status=PipelineRunStatus.COMPLETED,
                output_summary=result_state.result,
            )

            # Apply the NoOp result (creates a sentinel individual)
            apply_service = NoOpApplyService(ontology_service)
            apply_result = apply_service.apply(run)

            # Verify at least one entity was created
            assert len(apply_result.created_individual_ids) >= 1, "Should have sentinel entity ID"

            # Verify change events were recorded for the applied entity
            session = session_factory()
            try:
                sentinel_id = apply_result.created_individual_ids[0]
                change_events = session.query(ChangeEvent).filter_by(
                    entity_id=sentinel_id,
                    batch_run_id=run_id,
                ).all()
                assert len(change_events) >= 1, "Should have at least one change_event from NoOp apply"
            finally:
                session.close()
        finally:
            # Clear the batch run context
            set_batch_run_context(None)


class TestNoOpRevert:
    """Test that NoOp apply changes are revertable via RevertService."""

    @pytest.mark.asyncio
    async def test_noop_apply_revert_round_trip(
        self,
        noop_orchestrator,
        change_repo,
        ontology_service,
        ontology_repo,
        session_factory,
    ):
        """NoOp apply changes should be fully revertable via RevertService."""
        run_id = str(uuid4())

        # Set batch run context
        set_batch_run_context(run_id)

        try:
            # Execute NoOp orchestrator
            state = NoOpPipelineState(
                run_id=run_id,
                pipeline_type=PipelineType.NO_OP,
                input_data={"text": "test input"},
            )
            result_state = await noop_orchestrator.execute(state)

            assert result_state.current_status == PipelineRunStatus.COMPLETED

            # Create PipelineRun and apply
            run = NoOpPipelineRun(
                id=run_id,
                batch_run_id=run_id,
                implementation_id="noop",
                configuration_slug="noop-v1",
                configuration_version=1,
                status=PipelineRunStatus.COMPLETED,
                output_summary=result_state.result,
            )

            apply_service = NoOpApplyService(ontology_service)
            apply_result = apply_service.apply(run)

            # Verify apply created entities
            assert len(apply_result.created_individual_ids) >= 1, "Apply should create sentinel entity"
            sentinel_id = apply_result.created_individual_ids[0]

            # Verify sentinel exists before revert
            assert ontology_repo.get_taxonomy(sentinel_id) is not None

            # Query change events for this run
            session = session_factory()
            try:
                initial_events = session.query(ChangeEvent).filter_by(batch_run_id=run_id).all()
                initial_count = len(initial_events)
                assert initial_count >= 1, "Should have at least one change event from NoOp apply"
            finally:
                session.close()

            # Revert the NoOp changes
            revert_service = RevertService(change_repo, ontology_repo)
            reverted_count = revert_service.revert(run_id)

            # Verify at least one event was reverted
            assert reverted_count >= 1, "Should have reverted at least one change event from NoOp apply"

            # Verify sentinel is gone after revert
            assert ontology_repo.get_taxonomy(sentinel_id) is None
        finally:
            # Clear the batch run context
            set_batch_run_context(None)


class TestNoOpHarnessSelfTest:
    """Harness self-test: verify run_pipeline_against_fixture works."""

    @pytest.mark.asyncio
    async def test_harness_loads_and_runs_noop_fixture(self, noop_orchestrator):
        """Harness self-test: load NoOp fixture, run it, compare output."""
        actual, expected = await run_pipeline_against_fixture(
            noop_orchestrator,
            "no_op",
            "basic",
        )

        # Verify we got actual and expected outputs
        assert actual is not None
        assert expected is not None
        assert "status" in actual
        assert "status" in expected

        # Compare outputs
        diff = compare_output(actual, expected)

        # Assertion: the diff must be empty (perfect match)
        assert diff["matches"] is True, f"Outputs do not match: {diff}"
        assert len(diff["missing_keys"]) == 0, f"Missing keys: {diff['missing_keys']}"
        assert len(diff["extra_keys"]) == 0, f"Extra keys: {diff['extra_keys']}"
        assert len(diff["mismatched_values"]) == 0, f"Mismatched values: {diff['mismatched_values']}"

    @pytest.mark.asyncio
    async def test_harness_comparison_identifies_matches(self, noop_orchestrator):
        """Comparison helper should identify matching outputs."""
        output1 = {"status": "completed", "value": 42}
        output2 = {"status": "completed", "value": 42}

        diff = compare_output(output1, output2)

        assert diff["matches"] is True
        assert len(diff["missing_keys"]) == 0
        assert len(diff["mismatched_values"]) == 0

    @pytest.mark.asyncio
    async def test_harness_comparison_identifies_differences(self, noop_orchestrator):
        """Comparison helper should identify mismatches and missing keys."""
        output1 = {"status": "completed", "value": 42}
        output2 = {"status": "completed", "value": 99, "extra": "field"}

        diff = compare_output(output1, output2)

        assert diff["matches"] is False
        assert "extra" in diff["missing_keys"]
        assert len(diff["mismatched_values"]) > 0


class TestNoOpStructuralComplete:
    """Integration test: single NoOp run exercises full smoke test."""

    @pytest.mark.asyncio
    async def test_noop_smoke_test_complete(
        self, noop_orchestrator, llm_provider, change_repo, ontology_service, ontology_repo, session_factory
    ):
        """Single NoOp run exercises _call_llm, produces change_event, and is revertable."""
        run_id = str(uuid4())

        # Set batch run context
        set_batch_run_context(run_id)

        try:
            # Verify initial LLM call count
            initial_call_count = llm_provider.call_count

            # Execute NoOp orchestrator
            state = NoOpPipelineState(
                run_id=run_id,
                pipeline_type=PipelineType.NO_OP,
                input_data={"text": "smoke test input"},
            )
            result_state = await noop_orchestrator.execute(state)

            # Assertion 1: _call_llm was invoked
            assert llm_provider.call_count > initial_call_count, "LLM should have been called"
            assert result_state.current_status == PipelineRunStatus.COMPLETED

            # Create PipelineRun and apply
            run = NoOpPipelineRun(
                id=run_id,
                batch_run_id=run_id,
                implementation_id="noop",
                configuration_slug="noop-v1",
                configuration_version=1,
                status=PipelineRunStatus.COMPLETED,
                output_summary=result_state.result,
            )

            apply_service = NoOpApplyService(ontology_service)
            apply_result = apply_service.apply(run)

            # Assertion 2: Apply produces at least one change_event
            assert len(apply_result.created_individual_ids) >= 1, "Should create sentinel entity"
            sentinel_id = apply_result.created_individual_ids[0]

            session = session_factory()
            try:
                change_events = session.query(ChangeEvent).filter_by(
                    entity_id=sentinel_id,
                    batch_run_id=run_id,
                ).all()
                assert len(change_events) >= 1, "Should have at least one change_event from NoOp apply"
            finally:
                session.close()

            # Assertion 3: Revert mechanism works end-to-end
            revert_service = RevertService(change_repo, ontology_repo)
            reverted_count = revert_service.revert(run_id)

            # Verify revert worked (at least one event reverted)
            assert reverted_count >= 1, "Should have reverted at least one change event"

            # Verify sentinel is gone
            assert ontology_repo.get_taxonomy(sentinel_id) is None
        finally:
            # Clear the batch run context
            set_batch_run_context(None)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
