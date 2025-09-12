# LLM Traceability PRP

## Overview

Implement comprehensive LLM traceability to capture each pipeline flavor execution for debugging and refinement of prompts. This system will track every LLM service invocation with detailed context, request/response data, and user selections to enable effective prompt engineering and model performance analysis.

## Context and Research Findings

### Current Architecture Analysis

**LLM Service Infrastructure**: The codebase uses a sophisticated LLM service architecture in `llm/service.py`:
- `LLMService` class with Langchain integration for OpenAI models
- Pipeline flavor system with customizable prompts and model configurations
- Service factory pattern in `services/service_factory.py` for dependency injection
- Pipeline flavor management via `PipelineFlavorService` and database models

**Pipeline Flavor System**: Current pipeline flavors in `database/models.py`:
- `PipelineFlavor` table with id, pipeline type, title, LLM config, prompts, version tracking
- Three pipeline types: `SUGGEST_TERM_DEFINITION`, `SUGGEST_LAYER_DEFINITION`, `SUGGEST_DOMAIN_DEFINITION`
- Flavor-specific prompt templates with variable substitution
- Support for temperature, model selection, and provider configuration

**Database Architecture**: Existing patterns in `database/models.py` and migration system:
- SQLAlchemy ORM with UUID primary keys and datetime tracking
- Pipeline definitions are stored in a separate database from the nodes and links
- Use the PipelineDatabaseManager for database access
- Unlike the core database which directly manages the schema, the schema for the pipeline database should be maintained using sqlalchemy and the schema should be made to match the latest when the database is loaded
- Migrations are not necessary for this work
- Backwards compatibility is not necessary for this work
- Change events are not needed for anything in the pipeline definition database

**API Layer**: Current LLM APIs in `api/llm.py`:
- FastAPI endpoints with comprehensive error handling
- Streaming and non-streaming response support
- Request validation using Pydantic models
- Integration with existing dependency injection system

### External Research (2024 Best Practices)

**Industry Standard Patterns**: Research reveals LLM traceability best practices:
- **OpenTelemetry Integration**: Standard for LLM observability with structured span tracking
- **MLflow Tracing**: End-to-end request tracking with metadata capture
- **LangSmith Patterns**: Execution ID tracking with user selection correlation
- **Token Usage Monitoring**: Separate tracking of input/output tokens for cost analysis

**Database Schema Patterns**: Modern LLM tracing systems typically include:
- Execution tracking with unique IDs and batch correlation
- Request/response pairs with full context preservation
- User interaction tracking for feedback loops
- Performance metrics (latency, token counts, success rates)
- Debugging metadata (model parameters, prompt versions, timestamps)

**Security & Privacy**: Key considerations include:
- Data masking for sensitive content in prompts
- Configurable logging levels for production vs development
- Audit trails for compliance and debugging
- Token usage monitoring for cost control

## Implementation Requirements

### Core Components

1. **Database Tables** (extend `database/models.py`)
   - `PipelineFlavorExecution` - track each LLM invocation
   - `PipelineFlavorSelection` - track user selections of suggestions

2. **Service Extensions** (extend `llm/service.py`)
   - Execution tracking decorator
   - Response enhancement with execution IDs

3. **API Extensions** (new `api/llm_traceability.py`)
   - Selection tracking endpoint

4. **Model Updates** (extend `llm/models.py`)
   - Response models with execution IDs
   - Selection tracking request models

### Data Flow

```
User Request → LLM Service → Create Execution Record → Process Request → Update with Response → Return with Execution ID

User Selection → Selection API → Record Selection → Link to Execution Record
```

## Detailed Implementation Plan

### Task 1: Create Database Models

**File**: `database/models.py` - Add new tables

```python
class PipelineFlavorExecution(Base):
    """Track each pipeline flavor execution for debugging and analysis."""
    
    __tablename__ = "pipeline_flavor_executions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    pipeline_flavor_id = Column(String, ForeignKey("pipeline_flavors.id"), nullable=False)
    pipeline_type = Column(String, nullable=False)  # suggest_term_definition, etc.
    pipeline_flavor_version = Column(Integer, nullable=False)
    request_context = Column(JSON, nullable=False)  # Full request payload
    user_prompt = Column(Text, nullable=False)  # Formatted message sent to LLM
    response_message = Column(Text, nullable=True)  # Raw LLM response
    
    # Performance metrics
    execution_time_ms = Column(Integer, nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    
    # Status tracking
    status = Column(String, nullable=False, default="pending")  # pending, success, error
    error_message = Column(Text, nullable=True)
    
    # Timing
    started_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    pipeline_flavor = relationship("PipelineFlavor", backref="executions")


class PipelineFlavorSelection(Base):
    """Track when users select LLM suggestions."""
    
    __tablename__ = "pipeline_flavor_selections"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    pipeline_execution_id = Column(String, ForeignKey("pipeline_flavor_executions.id"), nullable=False)
    record_type = Column(String, nullable=False)  # structure_node, structure_node_link, etc.
    record_id = Column(String, nullable=False)  # Primary key of the record
    suggestion_field = Column(String, nullable=False)  # definition, title, etc.
    selected_content = Column(Text, nullable=False)  # The content that was selected
    date_created = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
    
    # Relationships  
    execution = relationship("PipelineFlavorExecution", backref="selections")
```

### Task 2: Create Migration Script

**File**: `pipeline/manager.py`

Upon load, use SqlAlchemy to ensure that the schema of the loaded pipelines database file matches the latest.

### Task 3: Extend LLM Models

**File**: `llm/models.py` - Add tracking to existing response and request models

```python
class DefinitionSuggestionResponse(DefinitionSuggestionResponse):
    """Definition suggestion response with execution tracking."""
    execution_id: str = Field(..., description="Unique execution ID for tracing")

class LayerDefinitionResponse(LayerDefinitionResponse):
    """Layer definition response with execution tracking.""" 
    execution_id: str = Field(..., description="Unique execution ID for tracing")

class DomainDefinitionResponse(DomainDefinitionResponse):
    """Domain definition response with execution tracking."""
    execution_id: str = Field(..., description="Unique execution ID for tracing")

class LLMSuccessResponse(BaseModel):
    """Success response wrapper with execution tracking."""
    success: bool = Field(True, description="Always true for success responses")
    data: DefinitionSuggestionResponse = Field(..., description="The response data")
    execution_id: str = Field(..., description="Unique execution ID for tracing")

class LayerLLMSuccessResponse(BaseModel):
    """Layer success response wrapper with execution tracking."""
    success: bool = Field(True, description="Always true for success responses")
    data: LayerDefinitionResponse = Field(..., description="The response data")
    execution_id: str = Field(..., description="Unique execution ID for tracing")

class DomainLLMSuccessResponse(BaseModel):
    """Domain success response wrapper with execution tracking."""
    success: bool = Field(True, description="Always true for success responses")  
    data: DomainDefinitionResponse = Field(..., description="The response data")
    execution_id: str = Field(..., description="Unique execution ID for tracing")

class RecordSelectionRequest(BaseModel):
    """Request model for recording user selection of LLM suggestions."""
    execution_id: str = Field(..., description="Execution ID from LLM response")
    record_type: str = Field(..., description="Type of record (structure_node, etc.)")
    record_id: str = Field(..., description="Primary key of the record")
    suggestion_field: str = Field(..., description="Field that was selected (definition, etc.)")
    selected_content: str = Field(..., description="The content that was selected")

class SelectionResponse(BaseModel):
    """Response model for selection recording."""
    success: bool = Field(..., description="Whether selection was recorded successfully")
    selection_id: str = Field(..., description="ID of the recorded selection")
    message: str = Field(..., description="Status message")

class StreamingLLMResponse(StreamingLLMResponse):
    """Streaming response model with execution tracking."""
    execution_id: Optional[str] = Field(None, description="Execution ID (set when streaming starts)")
```

### Task 4: Create Execution Tracking Service

**File**: `llm/execution_tracker.py`

```python
"""Service for tracking LLM pipeline flavor executions."""

import time
import json
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from database.models import PipelineFlavorExecution, PipelineFlavorSelection, PipelineFlavor
from llm.models import (
    DefinitionSuggestionRequest, LayerDefinitionRequest, DomainDefinitionRequest,
    PipelineType, RecordSelectionRequest
)
from utils.logger import get_logger

logger = get_logger(__name__)


class ExecutionTracker:
    """Tracks LLM pipeline flavor executions for debugging and analysis."""
    
    def __init__(self, db_session: Session):
        self.db_session = db_session
    
    def start_execution(
        self,
        pipeline_flavor: PipelineFlavor,
        request: Any,
        user_prompt: str
    ) -> str:
        """Start tracking a new execution and return execution ID."""
        
        try:
            # Create execution record
            execution = PipelineFlavorExecution(
                pipeline_flavor_id=pipeline_flavor.id,
                pipeline_type=pipeline_flavor.pipeline,
                pipeline_flavor_version=pipeline_flavor.version,
                request_context=json.dumps(request.model_dump() if hasattr(request, 'model_dump') else request),
                user_prompt=user_prompt,
                status="pending",
                started_at=datetime.utcnow()
            )
            
            self.db_session.add(execution)
            self.db_session.commit()
            
            logger.info(f"Started execution tracking: {execution.id}")
            return execution.id
            
        except Exception as e:
            logger.error(f"Failed to start execution tracking: {e}")
            self.db_session.rollback()
            # Return a fallback ID so execution can continue
            return "unknown"
    
    def complete_execution(
        self,
        execution_id: str,
        response_message: str,
        success: bool = True,
        error_message: Optional[str] = None,
        token_usage: Optional[Dict[str, int]] = None,
        start_time: Optional[float] = None
    ) -> None:
        """Complete execution tracking with response data."""
        
        if execution_id == "unknown":
            return
            
        try:
            execution = self.db_session.query(PipelineFlavorExecution).filter(
                PipelineFlavorExecution.id == execution_id
            ).first()
            
            if not execution:
                logger.warning(f"Execution {execution_id} not found for completion")
                return
            
            # Update execution record
            execution.response_message = response_message
            execution.status = "success" if success else "error"
            execution.error_message = error_message
            execution.completed_at = datetime.utcnow()
            
            # Calculate execution time if start_time provided
            if start_time:
                execution.execution_time_ms = int((time.time() - start_time) * 1000)
            
            # Update token usage if provided
            if token_usage:
                execution.input_tokens = token_usage.get('input_tokens')
                execution.output_tokens = token_usage.get('output_tokens') 
                execution.total_tokens = token_usage.get('total_tokens')
            
            self.db_session.commit()
            logger.info(f"Completed execution tracking: {execution_id}")
            
        except Exception as e:
            logger.error(f"Failed to complete execution tracking: {e}")
            self.db_session.rollback()
    
    def record_selection(self, selection_request: RecordSelectionRequest) -> str:
        """Record a user selection of an LLM suggestion."""
        
        try:
            # Verify execution exists
            execution = self.db_session.query(PipelineFlavorExecution).filter(
                PipelineFlavorExecution.id == selection_request.execution_id
            ).first()
            
            if not execution:
                raise ValueError(f"Execution {selection_request.execution_id} not found")
            
            # Create selection record
            selection = PipelineFlavorSelection(
                pipeline_execution_id=selection_request.execution_id,
                record_type=selection_request.record_type,
                record_id=selection_request.record_id,
                suggestion_field=selection_request.suggestion_field,
                selected_content=selection_request.selected_content
            )
            
            self.db_session.add(selection)
            self.db_session.commit()
            
            logger.info(f"Recorded selection: {selection.id} for execution: {selection_request.execution_id}")
            return selection.id
            
        except Exception as e:
            logger.error(f"Failed to record selection: {e}")
            self.db_session.rollback()
            raise
    
    def get_execution_analytics(
        self,
        pipeline_type: Optional[PipelineType] = None,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """Get analytics for pipeline executions."""
        
        try:
            from datetime import timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)
            
            query = self.db_session.query(PipelineFlavorExecution).filter(
                PipelineFlavorExecution.started_at >= cutoff_date
            )
            
            if pipeline_type:
                query = query.filter(PipelineFlavorExecution.pipeline_type == pipeline_type.value)
            
            executions = query.all()
            
            if not executions:
                return {"total_executions": 0, "success_rate": 0, "avg_execution_time": 0}
            
            successful = [e for e in executions if e.status == "success"]
            total_time = sum(e.execution_time_ms or 0 for e in executions if e.execution_time_ms)
            total_tokens = sum(e.total_tokens or 0 for e in executions if e.total_tokens)
            
            # Get selection rate
            total_selections = self.db_session.query(PipelineFlavorSelection).join(
                PipelineFlavorExecution
            ).filter(
                PipelineFlavorExecution.started_at >= cutoff_date
            ).count()
            
            return {
                "total_executions": len(executions),
                "successful_executions": len(successful),
                "success_rate": len(successful) / len(executions) if executions else 0,
                "avg_execution_time": total_time / len(executions) if executions else 0,
                "total_tokens_used": total_tokens,
                "total_selections": total_selections,
                "selection_rate": total_selections / len(successful) if successful else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get execution analytics: {e}")
            return {"error": str(e)}
```

### Task 5: Extend LLM Service with Tracking

**File**: `llm/service.py` - Add tracking to existing methods

Example of term definition provided, but all existing suggestion methods should be updated to include this traceability. Update the existing methods to include tracing, don't create a parallel set of methods with tracing.

```python
# Add imports at the top
from .execution_tracker import ExecutionTracker
from database.models import PipelineFlavorExecution

# Add to LLMService class after existing methods

async def suggest_term_definition(
    self, 
    request: DefinitionSuggestionRequest,
    db_session: Session
) -> DefinitionSuggestionResponse:
    """Generate term definition with execution tracking."""
    
    start_time = time.time()
    tracker = ExecutionTracker(db_session)
    execution_id = "unknown"
    
    try:
        # Get flavor
        flavor = await self._get_flavor(PipelineType.SUGGEST_TERM_DEFINITION, request.flavor)
        
        # Create formatted prompt
        user_prompt = self._render_user_prompt(flavor.user_prompt, request)
        
        # Start execution tracking
        execution_id = tracker.start_execution(flavor, request, user_prompt)
        
        # Create messages
        messages = [
            SystemMessage(content=flavor.system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        # Initialize LLM with flavor configuration
        llm = self._create_llm_from_flavor(flavor)
        
        # Make LLM call
        response = await llm.ainvoke(messages)
        response_content = response.content if hasattr(response, 'content') else str(response)
        
        # Parse response
        parsed_response = self._parse_definition_response(response_content)
        
        # Track token usage if available
        token_usage = None
        if hasattr(response, 'response_metadata') and response.response_metadata.get('token_usage'):
            usage = response.response_metadata['token_usage']
            token_usage = {
                'input_tokens': usage.get('prompt_tokens', 0),
                'output_tokens': usage.get('completion_tokens', 0),
                'total_tokens': usage.get('total_tokens', 0)
            }
        
        # Complete execution tracking
        tracker.complete_execution(
            execution_id=execution_id,
            response_message=response_content,
            success=True,
            token_usage=token_usage,
            start_time=start_time
        )
        
        # Return tracked response
        return DefinitionSuggestionResponse(
            execution_id=execution_id,
            **parsed_response.model_dump()
        )
        
    except Exception as e:
        # Complete execution tracking with error
        tracker.complete_execution(
            execution_id=execution_id,
            response_message="",
            success=False,
            error_message=str(e),
            start_time=start_time
        )
        raise

# Similar methods for layer and domain definitions...
async def suggest_layer_definition(
    self, 
    request: LayerDefinitionRequest,
    db_session: Session
) -> LayerDefinitionResponse:
    # Implementation follows same pattern as above
    pass

async def suggest_domain_definition(
    self, 
    request: DomainDefinitionRequest, 
    db_session: Session
) -> DomainDefinitionResponse:
    # Implementation follows same pattern as above
    pass
```

### Task 6: Create Selection Tracking API

**File**: `api/llm_traceability.py`

```python
"""API endpoints for LLM traceability and selection tracking."""

from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional

from api.dependencies.database import get_db
from llm.execution_tracker import ExecutionTracker
from llm.models import RecordSelectionRequest, SelectionResponse, PipelineType
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/llm", tags=["LLM Traceability"])


@router.post("/record-selection", response_model=SelectionResponse)
async def record_selection(
    request: RecordSelectionRequest,
    db: Session = Depends(get_db)
):
    """Record when a user selects an LLM suggestion."""
    
    try:
        tracker = ExecutionTracker(db)
        selection_id = tracker.record_selection(request)
        
        return SelectionResponse(
            success=True,
            selection_id=selection_id,
            message="Selection recorded successfully"
        )
        
    except ValueError as e:
        logger.warning(f"Invalid selection request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error recording selection: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record selection"
        )


@router.get("/execution-analytics")
async def get_execution_analytics(
    pipeline_type: Optional[PipelineType] = None,
    days_back: int = 30,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get analytics for LLM executions."""
    
    try:
        tracker = ExecutionTracker(db)
        analytics = tracker.get_execution_analytics(pipeline_type, days_back)
        
        return {
            "success": True,
            "data": analytics,
            "filters": {
                "pipeline_type": pipeline_type.value if pipeline_type else "all",
                "days_back": days_back
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting execution analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get execution analytics"
        )


@router.get("/execution-history/{execution_id}")
async def get_execution_details(
    execution_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get detailed information about a specific execution."""
    
    try:
        from database.models import PipelineFlavorExecution, PipelineFlavorSelection
        
        execution = db.query(PipelineFlavorExecution).filter(
            PipelineFlavorExecution.id == execution_id
        ).first()
        
        if not execution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution {execution_id} not found"
            )
        
        # Get associated selections
        selections = db.query(PipelineFlavorSelection).filter(
            PipelineFlavorSelection.pipeline_execution_id == execution_id
        ).all()
        
        return {
            "execution": {
                "id": execution.id,
                "pipeline_type": execution.pipeline_type,
                "pipeline_flavor_id": execution.pipeline_flavor_id,
                "status": execution.status,
                "request_context": execution.request_context,
                "user_prompt": execution.user_prompt,
                "response_message": execution.response_message,
                "execution_time_ms": execution.execution_time_ms,
                "token_usage": {
                    "input_tokens": execution.input_tokens,
                    "output_tokens": execution.output_tokens, 
                    "total_tokens": execution.total_tokens
                },
                "started_at": execution.started_at.isoformat() if execution.started_at else None,
                "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                "error_message": execution.error_message
            },
            "selections": [
                {
                    "id": s.id,
                    "record_type": s.record_type,
                    "record_id": s.record_id,
                    "suggestion_field": s.suggestion_field,
                    "selected_content": s.selected_content,
                    "date_created": s.date_created.isoformat() if s.date_created else None
                }
                for s in selections
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting execution details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get execution details"
        )
```

### Task 7: Update Service Factory

**File**: `services/service_factory.py` - Add execution tracker

```python
# Add to existing ServiceFactory class
def get_execution_tracker(self, db_session: Session) -> ExecutionTracker:
    """Get ExecutionTracker instance."""
    # ExecutionTracker doesn't need caching as it's session-dependent
    return ExecutionTracker(db_session)
```

### Task 8: Update Application Integration

**File**: `app.py` - Add traceability router

```python
# Add import
from api import llm_traceability

# Add to router registration section
app.include_router(llm_traceability.router, tags=["llm-traceability"])
```

### Task 10: Create Unit Tests

**File**: `tests/unit_tests/test_execution_tracker.py`

```python
import pytest
from unittest.mock import Mock, patch
from datetime import datetime
import json

from llm.execution_tracker import ExecutionTracker
from llm.models import DefinitionSuggestionRequest, RecordSelectionRequest, PipelineType
from database.models import PipelineFlavor, PipelineFlavorExecution


class TestExecutionTracker:
    
    def test_start_execution(self):
        """Test starting execution tracking."""
        mock_session = Mock()
        tracker = ExecutionTracker(mock_session)
        
        # Create mock flavor
        flavor = Mock()
        flavor.id = "flavor-123"
        flavor.pipeline = "suggest_term_definition"
        flavor.version = 1
        
        # Create mock request
        request = Mock()
        request.model_dump.return_value = {"term": "test"}
        
        execution_id = tracker.start_execution(flavor, request, "test prompt")
        
        # Verify session operations
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        
        # Verify execution was created with correct data
        added_execution = mock_session.add.call_args[0][0]
        assert added_execution.pipeline_flavor_id == "flavor-123"
        assert added_execution.pipeline_type == "suggest_term_definition"
        assert added_execution.user_prompt == "test prompt"
        assert added_execution.status == "pending"
    
    def test_complete_execution_success(self):
        """Test completing execution tracking successfully."""
        mock_session = Mock()
        tracker = ExecutionTracker(mock_session)
        
        # Mock execution query
        mock_execution = Mock()
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_execution
        
        tracker.complete_execution(
            execution_id="exec-123",
            response_message="Test response",
            success=True,
            token_usage={"input_tokens": 10, "output_tokens": 15, "total_tokens": 25}
        )
        
        # Verify execution was updated
        assert mock_execution.response_message == "Test response"
        assert mock_execution.status == "success"
        assert mock_execution.input_tokens == 10
        assert mock_execution.output_tokens == 15
        assert mock_execution.total_tokens == 25
        mock_session.commit.assert_called_once()
    
    def test_record_selection(self):
        """Test recording user selection."""
        mock_session = Mock()
        tracker = ExecutionTracker(mock_session)
        
        # Mock execution exists
        mock_execution = Mock()
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_execution
        
        selection_request = RecordSelectionRequest(
            execution_id="exec-123",
            record_type="structure_node",
            record_id="node-456",
            suggestion_field="definition",
            selected_content="Selected definition text"
        )
        
        selection_id = tracker.record_selection(selection_request)
        
        # Verify selection was created and saved
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        
        # Verify selection data
        added_selection = mock_session.add.call_args[0][0]
        assert added_selection.pipeline_execution_id == "exec-123"
        assert added_selection.record_type == "structure_node"
        assert added_selection.record_id == "node-456"
        assert added_selection.suggestion_field == "definition"
        assert added_selection.selected_content == "Selected definition text"
```

**File**: `tests/unit_tests/test_llm_traceability_api.py`

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch


class TestLLMTraceabilityAPI:
    
    def test_record_selection_success(self, client: TestClient):
        """Test successful selection recording."""
        
        with patch('api.llm_traceability.ExecutionTracker') as mock_tracker_class:
            mock_tracker = Mock()
            mock_tracker_class.return_value = mock_tracker
            mock_tracker.record_selection.return_value = "selection-123"
            
            response = client.post("/api/llm/record-selection", json={
                "execution_id": "exec-123",
                "record_type": "structure_node", 
                "record_id": "node-456",
                "suggestion_field": "definition",
                "selected_content": "Test definition"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["selection_id"] == "selection-123"
    
    def test_execution_analytics(self, client: TestClient):
        """Test execution analytics endpoint."""
        
        with patch('api.llm_traceability.ExecutionTracker') as mock_tracker_class:
            mock_tracker = Mock()
            mock_tracker_class.return_value = mock_tracker
            mock_tracker.get_execution_analytics.return_value = {
                "total_executions": 100,
                "success_rate": 0.95,
                "avg_execution_time": 1500
            }
            
            response = client.get("/api/llm/execution-analytics?days_back=7")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["total_executions"] == 100
            assert data["data"]["success_rate"] == 0.95
```

### Task 11: Create Integration Tests

**File**: `tests/integration_tests/test_llm_traceability_integration.py`

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from database.models import PipelineFlavorExecution, PipelineFlavorSelection


class TestLLMTraceabilityIntegration:
    
    def test_full_execution_flow(self, client: TestClient, db_session: Session):
        """Test complete execution tracking flow."""
        
        # Create a pipeline flavor for testing
        from database.models import PipelineFlavor
        flavor = PipelineFlavor(
            pipeline="suggest_term_definition",
            title="Test Flavor",
            llm_provider="openai",
            llm_model="gpt-3.5-turbo",
            llm_config={"temperature": 0.7},
            system_prompt="You are a helpful assistant.",
            user_prompt="Define: {term}",
            version=1
        )
        db_session.add(flavor)
        db_session.commit()
        
        # Mock LLM response to avoid actual API calls
        with patch('llm.service.LLMService._create_llm_from_flavor') as mock_create_llm:
            mock_llm = Mock()
            mock_response = Mock()
            mock_response.content = "A test term is a term used for testing."
            mock_response.response_metadata = {
                "token_usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 15,
                    "total_tokens": 25
                }
            }
            mock_llm.ainvoke.return_value = mock_response
            mock_create_llm.return_value = mock_llm
            
            # Make request to tracked endpoint
            response = client.post("/api/llm/suggest_term_definition", json={
                "term": "test term",
                "domain_title": "Testing"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert "execution_id" in data
            execution_id = data["execution_id"]
            
            # Verify execution was recorded
            execution = db_session.query(PipelineFlavorExecution).filter(
                PipelineFlavorExecution.id == execution_id
            ).first()
            
            assert execution is not None
            assert execution.status == "success"
            assert execution.input_tokens == 10
            assert execution.output_tokens == 15
            assert execution.total_tokens == 25
            
            # Test selection recording
            selection_response = client.post("/api/llm/record-selection", json={
                "execution_id": execution_id,
                "record_type": "structure_node",
                "record_id": "test-node-id",
                "suggestion_field": "definition", 
                "selected_content": "A test term is a term used for testing."
            })
            
            assert selection_response.status_code == 200
            selection_data = selection_response.json()
            assert selection_data["success"] is True
            
            # Verify selection was recorded
            selection = db_session.query(PipelineFlavorSelection).filter(
                PipelineFlavorSelection.pipeline_execution_id == execution_id
            ).first()
            
            assert selection is not None
            assert selection.record_type == "structure_node"
            assert selection.suggestion_field == "definition"
            
            # Test analytics endpoint
            analytics_response = client.get("/api/llm/execution-analytics")
            assert analytics_response.status_code == 200
            analytics_data = analytics_response.json()
            assert analytics_data["data"]["total_executions"] >= 1
```

## Validation Gates

### Database Migration
```bash
# Apply migration
python -m database.migrations.migration_manager migrate

# Verify tables created
sqlite3 database.db ".schema pipeline_flavor_executions"
sqlite3 database.db ".schema pipeline_flavor_selections"
```

### Code Quality
```bash
# Format and lint
black llm/execution_tracker.py api/llm_traceability.py
ruff check llm/ api/ --fix

# Type checking
mypy llm/execution_tracker.py api/llm_traceability.py --ignore-missing-imports
```

### Testing
```bash
# Unit tests
pytest tests/unit_tests/test_execution_tracker.py -v
pytest tests/unit_tests/test_llm_traceability_api.py -v

# Integration tests
pytest tests/integration_tests/test_llm_traceability_integration.py -v

# Full test suite
pytest tests/ -k "traceability" -v
```

## Implementation Notes

**Performance Considerations**: 
- Execution tracking adds ~10-20ms overhead per LLM call
- Database indexes optimize queries on frequently accessed fields
- Async operations prevent blocking during tracking operations
- Optional token usage tracking for cost analysis

**Error Handling**: 
- Graceful degradation when tracking fails (execution continues)
- Null execution IDs for system resilience
- Comprehensive error logging without exposing sensitive data
- Transaction rollback on tracking failures

**Security & Privacy**:
- No API keys or credentials logged in execution records

**Extensibility**:
- Pluggable tracking system via service factory pattern
- Extensible analytics queries via ExecutionTracker
- Support for additional pipeline types through enum extension

## Success Metrics

- [ ] Pipeline flavor executions captured with complete context (request, response, timing)
- [ ] User selections successfully linked to execution records
- [ ] Execution IDs included in all LLM API responses
- [ ] Analytics endpoint provides actionable insights (success rates, performance metrics)
- [ ] Database schema updates successfully with proper indexing
- [ ] Selection tracking API records user choices accurately
- [ ] Token usage tracking enables cost analysis
- [ ] System maintains <5% performance overhead
- [ ] Error scenarios handled gracefully without system failure
- [ ] All tests pass with >90% code coverage
- [ ] API endpoints return proper HTTP status codes and execution IDs
