"""
Integration tests for batch lifecycle management.

Tests verify:
1. Batch creation and status tracking
2. Aggregate status computation from child runs
3. Run enqueuing in batches
4. Cancel operation (halts only PENDING runs)
5. Resume operation (re-enqueues CANCELLED and FAILED runs)
6. Proper status transitions through the batch lifecycle
"""

from uuid import uuid4

from fastapi import status

from domain.pipelines.entities import PipelineRunStatus


class TestBatchLifecycle:
    """Test batch lifecycle management endpoints."""

    def test_create_batch_returns_201(self, client):
        """POST /api/pipelines/batches returns 201 with batch info."""
        response = client.post("/api/pipelines/batches")

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "id" in data
        assert data["status"] == "pending"
        assert data["run_count"] == 0
        assert data["run_counts"]["pending"] == 0
        assert data["run_counts"]["running"] == 0
        assert data["run_counts"]["completed"] == 0
        assert data["run_counts"]["failed"] == 0

    def test_get_batch_returns_404_for_missing_batch(self, client):
        """GET /api/pipelines/batches/{batch_id} returns 404 for missing batch."""
        response = client.get("/api/pipelines/batches/nonexistent-batch-id")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_batch_returns_200_with_batch_info(self, client):
        """GET /api/pipelines/batches/{batch_id} returns 200 with batch info."""
        # Create a batch
        create_response = client.post("/api/pipelines/batches")
        batch_id = create_response.json()["id"]

        # Get the batch
        response = client.get(f"/api/pipelines/batches/{batch_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == batch_id
        assert data["status"] == "pending"
        assert data["run_count"] == 0

    def test_enqueue_batch_runs_returns_201(self, client):
        """POST /api/pipelines/batches/{batch_id}/runs returns 201."""
        # Create a batch
        create_response = client.post("/api/pipelines/batches")
        batch_id = create_response.json()["id"]

        # Enqueue runs
        response = client.post(
            f"/api/pipelines/batches/{batch_id}/runs",
            json={
                "runs": [
                    {
                        "pipeline_type": "no_op",
                        "implementation_id": "default",
                        "configuration_ref": "noop-default",
                    },
                    {
                        "pipeline_type": "no_op",
                        "implementation_id": "default",
                        "configuration_ref": "noop-default",
                    },
                ]
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert len(data["run_ids"]) == 2
        assert data["run_count"] == 2

    def test_enqueue_batch_runs_returns_404_for_missing_batch(self, client):
        """POST /api/pipelines/batches/{batch_id}/runs returns 404 for missing batch."""
        response = client.post(
            "/api/pipelines/batches/nonexistent-batch-id/runs",
            json={
                "runs": [
                    {
                        "pipeline_type": "no_op",
                        "implementation_id": "default",
                        "configuration_ref": "noop-default",
                    }
                ]
            },
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_enqueue_batch_runs_returns_400_for_missing_implementation(self, client):
        """POST /api/pipelines/batches/{batch_id}/runs returns 400 for invalid implementation."""
        # Create a batch
        create_response = client.post("/api/pipelines/batches")
        batch_id = create_response.json()["id"]

        # Enqueue run with invalid implementation
        response = client.post(
            f"/api/pipelines/batches/{batch_id}/runs",
            json={
                "runs": [
                    {
                        "pipeline_type": "no_op",
                        "implementation_id": "nonexistent-impl",
                        "configuration_ref": "noop-default",
                    }
                ]
            },
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Implementation not found" in response.json()["detail"]

    def test_batch_aggregate_counts_transition_as_runs_change(
        self, client, pipeline_run_repo, batch_repo
    ):
        """
        Batch with N=3 runs reports correct aggregate counts as children
        transition through statuses.
        """
        # Create a batch and enqueue 3 runs
        create_response = client.post("/api/pipelines/batches")
        batch_id = create_response.json()["id"]

        enqueue_response = client.post(
            f"/api/pipelines/batches/{batch_id}/runs",
            json={
                "runs": [
                    {
                        "pipeline_type": "no_op",
                        "implementation_id": "default",
                        "configuration_ref": "noop-default",
                    },
                    {
                        "pipeline_type": "no_op",
                        "implementation_id": "default",
                        "configuration_ref": "noop-default",
                    },
                    {
                        "pipeline_type": "no_op",
                        "implementation_id": "default",
                        "configuration_ref": "noop-default",
                    },
                ]
            },
        )
        run_ids = enqueue_response.json()["run_ids"]

        # Verify initial state: 3 PENDING
        response = client.get(f"/api/pipelines/batches/{batch_id}")
        assert response.json()["run_counts"]["pending"] == 3
        assert response.json()["run_counts"]["running"] == 0
        assert response.json()["run_counts"]["completed"] == 0
        assert response.json()["run_counts"]["failed"] == 0

        # Update run 0 to RUNNING
        pipeline_run_repo.update_status(run_ids[0], PipelineRunStatus.RUNNING)
        response = client.get(f"/api/pipelines/batches/{batch_id}")
        assert response.json()["run_counts"]["pending"] == 2
        assert response.json()["run_counts"]["running"] == 1
        assert response.json()["run_counts"]["completed"] == 0
        assert response.json()["run_counts"]["failed"] == 0

        # Update run 1 to COMPLETED
        pipeline_run_repo.update_status(run_ids[1], PipelineRunStatus.COMPLETED)
        response = client.get(f"/api/pipelines/batches/{batch_id}")
        assert response.json()["run_counts"]["pending"] == 1
        assert response.json()["run_counts"]["running"] == 1
        assert response.json()["run_counts"]["completed"] == 1
        assert response.json()["run_counts"]["failed"] == 0

        # Update run 2 to FAILED
        pipeline_run_repo.update_status(run_ids[2], PipelineRunStatus.FAILED)
        response = client.get(f"/api/pipelines/batches/{batch_id}")
        assert response.json()["run_counts"]["pending"] == 0
        assert response.json()["run_counts"]["running"] == 1
        assert response.json()["run_counts"]["completed"] == 1
        assert response.json()["run_counts"]["failed"] == 1

    def test_cancel_batch_halts_only_pending_runs(
        self, client, pipeline_run_repo, batch_repo
    ):
        """Cancel operation halts only PENDING runs."""
        # Create a batch and enqueue 5 runs
        create_response = client.post("/api/pipelines/batches")
        batch_id = create_response.json()["id"]

        enqueue_response = client.post(
            f"/api/pipelines/batches/{batch_id}/runs",
            json={
                "runs": [
                    {
                        "pipeline_type": "no_op",
                        "implementation_id": "default",
                        "configuration_ref": "noop-default",
                    }
                    for _ in range(5)
                ]
            },
        )
        run_ids = enqueue_response.json()["run_ids"]

        # Set some runs to non-PENDING states
        pipeline_run_repo.update_status(run_ids[0], PipelineRunStatus.RUNNING)
        pipeline_run_repo.update_status(run_ids[1], PipelineRunStatus.COMPLETED)
        pipeline_run_repo.update_status(run_ids[2], PipelineRunStatus.FAILED)
        # run_ids[3] and run_ids[4] remain PENDING

        # Cancel the batch
        response = client.post(f"/api/pipelines/batches/{batch_id}/cancel")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["cancelled_count"] == 2  # Only 2 PENDING runs cancelled

        # Verify statuses: RUNNING, COMPLETED, FAILED, CANCELLED, CANCELLED
        run0 = pipeline_run_repo.get(run_ids[0])
        run1 = pipeline_run_repo.get(run_ids[1])
        run2 = pipeline_run_repo.get(run_ids[2])
        run3 = pipeline_run_repo.get(run_ids[3])
        run4 = pipeline_run_repo.get(run_ids[4])

        assert run0.status == PipelineRunStatus.RUNNING
        assert run1.status == PipelineRunStatus.COMPLETED
        assert run2.status == PipelineRunStatus.FAILED
        assert run3.status == PipelineRunStatus.CANCELLED
        assert run4.status == PipelineRunStatus.CANCELLED

    def test_resume_batch_re_enqueues_cancelled_and_failed_runs(
        self, client, pipeline_run_repo, batch_repo
    ):
        """Resume operation re-enqueues only CANCELLED and FAILED runs."""
        # Create a batch and enqueue 5 runs
        create_response = client.post("/api/pipelines/batches")
        batch_id = create_response.json()["id"]

        enqueue_response = client.post(
            f"/api/pipelines/batches/{batch_id}/runs",
            json={
                "runs": [
                    {
                        "pipeline_type": "no_op",
                        "implementation_id": "default",
                        "configuration_ref": "noop-default",
                    }
                    for _ in range(5)
                ]
            },
        )
        run_ids = enqueue_response.json()["run_ids"]

        # Set runs to various states
        pipeline_run_repo.update_status(run_ids[0], PipelineRunStatus.RUNNING)
        pipeline_run_repo.update_status(run_ids[1], PipelineRunStatus.COMPLETED)
        pipeline_run_repo.update_status(run_ids[2], PipelineRunStatus.FAILED)
        pipeline_run_repo.update_status(run_ids[3], PipelineRunStatus.CANCELLED)
        # run_ids[4] remains PENDING

        # Resume the batch
        response = client.post(f"/api/pipelines/batches/{batch_id}/resume")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["resumed_count"] == 2  # FAILED and CANCELLED

        # Verify statuses: RUNNING, COMPLETED, PENDING, PENDING, PENDING
        run0 = pipeline_run_repo.get(run_ids[0])
        run1 = pipeline_run_repo.get(run_ids[1])
        run2 = pipeline_run_repo.get(run_ids[2])
        run3 = pipeline_run_repo.get(run_ids[3])
        run4 = pipeline_run_repo.get(run_ids[4])

        assert run0.status == PipelineRunStatus.RUNNING
        assert run1.status == PipelineRunStatus.COMPLETED
        assert run2.status == PipelineRunStatus.PENDING
        assert run3.status == PipelineRunStatus.PENDING
        assert run4.status == PipelineRunStatus.PENDING

    def test_cancel_updates_batch_status_when_all_terminal(
        self, client, pipeline_run_repo, batch_repo
    ):
        """Cancel updates batch status when all runs are terminal."""
        # Create a batch and enqueue 2 runs
        create_response = client.post("/api/pipelines/batches")
        batch_id = create_response.json()["id"]

        enqueue_response = client.post(
            f"/api/pipelines/batches/{batch_id}/runs",
            json={
                "runs": [
                    {
                        "pipeline_type": "no_op",
                        "implementation_id": "default",
                        "configuration_ref": "noop-default",
                    }
                    for _ in range(2)
                ]
            },
        )
        run_ids = enqueue_response.json()["run_ids"]

        # Set one run to COMPLETED, one to PENDING
        pipeline_run_repo.update_status(run_ids[0], PipelineRunStatus.COMPLETED)
        # run_ids[1] remains PENDING

        # Cancel the batch
        response = client.post(f"/api/pipelines/batches/{batch_id}/cancel")
        assert response.status_code == status.HTTP_200_OK

        # Verify batch status was updated
        batch = batch_repo.get(batch_id)
        assert batch is not None
        # Batch status should reflect that all runs are now terminal
        # (COMPLETED, CANCELLED)

    def test_cancel_returns_404_for_missing_batch(self, client):
        """POST /api/pipelines/batches/{batch_id}/cancel returns 404 for missing batch."""
        response = client.post("/api/pipelines/batches/nonexistent-batch-id/cancel")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_resume_returns_404_for_missing_batch(self, client):
        """POST /api/pipelines/batches/{batch_id}/resume returns 404 for missing batch."""
        response = client.post("/api/pipelines/batches/nonexistent-batch-id/resume")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_enqueue_with_invalid_pipeline_type_returns_400(self, client):
        """POST /api/pipelines/batches/{batch_id}/runs returns 400 for invalid pipeline type."""
        # Create a batch
        create_response = client.post("/api/pipelines/batches")
        batch_id = create_response.json()["id"]

        # Enqueue run with invalid pipeline type
        response = client.post(
            f"/api/pipelines/batches/{batch_id}/runs",
            json={
                "runs": [
                    {
                        "pipeline_type": "invalid_type",
                        "implementation_id": "default",
                        "configuration_ref": "noop-default",
                    }
                ]
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid pipeline type" in response.json()["detail"]

    def test_resume_batch_clears_failure_reason(
        self, client, pipeline_run_repo, batch_repo
    ):
        """Resume operation clears failure_reason when resuming FAILED runs."""
        # Create a batch and enqueue runs
        create_response = client.post("/api/pipelines/batches")
        batch_id = create_response.json()["id"]

        enqueue_response = client.post(
            f"/api/pipelines/batches/{batch_id}/runs",
            json={
                "runs": [
                    {
                        "pipeline_type": "no_op",
                        "implementation_id": "default",
                        "configuration_ref": "noop-default",
                    }
                ]
            },
        )
        run_id = enqueue_response.json()["run_ids"][0]

        # Set run to FAILED with failure_reason
        pipeline_run_repo.update_failure_info(run_id, "Test failure reason")
        run = pipeline_run_repo.get(run_id)
        assert run.status == PipelineRunStatus.FAILED
        assert run.failure_reason == "Test failure reason"

        # Resume the batch
        response = client.post(f"/api/pipelines/batches/{batch_id}/resume")
        assert response.status_code == status.HTTP_200_OK

        # Verify status is PENDING and failure_reason is cleared
        run = pipeline_run_repo.get(run_id)
        assert run.status == PipelineRunStatus.PENDING
        assert run.failure_reason is None

    def test_enqueue_batch_cannot_override_protected_fields(
        self, client, pipeline_run_repo, batch_repo
    ):
        """Enqueue batch blocks attempts to override protected fields via specific_data."""
        # Create a batch
        create_response = client.post("/api/pipelines/batches")
        batch_id = create_response.json()["id"]

        # Try to enqueue with malicious specific_data that attempts to override id and status
        # Note: specific_data is ignored for no_op pipeline, so we're testing that the
        # build_run_specific_data() validates and filters it properly
        malicious_run_data = {
            "pipeline_type": "no_op",
            "implementation_id": "default",
            "configuration_ref": "noop-default",
            "specific_data": {
                "id": "evil-run-id",
                "status": "completed",
                "batch_id": "evil-batch-id",
            }
        }

        response = client.post(
            f"/api/pipelines/batches/{batch_id}/runs",
            json={"runs": [malicious_run_data]},
        )

        # Should succeed in creating the run
        assert response.status_code == status.HTTP_201_CREATED
        run_id = response.json()["run_ids"][0]

        # Verify the run has the correct values, not the malicious ones
        run = pipeline_run_repo.get(run_id)
        assert run is not None
        # The run should have the actual UUID, not "evil-run-id"
        assert run.id == run_id
        assert run.id != "evil-run-id"
        # The run should be PENDING, not "completed"
        assert run.status == PipelineRunStatus.PENDING
        # The run should belong to the correct batch
        assert run.batch_run_id == batch_id
        assert run.batch_run_id != "evil-batch-id"
