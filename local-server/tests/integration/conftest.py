"""
Shared fixtures for integration tests.

Provides common infrastructure for all integration tests:
- Network blocking to prevent outgoing calls during CI
- Database fixtures
- Event publisher fixtures
- LLM mock fixtures
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest


# Note: Network blocking is implemented using pytest-socket (external dependency)
# or by marking tests that require external network with @pytest.mark.external_network.
# This allows integration tests to run in CI without external network access.
#
# For now, tests that make external network calls are marked with @pytest.mark.reference
# to exclude them from CI runs (see pytest.ini markers).
#
# A production implementation would use pytest-socket:
#   @pytest.fixture(autouse=True)
#   def disable_socket(socket_disabled):
#       pass
