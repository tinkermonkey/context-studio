# Pipeline Test Fixtures

This directory contains data-only test fixtures for pipeline functional tests. Each fixture is a JSON file pair: input + expected output. Fixtures enable reproducible, deterministic testing of pipeline implementations across all five pipeline types.

## Directory Structure

```
fixtures/pipelines/
├── no_op/                      # No-op (framework smoke test)
├── individual_extraction/      # Individual extraction pipeline
├── schema_extraction/          # Schema extraction pipeline
├── schema_node_grounding/      # Schema node grounding pipeline
├── schema_node_definition_refinement/  # Definition refinement
├── schema_node_connection_refinement/  # Connection refinement
└── README.md                   # This file
```

## Fixture Format

Each pipeline type directory contains fixtures following this pattern:

```
{type}/{scenario}_input.json
{type}/{scenario}_output.json
```

### Input Format

Input fixtures are pure data (JSON), never Python. They represent a complete request payload to the pipeline.

**Example: no_op/basic_input.json**
```json
{
  "text": "Sample input text",
  "ontology_id": "onto-12345",
  "pipeline_type": "individual_extraction",
  "implementation_id": "default",
  "configuration_ref": "extraction-default"
}
```

### Output Format

Output fixtures describe the expected structure and key values the pipeline should produce. They include:
- `status`: "completed" or "failed"
- `result`: The returned data (structure varies by pipeline type)
- `metadata`: Token counts, duration, finish_reason (if applicable)

**Example: no_op/basic_output.json**
```json
{
  "status": "completed",
  "result": {
    "status": "completed",
    "message": "No-op pipeline completed successfully",
    "steps": ["initialize", "process", "finalize"]
  },
  "metadata": {
    "tokens_in": 10,
    "tokens_out": 5,
    "duration_ms": 100,
    "finish_reason": "stop"
  }
}
```

## Fixture Usage in Tests

Tests load fixtures using utility functions:

```python
from tests.fixtures.pipeline_fixtures import load_fixture, load_expected_output

def test_pipeline_with_fixture():
    input_data = load_fixture("individual_extraction", "basic")
    expected = load_expected_output("individual_extraction", "basic")
    
    result = pipeline.execute(input_data)
    assert result["status"] == expected["status"]
    # Additional assertions...
```

## Mock LLM Strategy

All pipeline tests use `FakeLLMProvider` from `tests.fakes.fake_llm_provider` with canned responses. The LLM provider is registered with a mock cache that returns deterministic responses based on prompt/model pairs. This ensures:

- Tests are deterministic across runs
- No network calls to real LLM services
- Reproducible behavior for all pipeline types

See `tests/integration/pipelines/test_framework.py` for implementation details.

## Network Blocking

All pipeline tests run under a pytest fixture that blocks any outgoing network calls. Tests that require external services (e.g., reference source lookups) must explicitly opt-in via a marker: `@pytest.mark.external_network` or similar.

Default behavior: **All network calls fail with a clear error message.**

## Naming Conventions

- Use `{scenario}_input.json` and `{scenario}_output.json` pairs
- Scenario names should be descriptive: `basic`, `edge_case`, `error_condition`, etc.
- Keep scenario names lowercase with underscores
- One scenario per test; avoid combining multiple test cases in one fixture pair

## Maintenance

- Fixtures are data-only; never include Python code or references
- When pipeline input/output contracts change, update fixtures and document in commit
- Fixtures serve as documentation of expected behavior; keep them aligned with domain entities
- Performance benchmarks use separate harness (Wave A pattern); fixtures focus on correctness
