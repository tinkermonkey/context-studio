#!/usr/bin/env python3
"""Script to capture and display warnings from pytest"""
import subprocess
import sys

# Run pytest with warnings enabled
result = subprocess.run(
    [
        sys.executable,
        "-W", "always",
        "-m", "pytest",
        "tests/unit_tests/test_terms.py::test_move_terms_conflict_warning",
        "-v",
        "--tb=short",
        "--pythonwarnings=all"
    ],
    capture_output=True,
    text=True,
    cwd="/workspace/local-server"
)

print("STDOUT:")
print(result.stdout)
print("\nSTDERR:")
print(result.stderr)
print(f"\nReturn code: {result.returncode}")
