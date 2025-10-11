# Test Runner for Agents

This directory contains a comprehensive test runner script designed to help automated agents analyze test failures by mapping them to source files.

## Files

- `test_runner.py` - Main test runner script with comprehensive functionality
- `test_failure_example.py` - Simple example showing basic usage
- `README_test_runner.md` - This documentation file

## Basic Usage

### Simple Function (as requested)

```python
from test_runner import TestFailureMapper

def run_tests_with_file_mapping():
    """Run tests and map failures to source files"""
    mapper = TestFailureMapper()
    
    result = subprocess.run(
        ['pytest', '--json-report', '--json-report-file=report.json'],
        capture_output=True
    )
    
    with open('report.json') as f:
        report = json.load(f)
    
    # Create deterministic mapping
    file_failures = {}
    for test in report['tests']:
        if test['outcome'] == 'failed':
            source_file = mapper.extract_source_file(test)
            if source_file not in file_failures:
                file_failures[source_file] = []
            file_failures[source_file].append({
                'test_name': test['nodeid'],
                'error': test['call']['longrepr'],
                'line': test['call']['lineno']
            })
    
    return file_failures
```

### Command Line Usage

```bash
# Run all tests and show failures
python test_runner.py

# Run specific test file
python test_runner.py tests/integration_tests/test_llm_traceability_integration.py

# Include passed tests in output
python test_runner.py --include-passed

# Output to JSON file
python test_runner.py --format json --output results.json

# Run with specific pytest arguments
python test_runner.py tests/unit_tests/ -k "not slow"
```

### Programmatic Usage

```python
from test_runner import TestFailureMapper

# Initialize mapper
mapper = TestFailureMapper()

# Run tests and get file mapping
results = mapper.run_tests_with_file_mapping(
    test_args=['tests/unit_tests/'],
    include_passed=False
)

# Process results
for source_file, test_results in results.items():
    if source_file == '_summary':
        continue
    
    print(f"Source: {source_file}")
    for test in test_results:
        if test['outcome'] == 'failed':
            print(f"  Failed: {test['test_name']}")
            print(f"  Error: {test['error']}")
```

## Features

### Source File Mapping

The script intelligently maps test files to their corresponding source files:

- `test_module.py` → `module.py`
- `test_module_integration.py` → `api/module.py`
- Analyzes traceback to find actual source files
- Searches common directories (`api/`, `llm/`, `database/`, etc.)

### Error Analysis

Extracts comprehensive error information:

- Test name and location
- Error message and traceback
- Line numbers
- Test duration
- Test keywords/markers
- Setup/teardown failures

### Output Formats

- **Text**: Human-readable summary with failures by source file
- **JSON**: Machine-readable format for automation

### Test Categories

Handles different test outcomes:

- Failed tests (assertion errors)
- Error tests (setup/runtime errors)
- Passed tests (optional)
- Skipped tests

## Example Output

### Text Format

```
============================================================
TEST RESULTS SUMMARY
============================================================
Total: 10
Passed: 1
Failed: 9
Errors: 0
Skipped: 0
Duration: 0.57s
Overall: FAILED

Source File: llm/execution_tracker.py
------------------------------------------------------------
  ❌ test_record_selection_flow
     Line: 156
     Error: KeyError: 'flavor_id'

  ❌ test_analytics_calculation
     Line: 180
     Error: AssertionError: Expected 3, got 0
```

### JSON Format

```json
{
  "llm/execution_tracker.py": [
    {
      "test_name": "tests/integration_tests/test_llm_traceability_integration.py::TestLLMTraceabilityIntegration::test_record_selection_flow",
      "outcome": "failed",
      "error": "KeyError: 'flavor_id'",
      "line": 156,
      "duration": 0.05,
      "keywords": ["integration"]
    }
  ],
  "_summary": {
    "total": 10,
    "passed": 1,
    "failed": 9,
    "error": 0,
    "skipped": 0,
    "duration": 0.57,
    "outcome": "failed"
  }
}
```

## Requirements

- Python 3.7+
- pytest
- pytest-json-report

Install dependencies:

```bash
pip install pytest pytest-json-report
```

## Agent Integration

This script is designed for automated agents to:

1. **Run tests systematically** - Execute test suites with consistent reporting
2. **Map failures to code** - Identify which source files need attention
3. **Prioritize fixes** - Focus on files with multiple failures
4. **Track progress** - Compare results across runs
5. **Generate reports** - Provide structured output for further analysis

### Integration Tips

- Use JSON output for programmatic processing
- Filter by test markers to run specific test suites
- Combine with git diff to focus on changed files
- Use exit codes to determine overall test status
- Parse error messages for specific failure patterns

## Advanced Usage

### Custom Test Arguments

```python
# Run only fast tests
results = mapper.run_tests_with_file_mapping(
    test_args=['-m', 'not slow']
)

# Run with coverage
results = mapper.run_tests_with_file_mapping(
    test_args=['--cov=api', '--cov-report=json']
)
```

### Error Pattern Analysis

```python
def analyze_error_patterns(results):
    """Analyze common error patterns across failures."""
    patterns = {}
    
    for source_file, tests in results.items():
        if source_file == '_summary':
            continue
            
        for test in tests:
            if test['outcome'] == 'failed':
                error = test['error']
                # Extract error type
                if 'KeyError' in error:
                    patterns.setdefault('KeyError', []).append(source_file)
                elif 'AssertionError' in error:
                    patterns.setdefault('AssertionError', []).append(source_file)
    
    return patterns
```

This test runner provides a robust foundation for automated test analysis and failure tracking in agent-driven development workflows.