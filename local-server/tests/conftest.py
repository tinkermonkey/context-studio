"""Root conftest for test configuration."""

import sys
from pathlib import Path

# Add the project root to sys.path so that utils, adapters, and domain modules can be imported
# This is needed because pytest may be run from different directories
# NOTE: This MUST be done at module load time, before any imports, to work during collection
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Pre-import utils to ensure it's available when other modules need it
try:
    import utils.async_executor  # noqa: F401
    import utils.logger  # noqa: F401
except ImportError:
    # If utils is not available yet, it will be handled when the root is added to sys.path
    pass

# Note: Pydantic validation errors are handled by FastAPI's default behavior
# which returns 422 (UNPROCESSABLE_ENTITY). No custom patching is needed.
