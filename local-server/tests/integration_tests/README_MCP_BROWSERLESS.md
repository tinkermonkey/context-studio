# MCP Browserless Smoke Test

## Overview

This directory contains a smoke test for verifying browser automation via Playwright MCP (Model Context Protocol) integration.

## Test File

- `test_mcp_browserless_smoke.py` - Smoke test for MCP Browserless integration

## Test Requirements

The smoke test verifies the following functionality:

1. **Navigation**: Browser can navigate to https://linkagelabs.co
2. **Page Title**: Page title contains "Linkage Labs"
3. **HTTP Status**: Page loads successfully with status 200
4. **Screenshot**: Screenshot can be captured and saved to `test_outputs/test_screenshot.png`

## Current Status

⚠️ **PENDING MCP INTEGRATION**

The test structure is complete but requires MCP Playwright server integration to function. The test is currently marked as `skipped` until the following components are available:

1. MCP server with Playwright support running
2. MCP client integration to communicate with the server
3. Browser automation protocol implementation

## Running the Test

### Using pytest directly:

```bash
cd /workspace/local-server
source .venv/bin/activate
python tests/integration_tests/test_mcp_browserless_smoke.py
```

### Using pytest with verbose output:

```bash
cd /workspace/local-server
source .venv/bin/activate
pytest tests/integration_tests/test_mcp_browserless_smoke.py -v -s
```

### Running all integration tests:

```bash
cd /workspace/local-server
source .venv/bin/activate
pytest tests/integration_tests/ -v
```

## Expected Output

When run, the test will display:

```
============================================================
MCP Browserless Smoke Test
============================================================
Target URL: https://linkagelabs.co
Expected title contains: Linkage Labs
Screenshot path: test_outputs/test_screenshot.png
============================================================

Test Status: PENDING MCP INTEGRATION
```

## Integration Steps

To complete the integration with MCP Playwright server:

1. **Set up MCP Server**: Install and configure MCP server with Playwright support
2. **Install MCP Client**: Add MCP client library to `requirements.txt`
3. **Update Test Code**: Replace placeholder code with actual MCP client calls:
   - Initialize MCP client
   - Send navigation request to target URL
   - Retrieve page title and HTTP status
   - Request screenshot capture
   - Save screenshot to specified path
4. **Enable Assertions**: Uncomment assertion statements at the end of the test
5. **Run Test**: Execute test and verify all assertions pass

## Example MCP Integration Code

Once MCP client is available, the test would be updated similar to:

```python
from mcp_client import MCPClient
from pathlib import Path

def test_browser_navigation_and_screenshot(self, test_output_dir):
    screenshot_path = test_output_dir / self.SCREENSHOT_FILENAME

    # Initialize MCP client
    mcp_client = MCPClient()

    # Navigate to URL
    response = mcp_client.navigate(self.TEST_URL)
    page_title = response.title
    http_status = response.status

    # Capture screenshot
    screenshot_data = mcp_client.screenshot()
    with open(screenshot_path, 'wb') as f:
        f.write(screenshot_data)

    # Assertions
    assert self.EXPECTED_TITLE_TEXT in page_title
    assert http_status == 200
    assert screenshot_path.exists()
```

## Related Issues

- Issue #191: MCP Browserless smoke test
