name: "Fix Traceability API - Complete Feature Implementation"
description: |

## Purpose
Enhance the LLM traceability API to provide comprehensive execution tracking and analytics capabilities, enabling users to trace flavor-specific execution history and detailed analytics.

## Core Principles
1. **Focus is King**: Include ONLY necessary documentation, examples, and caveats
2. **Validation Loops**: Provide executable tests/lints the AI can run and fix
3. **Information Dense**: Use keywords and patterns from the codebase
4. **Progressive Success**: Start simple, validate, then enhance
5. **Global rules**: Be sure to follow all rules in CLAUDE.md

---

## Goal
Fix and enhance the traceability API to provide complete execution history tracking per flavor, detailed execution information, and flavor-specific analytics. The end state should enable users to:
- View execution history filtered by flavor ID
- Get detailed information about specific executions
- Access analytics scoped to individual flavors
- Ensure current flavor versions are captured in execution records

## Why
- **Business value**: Enables data-driven optimization of LLM pipeline flavors by providing granular tracking and analytics
- **Integration with existing features**: Builds upon existing execution tracking infrastructure in `ExecutionTracker` class
- **Problems this solves**: Currently users cannot see execution history for a specific flavor or get flavor-scoped analytics, limiting their ability to optimize and debug LLM performance

## What
Enhance the LLM traceability API with three key improvements:

1. **Execution History by Flavor**: New endpoint to retrieve execution history for a specific flavor
2. **Execution Details**: Dedicated endpoint for detailed execution information (renaming existing endpoint)
3. **Flavor Analytics**: New endpoint for flavor-specific execution analytics

### Success Criteria
- [ ] `/execution-history` endpoint accepts `flavor_id` parameter and returns list of executions for that flavor
- [ ] `/execution-details/{execution_id}` endpoint returns detailed execution information (renamed from current `/execution-history/{execution_id}`)
- [ ] `/flavor-analytics/{flavor_id}` endpoint returns analytics scoped to a specific flavor
- [ ] Current flavor version capture is verified to work correctly (existing `pipeline_flavor_version` field)
- [ ] All existing functionality continues to work unchanged
- [ ] Comprehensive test coverage for new endpoints

## All Needed Context

### Documentation & References (list all context needed to implement the feature)
```yaml
# MUST READ - Include these in your context window
- file: /Users/austinsand/workspace/context-studio/local-server/api/llm_traceability.py
  why: Current traceability API implementation - shows patterns for error handling, response structure, and ExecutionTracker usage
  
- file: /Users/austinsand/workspace/context-studio/local-server/llm/execution_tracker.py
  why: ExecutionTracker class implementation - contains database queries and business logic that needs to be extended
  
- file: /Users/austinsand/workspace/context-studio/local-server/llm/models.py
  why: Pydantic models for requests/responses - shows pattern for creating new response models
  
- file: /Users/austinsand/workspace/context-studio/local-server/api/pipeline_flavors.py
  why: Similar API pattern with proper error handling, logging, and FastAPI conventions used in this codebase

- file: /Users/austinsand/workspace/context-studio/local-server/tests/unit_tests/test_llm_traceability_api.py
  why: Testing patterns for traceability API - shows how to mock ExecutionTracker and test API endpoints
  
- file: /Users/austinsand/workspace/context-studio/local-server/tests/integration_tests/test_llm_traceability_integration.py
  why: Integration testing patterns with real database - shows setup/teardown and database interaction testing

- file: /Users/austinsand/workspace/context-studio/local-server/pipeline/manager.py
  why: Database schema for pipeline_flavor_executions and pipeline_flavor_selections tables - critical for understanding data structure
```

### Current Codebase tree (focused on relevant directories)
```bash
./
├── api/
│   ├── llm_traceability.py          # Main API file to modify
│   └── pipeline_flavors.py          # API pattern reference
├── llm/
│   ├── execution_tracker.py         # Business logic to extend
│   └── models.py                     # Pydantic models to add
├── tests/
│   ├── unit_tests/
│   │   └── test_llm_traceability_api.py     # Unit tests to extend
│   └── integration_tests/
│       └── test_llm_traceability_integration.py  # Integration tests to extend
└── pipeline/
    └── manager.py                    # Database schema reference
```

### Desired Codebase tree with files to be modified and responsibility of file
```bash
# Files to be MODIFIED:
./api/llm_traceability.py            # Add new endpoints, rename existing endpoint
./llm/execution_tracker.py           # Add new methods for flavor-filtered queries
./llm/models.py                       # Add new response models
./tests/unit_tests/test_llm_traceability_api.py     # Add tests for new endpoints
./tests/integration_tests/test_llm_traceability_integration.py  # Add integration tests
```

### Known Gotchas of our codebase & Library Quirks
```python
# CRITICAL: Always cast UUID values to strings when comparing, as SQLite stores UUIDs as text
# CRITICAL: FastAPI requires async functions for endpoints
# CRITICAL: Use ExecutionTracker() for business logic - don't access database directly in API layer
# CRITICAL: Follow existing error handling pattern: ValueError -> 400, Exception -> 500
# CRITICAL: All API endpoints must use utils.logger for logging
# CRITICAL: Use Pydantic response models for all API endpoints
# CRITICAL: Always use get_pipeline_session() via ExecutionTracker - don't create direct DB connections
# CRITICAL: Test files must add path setup: sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

## Implementation Blueprint

### Data models and structure

The database schema already exists and is correct. We need to add new Pydantic response models:

```python
# Add to llm/models.py:
class ExecutionHistoryResponse(BaseModel):
    """Response model for execution history by flavor"""
    executions: List[Dict[str, Any]] = Field(..., description="List of executions for the flavor")
    total_count: int = Field(..., description="Total number of executions")
    flavor_id: str = Field(..., description="Flavor ID that was filtered")

class FlavorAnalyticsResponse(BaseModel):
    """Response model for flavor-specific analytics"""
    flavor_id: str = Field(..., description="Flavor ID")
    analytics: Dict[str, Any] = Field(..., description="Analytics data for the flavor")
    time_range_days: int = Field(..., description="Number of days of data included")
```

### list of tasks to be completed to fullfill the PRP in the order they should be completed

```yaml
Task 1:
MODIFY llm/models.py:
  - FIND pattern: "class SelectionResponse(BaseModel):" (at end of file)
  - ADD new response models after it
  - KEEP existing patterns for Field descriptions and types

Task 2:
MODIFY llm/execution_tracker.py:
  - FIND pattern: "def get_execution_analytics(" method (line ~185)
  - ADD new method get_flavor_execution_history(flavor_id: str, limit: int = 100) after analytics method
  - ADD new method get_flavor_analytics(flavor_id: str, days_back: int = 30) after analytics method
  - KEEP same database session handling pattern as existing methods

Task 3:  
MODIFY api/llm_traceability.py:
  - FIND pattern: "@router.get("/execution-history/{execution_id}")" endpoint (line ~70)
  - RENAME endpoint path to "/execution-details/{execution_id}"
  - KEEP all existing functionality unchanged
  - ADD new get_execution_history endpoint with flavor_id query parameter
  - ADD new get_flavor_analytics endpoint with flavor_id path parameter
  - PRESERVE existing error handling patterns

Task 4:
MODIFY tests/unit_tests/test_llm_traceability_api.py:
  - FIND pattern: "class TestLLMTraceabilityAPI:" 
  - ADD test methods for new endpoints
  - MIRROR existing test patterns with Mock and patch
  - KEEP test setup pattern identical

Task 5:
MODIFY tests/integration_tests/test_llm_traceability_integration.py:
  - FIND pattern: "class TestLLMTraceabilityIntegration:"
  - ADD integration test methods for new endpoints  
  - MIRROR existing database setup pattern
  - KEEP temporary database pattern for isolation

Task 6:
RUN validation tests to ensure everything works correctly
```

### Per task pseudocode as needed added to each task

```python
# Task 2: ExecutionTracker new methods
def get_flavor_execution_history(self, flavor_id: str, limit: int = 100) -> Dict[str, Any]:
    """Get execution history for a specific flavor."""
    # PATTERN: Same session handling as get_execution_analytics
    session = get_pipeline_session()
    try:
        # QUERY: SELECT * FROM pipeline_flavor_executions WHERE pipeline_flavor_id = ? ORDER BY started_at DESC LIMIT ?
        # RETURN: {"executions": [...], "total_count": count, "flavor_id": flavor_id}
        pass
    finally:
        session.close()

def get_flavor_analytics(self, flavor_id: str, days_back: int = 30) -> Dict[str, Any]:
    """Get analytics for a specific flavor.""" 
    # PATTERN: Reuse analytics query logic but add flavor_id filter
    # QUERY: Same as get_execution_analytics but add "AND pipeline_flavor_id = ?" to WHERE clause
    # RETURN: Same structure as get_execution_analytics
    pass

# Task 3: API endpoint patterns  
@router.get("/execution-history")
async def get_execution_history(
    flavor_id: str = Query(..., description="Flavor ID to get execution history for"),
    limit: int = Query(100, description="Maximum number of executions to return")
) -> ExecutionHistoryResponse:
    """Get execution history for a specific flavor."""
    # PATTERN: Same as existing endpoints - use ExecutionTracker(), handle exceptions
    # ERROR: ValueError -> 400, Exception -> 500
    # LOG: Use logger.info for success, logger.error for failures
    pass

@router.get("/flavor-analytics/{flavor_id}")  
async def get_flavor_analytics(flavor_id: str, days_back: int = Query(30)) -> FlavorAnalyticsResponse:
    """Get analytics for a specific flavor."""
    # PATTERN: Same as get_execution_analytics but call new tracker method
    pass
```

### Integration Points
```yaml
DATABASE:
  - no_changes: "Existing pipeline_flavor_executions table has all needed columns"
  - indexes: "Existing idx_executions_flavor_id index supports new queries efficiently"
  
API_ROUTES:
  - modify: "api/llm_traceability.py router endpoints"
  - pattern: "Follow existing endpoint patterns with proper error handling"
  
MODELS:
  - add: "New response models in llm/models.py"
  - pattern: "Follow existing BaseModel patterns with Field descriptions"
```

## Validation Loop

### Level 1: Syntax & Style
```bash
# Run these FIRST - fix any errors before proceeding
source .venv/bin/activate  # Activate virtual environment first
ruff check api/llm_traceability.py llm/execution_tracker.py llm/models.py --fix
mypy api/llm_traceability.py llm/execution_tracker.py llm/models.py

# Expected: No errors. If errors, READ the error and fix.
```

### Level 2: Unit Tests each new feature/file/function use existing test patterns
```python
# Key test cases to ADD to test_llm_traceability_api.py:
def test_get_execution_history_success():
    """Test successful execution history retrieval."""
    # Mock tracker.get_flavor_execution_history to return test data
    # Verify correct flavor_id passed and response structure
    pass

def test_get_execution_history_invalid_flavor():
    """Test execution history with invalid flavor ID."""
    # Mock tracker to return empty results
    # Verify proper response structure for no data
    pass

def test_get_flavor_analytics_success():
    """Test successful flavor analytics retrieval."""
    # Mock tracker.get_flavor_analytics to return analytics data
    # Verify correct parameters passed and response structure
    pass

def test_execution_details_endpoint_renamed():
    """Test that execution-details endpoint still works after rename."""
    # Verify renamed endpoint returns execution details
    # Ensure backward compatibility
    pass
```

```bash
# Run and iterate until passing:
source .venv/bin/activate
pytest tests/unit_tests/test_llm_traceability_api.py -v
# If failing: Read error, understand root cause, fix code, re-run
```

### Level 3: Integration Test  
```bash
# Test the endpoints with real database
source .venv/bin/activate
pytest tests/integration_tests/test_llm_traceability_integration.py -v

# Manual endpoint testing:
python -m uvicorn app:app --reload &
sleep 2

# Test new execution history endpoint:
curl -X GET "http://localhost:8000/api/llm/execution-history?flavor_id=test-flavor-123&limit=10"
# Expected: {"executions": [...], "total_count": N, "flavor_id": "test-flavor-123"}

# Test new flavor analytics endpoint:
curl -X GET "http://localhost:8000/api/llm/flavor-analytics/test-flavor-123?days_back=7"
# Expected: {"flavor_id": "test-flavor-123", "analytics": {...}, "time_range_days": 7}

# Test renamed execution details endpoint:
curl -X GET "http://localhost:8000/api/llm/execution-details/some-execution-id"
# Expected: {"success": true, "data": {...}}

kill %1  # Stop server
```

## Final validation Checklist
- [ ] All tests pass: `pytest tests/ -v`
- [ ] No linting errors: `ruff check .`
- [ ] No type errors: `mypy api/llm_traceability.py llm/execution_tracker.py llm/models.py`
- [ ] Manual test successful: All curl commands return expected JSON
- [ ] Error cases handled gracefully (invalid flavor_id, missing execution_id)
- [ ] Logs are informative but not verbose
- [ ] Existing functionality unchanged (execution-details endpoint still works)

---

## Anti-Patterns to Avoid
- ❌ Don't create new database tables - use existing schema
- ❌ Don't skip validation because "it should work"  
- ❌ Don't ignore failing tests - fix them
- ❌ Don't use sync functions in async context
- ❌ Don't hardcode values that should be parameters
- ❌ Don't change existing endpoint behavior - only add new functionality
- ❌ Don't access database directly in API layer - always use ExecutionTracker

---

## Confidence Score: 9/10

This PRP has very high confidence for one-pass implementation because:
- ✅ Existing patterns are well-established and clear
- ✅ Database schema already supports all required queries  
- ✅ ExecutionTracker class provides clean abstraction
- ✅ Comprehensive test patterns exist to follow
- ✅ Clear validation steps with executable commands
- ✅ All necessary context files identified and referenced
- ❌ Only risk is potential edge cases in database query performance with large datasets

The implementation should be straightforward following existing patterns in the codebase.