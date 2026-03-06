#!/usr/bin/env python3
"""Test script to verify predicate_set format handling."""

import json
import sys
import os

# Add the project root to the path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from utils.logger import get_logger  # noqa: E402

logger = get_logger("test")


def test_predicate_set_parsing():
    """Test the predicate_set parsing logic from to_domain_out function."""

    # Mock domain object
    class MockDomain:
        def __init__(self, domain_id, predicate_set):
            self.id = domain_id
            self.predicate_set = predicate_set

    def parse_predicate_set(domain):
        """Extracted logic from to_domain_out function."""
        predicate_set_list = None
        if domain.predicate_set:
            try:
                parsed_set = json.loads(domain.predicate_set)
                # Handle two formats:
                # 1. List format: ["predicate1", "predicate2"] (newer format from API)
                # 2. Object format: {"predicates": ["predicate1", "predicate2"]} (older format)
                if isinstance(parsed_set, list):
                    predicate_set_list = parsed_set
                elif isinstance(parsed_set, dict):
                    predicate_set_list = parsed_set.get("predicates", [])
                else:
                    logger.warning(
                        f"Domain {domain.id} predicate_set has unexpected format after JSON parsing: {type(parsed_set)}"
                    )
                    predicate_set_list = None
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(
                    f"Invalid JSON in domain {domain.id} predicate_set: {domain.predicate_set}, error: {e}"
                )
                predicate_set_list = None
        return predicate_set_list

    # Test cases
    test_cases = [
        # New list format
        ("list-format", '["predicate1", "predicate2", "predicate3"]'),
        # Old dict format
        ("dict-format", '{"predicates": ["predicate1", "predicate2"]}'),
        # Empty dict
        ("empty-dict", "{}"),
        # Invalid JSON
        ("invalid-json", "invalid json"),
        # None
        ("none", None),
        # Empty string
        ("empty", ""),
    ]

    print("Testing predicate_set format handling...")
    print("=" * 50)

    for test_name, predicate_set in test_cases:
        domain = MockDomain(f"test-{test_name}", predicate_set)
        result = parse_predicate_set(domain)
        print(f"Test: {test_name}")
        print(f"Input: {predicate_set}")
        print(f"Result: {result}")
        print(f"Type: {type(result)}")
        print("-" * 30)


if __name__ == "__main__":
    test_predicate_set_parsing()
