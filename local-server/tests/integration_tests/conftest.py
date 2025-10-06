"""
Minimal conftest for Phase 1 integration tests
Avoids loading full app dependencies
"""

import sys
from pathlib import Path

# Add local-server to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
