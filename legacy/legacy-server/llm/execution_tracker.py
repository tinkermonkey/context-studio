"""Service for tracking LLM pipeline flavor executions."""

import json
import time
import uuid
from datetime import datetime
from typing import Any

from pipeline.manager import get_pipeline_session
from sqlalchemy import text
from utils.logger import get_logger

from llm.models import PipelineType, RecordSelectionRequest

logger = get_logger(__name__)


class ExecutionTracker:
    """Tracks LLM pipeline flavor executions for debugging and analysis."""

    def __init__(self):
        """Initialize the execution tracker."""
        self.logger = logger

    def start_execution(
        self,
        pipeline_flavor_id: str,
        pipeline_type: str,
        pipeline_flavor_version: int,
        request: Any,
        user_prompt: str,
    ) -> str:
        """Start tracking a new execution and return execution ID."""

        try:
            execution_id = str(uuid.uuid4())

            # Serialize request context
            if hasattr(request, "model_dump"):
                request_context = json.dumps(request.model_dump())
            else:
                request_context = json.dumps(str(request))

            # Get operations database session
            session = get_pipeline_session()

            try:
                # Insert execution record directly with raw SQL
                session.execute(
                    text("""
                    INSERT INTO pipeline_flavor_executions (
                        id, pipeline_flavor_id, pipeline_type, pipeline_flavor_version,
                        request_context, user_prompt, status, started_at
                    ) VALUES (
                        :id, :pipeline_flavor_id, :pipeline_type, :pipeline_flavor_version,
                        :request_context, :user_prompt, 'pending', datetime('now')
                    )
                """),
                    {
                        "id": execution_id,
                        "pipeline_flavor_id": pipeline_flavor_id,
                        "pipeline_type": pipeline_type,
                        "pipeline_flavor_version": pipeline_flavor_version,
                        "request_context": request_context,
                        "user_prompt": user_prompt,
                    },
                )

                session.commit()
                logger.info(f"Started execution tracking: {execution_id}")
                return execution_id

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Failed to start execution tracking: {e}")
            # Return a fallback ID so execution can continue
            return "unknown"

    def complete_execution(
        self,
        execution_id: str,
        response_message: str,
        success: bool = True,
        error_message: str | None = None,
        token_usage: dict[str, int] | None = None,
        start_time: float | None = None,
        structured_output: dict[str, Any] | None = None,
    ) -> None:
        """Complete execution tracking with response data."""

        if execution_id == "unknown":
            return

        try:
            session = get_pipeline_session()

            try:
                # Calculate execution time if start_time provided
                execution_time_ms = None
                if start_time:
                    execution_time_ms = int((time.time() - start_time) * 1000)

                # Prepare update values
                update_values = {
                    "id": execution_id,
                    "response_message": response_message,
                    "status": "success" if success else "error",
                    "error_message": error_message,
                    "completed_at": datetime.utcnow().isoformat(),
                    "execution_time_ms": execution_time_ms,
                    "input_tokens": (
                        token_usage.get("input_tokens") if token_usage else None
                    ),
                    "output_tokens": (
                        token_usage.get("output_tokens") if token_usage else None
                    ),
                    "total_tokens": (
                        token_usage.get("total_tokens") if token_usage else None
                    ),
                    "structured_output": (
                        json.dumps(structured_output) if structured_output else None
                    ),
                }

                # Update execution record
                session.execute(
                    text("""
                    UPDATE pipeline_flavor_executions
                    SET response_message = :response_message,
                        status = :status,
                        error_message = :error_message,
                        completed_at = :completed_at,
                        execution_time_ms = :execution_time_ms,
                        input_tokens = :input_tokens,
                        output_tokens = :output_tokens,
                        total_tokens = :total_tokens,
                        structured_output = :structured_output
                    WHERE id = :id
                """),
                    update_values,
                )

                session.commit()
                logger.info(f"Completed execution tracking: {execution_id}")

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Failed to complete execution tracking: {e}")

    def record_selection(self, selection_request: RecordSelectionRequest) -> str:
        """Record a user selection of an LLM suggestion."""

        try:
            selection_id = str(uuid.uuid4())
            session = get_pipeline_session()

            try:
                # Verify execution exists
                result = session.execute(
                    text("""
                    SELECT id FROM pipeline_flavor_executions 
                    WHERE id = :execution_id
                """),
                    {"execution_id": selection_request.execution_id},
                )

                if not result.fetchone():
                    raise ValueError(
                        f"Execution {selection_request.execution_id} not found"
                    )

                # Insert selection record
                session.execute(
                    text("""
                    INSERT INTO pipeline_flavor_selections (
                        id, pipeline_execution_id, record_type, record_id,
                        suggestion_field, selected_content, date_created
                    ) VALUES (
                        :id, :pipeline_execution_id, :record_type, :record_id,
                        :suggestion_field, :selected_content, datetime('now')
                    )
                """),
                    {
                        "id": selection_id,
                        "pipeline_execution_id": selection_request.execution_id,
                        "record_type": selection_request.record_type,
                        "record_id": selection_request.record_id,
                        "suggestion_field": selection_request.suggestion_field,
                        "selected_content": selection_request.selected_content,
                    },
                )

                session.commit()
                logger.info(
                    f"Recorded selection: {selection_id} for execution: {selection_request.execution_id}"
                )
                return selection_id

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Failed to record selection: {e}")
            raise

    def get_execution_analytics(
        self, pipeline_type: PipelineType | None = None, days_back: int = 30
    ) -> dict[str, Any]:
        """Get analytics for pipeline executions."""

        try:
            session = get_pipeline_session()

            try:
                # Build query with optional pipeline type filter
                where_clause = f"WHERE started_at >= date('now', '-{days_back} days')"
                if pipeline_type:
                    where_clause += f" AND pipeline_type = '{pipeline_type.value}'"

                # Get execution statistics
                result = session.execute(text(f"""
                    SELECT 
                        COUNT(*) as total_executions,
                        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful_executions,
                        AVG(CASE WHEN execution_time_ms IS NOT NULL THEN execution_time_ms ELSE 0 END) as avg_execution_time,
                        SUM(CASE WHEN total_tokens IS NOT NULL THEN total_tokens ELSE 0 END) as total_tokens_used
                    FROM pipeline_flavor_executions 
                    {where_clause}
                """))

                stats = result.fetchone()

                # Get selection rate
                selection_result = session.execute(text(f"""
                    SELECT COUNT(DISTINCT s.id) as total_selections
                    FROM pipeline_flavor_selections s
                    JOIN pipeline_flavor_executions e ON s.pipeline_execution_id = e.id
                    {where_clause}
                """))

                selection_stats = selection_result.fetchone()

                if not stats or stats.total_executions == 0:
                    return {
                        "total_executions": 0,
                        "successful_executions": 0,
                        "success_rate": 0,
                        "avg_execution_time": 0,
                        "total_tokens_used": 0,
                        "total_selections": 0,
                        "selection_rate": 0,
                    }

                total_selections = (
                    selection_stats.total_selections if selection_stats else 0
                )

                return {
                    "total_executions": stats.total_executions,
                    "successful_executions": stats.successful_executions,
                    "success_rate": (
                        stats.successful_executions / stats.total_executions
                        if stats.total_executions
                        else 0
                    ),
                    "avg_execution_time": stats.avg_execution_time,
                    "total_tokens_used": stats.total_tokens_used or 0,
                    "total_selections": total_selections,
                    "selection_rate": (
                        total_selections / stats.successful_executions
                        if stats.successful_executions
                        else 0
                    ),
                }

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Failed to get execution analytics: {e}")
            return {"error": str(e)}

    def get_flavor_execution_history(
        self, flavor_id: str, limit: int = 100
    ) -> dict[str, Any]:
        """Get execution history for a specific flavor."""

        try:
            session = get_pipeline_session()

            try:
                # Get executions for the specific flavor, ordered by most recent first
                result = session.execute(
                    text("""
                    SELECT * FROM pipeline_flavor_executions 
                    WHERE pipeline_flavor_id = :flavor_id 
                    ORDER BY started_at DESC 
                    LIMIT :limit
                """),
                    {"flavor_id": flavor_id, "limit": limit},
                )

                executions = []
                for row in result:
                    # Parse structured_output if it exists
                    structured_output = None
                    if hasattr(row, "structured_output") and row.structured_output:
                        try:
                            structured_output = json.loads(row.structured_output)
                        except (json.JSONDecodeError, AttributeError, TypeError):
                            structured_output = None

                    executions.append(
                        {
                            "id": row.id,
                            "pipeline_type": row.pipeline_type,
                            "pipeline_flavor_version": row.pipeline_flavor_version,
                            "status": row.status,
                            "request_context": row.request_context,
                            "user_prompt": row.user_prompt,
                            "response_message": row.response_message,
                            "structured_output": structured_output,
                            "execution_time_ms": row.execution_time_ms,
                            "token_usage": {
                                "input_tokens": row.input_tokens,
                                "output_tokens": row.output_tokens,
                                "total_tokens": row.total_tokens,
                            },
                            "started_at": row.started_at,
                            "completed_at": row.completed_at,
                            "error_message": row.error_message,
                        }
                    )

                # Get total count for the flavor
                count_result = session.execute(
                    text("""
                    SELECT COUNT(*) as total_count 
                    FROM pipeline_flavor_executions 
                    WHERE pipeline_flavor_id = :flavor_id
                """),
                    {"flavor_id": flavor_id},
                )

                total_count = count_result.fetchone().total_count

                return {
                    "executions": executions,
                    "total_count": total_count,
                    "flavor_id": flavor_id,
                }

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Failed to get flavor execution history: {e}")
            return {"error": str(e)}

    def get_flavor_analytics(
        self, flavor_id: str, days_back: int = 30
    ) -> dict[str, Any]:
        """Get analytics for a specific flavor."""

        try:
            session = get_pipeline_session()

            try:
                # Build query with flavor filter and date range
                where_clause = f"WHERE pipeline_flavor_id = :flavor_id AND started_at >= date('now', '-{days_back} days')"

                # Get execution statistics for the specific flavor
                result = session.execute(
                    text(f"""
                    SELECT 
                        COUNT(*) as total_executions,
                        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful_executions,
                        AVG(CASE WHEN execution_time_ms IS NOT NULL THEN execution_time_ms ELSE 0 END) as avg_execution_time,
                        SUM(CASE WHEN total_tokens IS NOT NULL THEN total_tokens ELSE 0 END) as total_tokens_used
                    FROM pipeline_flavor_executions 
                    {where_clause}
                """),
                    {"flavor_id": flavor_id},
                )

                stats = result.fetchone()

                # Get selection rate for the flavor
                selection_result = session.execute(
                    text(f"""
                    SELECT COUNT(DISTINCT s.id) as total_selections
                    FROM pipeline_flavor_selections s
                    JOIN pipeline_flavor_executions e ON s.pipeline_execution_id = e.id
                    {where_clause}
                """),
                    {"flavor_id": flavor_id},
                )

                selection_stats = selection_result.fetchone()

                if not stats or stats.total_executions == 0:
                    return {
                        "flavor_id": flavor_id,
                        "analytics": {
                            "total_executions": 0,
                            "successful_executions": 0,
                            "success_rate": 0,
                            "avg_execution_time": 0,
                            "total_tokens_used": 0,
                            "total_selections": 0,
                            "selection_rate": 0,
                        },
                        "time_range_days": days_back,
                    }

                total_selections = (
                    selection_stats.total_selections if selection_stats else 0
                )

                analytics = {
                    "total_executions": stats.total_executions,
                    "successful_executions": stats.successful_executions,
                    "success_rate": (
                        stats.successful_executions / stats.total_executions
                        if stats.total_executions
                        else 0
                    ),
                    "avg_execution_time": stats.avg_execution_time,
                    "total_tokens_used": stats.total_tokens_used or 0,
                    "total_selections": total_selections,
                    "selection_rate": (
                        total_selections / stats.successful_executions
                        if stats.successful_executions
                        else 0
                    ),
                }

                return {
                    "flavor_id": flavor_id,
                    "analytics": analytics,
                    "time_range_days": days_back,
                }

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Failed to get flavor analytics: {e}")
            return {"error": str(e)}

    def get_execution_details(self, execution_id: str) -> dict[str, Any] | None:
        """Get detailed information about a specific execution."""

        try:
            session = get_pipeline_session()

            try:
                # Get execution details
                result = session.execute(
                    text("""
                    SELECT * FROM pipeline_flavor_executions 
                    WHERE id = :execution_id
                """),
                    {"execution_id": execution_id},
                )

                execution_row = result.fetchone()
                if not execution_row:
                    return None

                # Parse structured_output if it exists
                structured_output = None
                if (
                    hasattr(execution_row, "structured_output")
                    and execution_row.structured_output
                ):
                    try:
                        structured_output = json.loads(execution_row.structured_output)
                    except (json.JSONDecodeError, AttributeError, TypeError):
                        structured_output = None

                # Get associated selections
                selections_result = session.execute(
                    text("""
                    SELECT * FROM pipeline_flavor_selections
                    WHERE pipeline_execution_id = :execution_id
                    ORDER BY date_created
                """),
                    {"execution_id": execution_id},
                )

                selections = []
                for selection_row in selections_result:
                    selections.append(
                        {
                            "id": selection_row.id,
                            "record_type": selection_row.record_type,
                            "record_id": selection_row.record_id,
                            "suggestion_field": selection_row.suggestion_field,
                            "selected_content": selection_row.selected_content,
                            "date_created": selection_row.date_created,
                        }
                    )

                return {
                    "execution": {
                        "id": execution_row.id,
                        "pipeline_type": execution_row.pipeline_type,
                        "pipeline_flavor_id": execution_row.pipeline_flavor_id,
                        "pipeline_flavor_version": execution_row.pipeline_flavor_version,
                        "status": execution_row.status,
                        "request_context": execution_row.request_context,
                        "user_prompt": execution_row.user_prompt,
                        "response_message": execution_row.response_message,
                        "structured_output": structured_output,
                        "execution_time_ms": execution_row.execution_time_ms,
                        "token_usage": {
                            "input_tokens": execution_row.input_tokens,
                            "output_tokens": execution_row.output_tokens,
                            "total_tokens": execution_row.total_tokens,
                        },
                        "started_at": execution_row.started_at,
                        "completed_at": execution_row.completed_at,
                        "error_message": execution_row.error_message,
                    },
                    "selections": selections,
                }

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Failed to get execution details: {e}")
            return None
