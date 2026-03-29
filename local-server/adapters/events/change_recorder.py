"""
Change event recorder adapter.

Subscribes to domain events and persists them as change records for auditing
and versioning. Implements the pattern where domain events are consumed by
dedicated handlers outside the domain layer.

This keeps event persistence concerns out of the domain and makes it easy to
add other event consumers (e.g., notifications, graph cache invalidation)
without modifying domain code.
"""

from domain.ports import ChangeRecordPort
from domain.extraction.events import ExtractionCompleted
from domain.pipeline.events import PipelineExecuted
from utils.logger import get_logger


logger = get_logger(__name__)


class ChangeEventRecorder:
    """
    Records domain events to the change audit trail.

    Subscribes to domain events and persists them as change records using
    a change record port. Designed to be registered with the event
    publisher during application startup.
    """

    def __init__(self, change_repo: ChangeRecordPort) -> None:
        """
        Initialize the recorder with a change repository.

        Args:
            change_repo: Port implementation for persisting changes
        """
        self.change_repo = change_repo

    def on_extraction_completed(self, event: ExtractionCompleted) -> None:
        """
        Handle ExtractionCompleted events.

        Records extraction completion to the audit trail, capturing the
        result ID, entity count, and duration.

        Args:
            event: The ExtractionCompleted event to record
        """
        try:
            change_id = self.change_repo.record_change(
                entity_id=event.result_id,
                entity_type="extraction_result",
                operation="create",
                new_state={
                    "result_id": event.result_id,
                    "entity_count": event.entity_count,
                    "duration_ms": event.duration_ms,
                },
                change_reason="Extraction processing completed",
            )
            logger.debug(
                f"Recorded extraction completion: result_id={event.result_id}, "
                f"change_event_id={change_id}"
            )
        except Exception as e:
            logger.error(
                f"Failed to record extraction completion for result_id={event.result_id}: "
                f"{type(e).__name__}: {str(e)}",
                exc_info=True,
            )

    def on_pipeline_executed(self, event: PipelineExecuted) -> None:
        """
        Handle PipelineExecuted events.

        Records pipeline execution completion to the audit trail, capturing
        the execution ID, pipeline ID, and status.

        Args:
            event: The PipelineExecuted event to record
        """
        try:
            change_id = self.change_repo.record_change(
                entity_id=event.execution_id,
                entity_type="pipeline_execution",
                operation="create",
                new_state={
                    "execution_id": event.execution_id,
                    "pipeline_id": event.pipeline_id,
                    "status": event.status,
                },
                change_reason="Pipeline execution completed",
            )
            logger.debug(
                f"Recorded pipeline execution: execution_id={event.execution_id}, "
                f"pipeline_id={event.pipeline_id}, status={event.status}, "
                f"change_event_id={change_id}"
            )
        except Exception as e:
            logger.error(
                f"Failed to record pipeline execution for execution_id={event.execution_id}: "
                f"{type(e).__name__}: {str(e)}",
                exc_info=True,
            )
