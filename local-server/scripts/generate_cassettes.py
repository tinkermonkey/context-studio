#!/usr/bin/env python3
"""
Note: Cassette files are now generated dynamically during test execution.

The RecordingLLMProvider records real LLM responses to cassettes when they don't exist.
This ensures cassettes contain accurate prompt hashes that match actual orchestrator prompts.

To regenerate cassettes:
1. Delete the _cassettes directories in fixture folders
2. Run tests with a real LLM provider
3. Cassettes will be recorded automatically

This script is kept for reference but is no longer used for cassette generation.
"""

if __name__ == "__main__":
    print("Cassettes are generated dynamically during test execution.")
