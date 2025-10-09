#!/bin/bash
cd /workspace/local-server
/usr/local/bin/python3 -m pytest tests/unit_tests/test_external_predicates.py tests/integration_tests/test_external_predicates_integration.py tests/integration_tests/test_external_predicates_e2e.py -v --tb=short
