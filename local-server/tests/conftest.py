"""Root conftest for test configuration."""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Note: Pydantic validation errors are handled by FastAPI's default behavior
# which returns 422 (UNPROCESSABLE_ENTITY). No custom patching is needed.
