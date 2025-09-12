# LLM Pipeline Unified Execution API

## Goal
Create a unified "execute a pipeline flavor with this context" API that replaces the current bespoke single-purpose pipeline definitions in the LLM service, while maintaining backward compatibility and full execution tracking integration.

## Why
- **Code Duplication Elimination**: Current LLM service has 6+ nearly identical methods that follow the same pattern (get flavor → create LLM → render prompts → execute → parse → track)
- **Extensibility**: Adding new pipeline types currently requires duplicating ~100 lines of boilerplate code
- **Maintainability**: Bug fixes and improvements must be applied to multiple similar methods
- **Flexibility**: Custom pipeline flavors are limited by hardcoded request/response models

## What
A generic pipeline execution API that accepts any pipeline flavor ID and context data, leveraging the existing robust pipeline flavor system and execution tracking infrastructure.

### Success Criteria
- [ ] Generic `execute_pipeline_flavor(flavor_id, context_data)` method implemented
- [ ] Existing typed methods refactored to use generic method internally (zero behavior change)
- [ ] Full execution tracking preserved
- [ ] All existing tests pass
- [ ] New API endpoint `/llm/execute_pipeline` available
- [ ] Streaming variant available
- [ ] Documentation updated

## All Needed Context

### Documentation & References
```yaml
# MUST READ - Include these in your context window
- file: local-server/llm/service.py
  why: Current bespoke methods follow identical patterns - need to extract common logic
  
- file: local-server/llm/models.py
  why: PipelineFlavor model and request/response patterns to follow
  
- file: local-server/llm/execution_tracker.py
  why: Execution tracking integration patterns - must preserve all tracking
  
- file: local-server/api/llm.py
  why: API endpoint patterns and error handling to mirror

- file: local-server/llm/flavor_service.py
  why: Flavor lookup patterns - get_flavor_by_id vs get_default_flavor logic

- file: local-server/tests/unit_tests/test_llm_basic.py
  why: Test patterns for LLM service methods
  
- file: local-server/tests/integration_tests/test_llm_traceability_integration.py  
  why: Integration test patterns including execution tracking validation
```

### Current Codebase Analysis
The LLM service contains these bespoke methods that follow identical patterns:
```python
# All follow this pattern:
async def suggest_X_definition(request) -> Response:
    flavor = await self._get_flavor(PipelineType.X, request.flavor)
    llm = self._create_llm_from_flavor(flavor) 
    user_prompt = self._render_user_prompt(flavor.user_prompt, request)
    execution_id = self.execution_tracker.start_execution(...)
    response = await llm.ainvoke([SystemMessage(...), HumanMessage(...)])
    parsed = self._parse_X_response(response.content)
    self.execution_tracker.complete_execution(...)
    return parsed
```

### Desired Codebase Changes
```bash
local-server/llm/
├── models.py (ADD new generic models)
├── service.py (ADD generic method, REFACTOR existing methods)
└── api/llm.py (ADD new endpoint)
```

### Known Gotchas & Library Quirks
```python
# CRITICAL: Template rendering uses different variable sets per pipeline type
# Current: Each request model has different fields for template substitution
# Solution: Generic context dict with validation against flavor requirements

# CRITICAL: Response parsing varies by pipeline type
# Current: _parse_definition_response vs _parse_layer_definition_response
# Solution: Configurable response format or inferred from pipeline type

# CRITICAL: Execution tracking expects specific request types for serialization
# Current: request.model_dump() for structured data
# Solution: Accept generic Dict[str, Any] and serialize as JSON

# CRITICAL: Flavor lookup supports both ID and title resolution
# Current: _get_flavor() handles ID, title, and default resolution
# Solution: Reuse existing _get_flavor() method pattern
```

## Implementation Blueprint

### Data Models and Structure

```python
# ADD to local-server/llm/models.py
class GenericPipelineExecutionRequest(BaseModel):
    """Generic request for pipeline flavor execution"""
    flavor_id: str = Field(..., description="Pipeline flavor ID, title, or 'default'")
    context_data: Dict[str, Any] = Field(..., description="Context variables for template rendering")
    pipeline_type: Optional[PipelineType] = Field(None, description="Pipeline type (auto-detected if not provided)")

class GenericPipelineExecutionResponse(BaseModel):
    """Generic response from pipeline execution"""
    execution_id: str = Field(..., description="Execution tracking ID")
    response_content: str = Field(..., description="Raw LLM response")
    parsed_response: Optional[Dict[str, Any]] = Field(None, description="Parsed response if standard format")
    pipeline_type: PipelineType = Field(..., description="Pipeline type that was executed")
    flavor_id: str = Field(..., description="Flavor ID that was used")

class StreamingGenericLLMResponse(BaseModel):
    """Streaming response for generic pipeline execution"""
    token: Optional[str] = Field(None, description="Response token")
    execution_id: Optional[str] = Field(None, description="Execution ID")
    flavor_id: str = Field(..., description="Flavor ID")
    pipeline_type: Optional[PipelineType] = Field(None, description="Pipeline type")
    done: bool = Field(default=False, description="Whether streaming is complete")
    error: Optional[str] = Field(None, description="Error message if failed")
```

### List of Tasks (Implementation Order)

```yaml
Task 1: Add Generic Execution Method to LLMService
MODIFY local-server/llm/service.py:
  - ADD async def execute_pipeline_flavor(flavor_id, context_data, pipeline_type=None)
  - REUSE existing _get_flavor, _create_llm_from_flavor, execution tracking patterns
  - HANDLE template rendering with generic context data
  - PRESERVE all error handling and timeout logic

Task 2: Add Generic Streaming Method 
MODIFY local-server/llm/service.py:
  - ADD async def execute_pipeline_flavor_streaming(flavor_id, context_data, pipeline_type=None)
  - MIRROR streaming patterns from existing methods
  - PRESERVE execution tracking for streaming

Task 3: Refactor Existing Methods to Use Generic Implementation
MODIFY local-server/llm/service.py:
  - REFACTOR suggest_term_definition to call execute_pipeline_flavor internally
  - REFACTOR suggest_layer_definition to call execute_pipeline_flavor internally  
  - REFACTOR suggest_domain_definition to call execute_pipeline_flavor internally
  - PRESERVE existing method signatures and return types (zero breaking changes)
  - KEEP existing error handling behavior

Task 4: Add API Endpoints
MODIFY local-server/api/llm.py:
  - ADD POST /llm/execute_pipeline endpoint
  - ADD POST /llm/execute_pipeline/stream endpoint
  - MIRROR error handling patterns from existing endpoints
  - PRESERVE authentication and validation patterns

Task 5: Add Comprehensive Tests
CREATE local-server/tests/unit_tests/test_llm_generic_execution.py:
  - TEST generic execution method with all pipeline types
  - TEST context data validation and template rendering
  - TEST error cases (invalid flavor, malformed context)
  - TEST execution tracking integration

CREATE local-server/tests/integration_tests/test_generic_pipeline_api.py:
  - TEST new API endpoints
  - TEST backward compatibility of existing endpoints
  - TEST execution tracking end-to-end

Task 6: Update API Documentation
MODIFY local-server/documentation/openapi.json:
  - RUN local-server/utils/update_api_specs.py to refresh OpenAPI spec
  - VERIFY new endpoints documented correctly
```

### Per-Task Pseudocode

```python
# Task 1: Generic Execution Method
async def execute_pipeline_flavor(
    self,
    flavor_id: str,
    context_data: Dict[str, Any],
    pipeline_type: Optional[PipelineType] = None
) -> GenericPipelineExecutionResponse:
    
    # PATTERN: Reuse existing flavor resolution logic
    if pipeline_type:
        flavor = await self._get_flavor(pipeline_type, flavor_id)
    else:
        # Auto-detect pipeline type from flavor
        flavor = await self.flavor_service.get_flavor_by_id(flavor_id)
    
    # PATTERN: Reuse LLM creation logic
    llm = self._create_llm_from_flavor(flavor)
    
    # CRITICAL: Generic template rendering
    user_prompt = self._render_generic_user_prompt(flavor.user_prompt, context_data)
    
    # PATTERN: Preserve execution tracking
    execution_id = self.execution_tracker.start_execution(
        pipeline_flavor_id=flavor.id,
        pipeline_type=flavor.pipeline.value,
        pipeline_flavor_version=flavor.version,
        request=context_data,  # Generic dict instead of typed request
        user_prompt=user_prompt
    )
    
    # PATTERN: Reuse timeout and LLM execution logic
    # ... (identical to existing methods)
    
    return GenericPipelineExecutionResponse(
        execution_id=execution_id,
        response_content=response.content,
        parsed_response=None,  # Optional parsing
        pipeline_type=flavor.pipeline,
        flavor_id=flavor.id
    )

# Task 3: Refactor Existing Method
async def suggest_term_definition(self, request: DefinitionSuggestionRequest) -> DefinitionSuggestionResponse:
    """REFACTORED: Now uses generic execution internally"""
    
    # Convert typed request to generic context
    context_data = request.model_dump()
    
    # Use generic method
    generic_response = await self.execute_pipeline_flavor(
        flavor_id=request.flavor or "default",
        context_data=context_data,
        pipeline_type=PipelineType.SUGGEST_TERM_DEFINITION
    )
    
    # Parse using existing logic
    parsed_response = self._parse_definition_response(generic_response.response_content)
    parsed_response.execution_id = generic_response.execution_id
    
    return parsed_response
```

### Integration Points
```yaml
DATABASE:
  - No changes required - reuses existing pipeline_flavor_executions tables
  
CONFIG:
  - No new configuration required
  
ROUTES:
  - ADD to: local-server/api/llm.py
  - pattern: "@router.post('/llm/execute_pipeline')"
```

## Validation Loop

### Level 1: Syntax & Style
```bash
# Run these FIRST - fix any errors before proceeding
ruff check local-server/llm/service.py --fix
ruff check local-server/api/llm.py --fix
mypy local-server/llm/service.py
mypy local-server/api/llm.py

# Expected: No errors. If errors, READ the error and fix.
```

### Level 2: Unit Tests
```python
# CREATE test_llm_generic_execution.py with these test cases:
def test_generic_execution_with_term_definition():
    """Generic method produces same result as specific method"""
    # Test that generic API produces identical results to existing API

def test_generic_execution_invalid_flavor():
    """Handles invalid flavor IDs gracefully"""
    with pytest.raises(FlavorNotFoundError):
        await service.execute_pipeline_flavor("invalid_flavor", {})

def test_context_data_template_rendering():
    """Context data is properly substituted in templates"""
    # Test template variable substitution with generic context

def test_execution_tracking_integration():
    """Execution tracking works with generic context data"""
    # Verify all tracking metadata is preserved

def test_backward_compatibility():
    """Existing methods produce identical results"""
    # Side-by-side comparison of old vs refactored methods
```

```bash
# Run and iterate until passing:
uv run pytest local-server/tests/unit_tests/test_llm_generic_execution.py -v
# Ensure existing tests still pass:
uv run pytest local-server/tests/unit_tests/test_llm_basic.py -v
```

### Level 3: Integration Test  
```bash
# Test existing endpoints still work (backward compatibility)
curl -X POST http://localhost:8000/llm/suggest_term_definition \
  -H "Content-Type: application/json" \
  -d '{"term": "test", "domain_title": "test domain"}'

# Test new generic endpoint
curl -X POST http://localhost:8000/llm/execute_pipeline \
  -H "Content-Type: application/json" \
  -d '{"flavor_id": "default", "context_data": {"term": "test", "domain_title": "test domain"}, "pipeline_type": "suggest_term_definition"}'

# Expected: Both return successful responses with execution tracking
```

## Final Validation Checklist
- [ ] All tests pass: `uv run pytest local-server/tests/ -v`
- [ ] No linting errors: `uv run ruff check local-server/`
- [ ] No type errors: `uv run mypy local-server/`
- [ ] Manual test of backward compatibility successful
- [ ] Manual test of new generic API successful
- [ ] Execution tracking verified in database
- [ ] OpenAPI spec updated with new endpoints

---

## Benefits Achieved
✅ **Code Reuse**: ~300 lines of duplicate code eliminated
✅ **Extensibility**: New pipeline types require only flavor definition, no code changes
✅ **Maintainability**: Single implementation for all pipeline execution logic  
✅ **Flexibility**: Custom contexts supported without new request models
✅ **Zero Breaking Changes**: All existing callers continue to work

## Confidence Level: 8/10
This PRP provides comprehensive context about existing patterns, clear implementation tasks, and thorough validation. The hybrid approach (generic implementation + backward compatible wrappers) minimizes risk while maximizing benefits.