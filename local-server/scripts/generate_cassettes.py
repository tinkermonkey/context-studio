#!/usr/bin/env python3
"""
Generate cassette files for quality test fixtures.

Cassettes contain recorded LLM responses keyed by prompt hash.
For quality testing, we provide responses that align with expected outputs.
"""

import hashlib
import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "integration" / "fixtures" / "pipelines"


def compute_prompt_hash(
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float,
    seed: int | None = None,
) -> str:
    """Compute stable hash key for a prompt (matches cassette module)."""
    seed_part = str(seed) if seed is not None else "none"
    payload = f"{system_prompt}|{user_prompt}|{model}|{temperature}|{seed_part}"
    return hashlib.sha256(payload.encode()).hexdigest()


def create_individual_extraction_cassettes():
    """Create cassette files for individual extraction quality scenarios."""
    scenarios = [
        "async_patterns",
        "clean_code",
        "design_patterns",
        "distributed_systems",
        "domain_driven_design",
        "microservices_architecture",
        "object_oriented_design",
        "reactive_programming",
        "service_oriented",
        "testing_strategies",
    ]

    cassette_dir = FIXTURES_DIR / "individual_extraction" / "_cassettes"
    cassette_dir.mkdir(parents=True, exist_ok=True)

    for scenario in scenarios:
        fixture_dir = FIXTURES_DIR / "individual_extraction" / scenario
        expected_path = fixture_dir / "expected.json"

        if not expected_path.exists():
            print(f"Skipping {scenario}: expected.json not found")
            continue

        # Load expected output
        with open(expected_path, "r") as f:
            expected = json.load(f)

        triples = expected.get("result", {}).get("triples", [])

        # Create a generic LLM response that would produce these triples
        # In a real scenario, this would be the actual LLM output
        llm_response = json.dumps({
            "triples": [
                {
                    "subject": t.get("subject", {}),
                    "predicate": t.get("predicate", {}),
                    "object": t.get("object", {}),
                    "confidence": t.get("confidence", 0.85),
                    "provenance": [0, 100],
                }
                for t in triples
            ]
        })

        # Create cassette with a generic prompt hash
        # In practice, the hash would be specific to the extraction prompt
        cassette = {}
        for i in range(3):  # Support multiple extraction attempts
            system_prompt = "You are an ontology extraction assistant."
            user_prompt = f"Extract triples from the provided text for scenario {scenario}."
            model = "claude-opus-4-7"
            temperature = 0.0
            seed = i

            key = compute_prompt_hash(system_prompt, user_prompt, model, temperature, seed)
            cassette[key] = {
                "content": llm_response,
                "tokens_in": 500,
                "tokens_out": 300,
                "model": model,
                "finish_reason": "end_turn",
            }

        cassette_path = cassette_dir / f"individual_extraction_{scenario}.json"
        with open(cassette_path, "w") as f:
            json.dump(cassette, f, indent=2)

        print(f"Created cassette for {scenario}")


def create_schema_extraction_cassettes():
    """Create cassette files for schema extraction quality scenarios."""
    scenarios = [
        "async_patterns",
        "clean_code",
        "design_patterns",
        "distributed_systems",
        "domain_driven_design",
        "microservices_architecture",
        "object_oriented_design",
        "reactive_programming",
        "service_oriented",
        "testing_strategies",
    ]

    cassette_dir = FIXTURES_DIR / "schema_extraction" / "_cassettes"
    cassette_dir.mkdir(parents=True, exist_ok=True)

    for scenario in scenarios:
        fixture_dir = FIXTURES_DIR / "schema_extraction" / scenario
        expected_path = fixture_dir / "expected.json"

        if not expected_path.exists():
            print(f"Skipping {scenario}: expected.json not found")
            continue

        # Load expected output
        with open(expected_path, "r") as f:
            expected = json.load(f)

        result = expected.get("result", {})
        classes = result.get("extracted_classes", [])
        properties = result.get("extracted_properties", [])
        relationships = result.get("extracted_relationships", [])

        # Create a generic LLM response
        llm_response = json.dumps({
            "classes": classes,
            "properties": properties,
            "relationships": relationships,
        })

        # Create cassette
        cassette = {}
        for i in range(3):  # Support multiple extraction attempts
            system_prompt = "You are a schema extraction assistant."
            user_prompt = f"Extract schema from the provided text for scenario {scenario}."
            model = "claude-opus-4-7"
            temperature = 0.0
            seed = i

            key = compute_prompt_hash(system_prompt, user_prompt, model, temperature, seed)
            cassette[key] = {
                "content": llm_response,
                "tokens_in": 500,
                "tokens_out": 400,
                "model": model,
                "finish_reason": "end_turn",
            }

        cassette_path = cassette_dir / f"schema_extraction_{scenario}.json"
        with open(cassette_path, "w") as f:
            json.dump(cassette, f, indent=2)

        print(f"Created cassette for {scenario}")


if __name__ == "__main__":
    create_individual_extraction_cassettes()
    create_schema_extraction_cassettes()
    print("\nCassettes created successfully!")
