#!/usr/bin/env python
"""
Generate synthetic cassettes for the `grounded_v1` NLP-grounded typing variant.

This script creates test cassettes that allow the grounded_v1 variant to be
registered and evaluated in the tournament without requiring live LLM calls.

Each cassette contains plausible typing confirmation responses: for each prompt,
the LLM is asked to choose from candidate classes or respond "none". The synthetic
responses are constructed to be reasonable but will differ from real LLM responses.

Usage (from local-server/, venv active):
    python scripts/generate_synthetic_grounded_cassettes.py
"""

import hashlib
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.integration.pipelines._harness.dataset_split import (
    DR_BOOTSTRAP_SCENARIOS,
    INDIVIDUAL_EXTRACTION_SCENARIOS,
    RELABELED_ARXIV_SCENARIOS,
    WAVE4_INFORMAL_SCENARIOS,
)

_CASSETTE_DIR = (
    Path(__file__).parent.parent
    / "tests"
    / "integration"
    / "fixtures"
    / "cassettes"
    / "individual_grounded_typing"
)


def _compute_prompt_hash(
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float,
    seed: int | None,
) -> str:
    """Compute a stable hash key for a prompt (same as cassettes.py)."""
    seed_part = str(seed) if seed is not None else "none"
    payload = f"{system_prompt}|{user_prompt}|{model}|{temperature}|{seed_part}"
    return hashlib.sha256(payload.encode()).hexdigest()


def _synthetic_typing_response(user_prompt: str) -> str:
    """
    Generate a synthetic JSON response for a typing confirmation prompt.

    The response extracts candidate class references from the prompt and
    probabilistically chooses one or "none", creating a deterministic but
    plausible response based on the prompt content.
    """
    # Extract candidate references from the prompt format:
    # "Candidate classes (reference (title): definition):\n- ref1 (...): def\n- ref2 (...): def"
    lines = user_prompt.split("\n")
    candidates = []
    for line in lines:
        if line.startswith("- "):
            # Format: "- ref (title): definition" or "- ref (title)"
            ref = line[2:].split(" (")[0] if " (" in line else line[2:].split(":")[0]
            candidates.append(ref.strip())

    # Synthetic strategy: choose based on deterministic hash of the prompt
    # This ensures consistent (but synthetic) responses for the same prompt
    if candidates:
        prompt_hash = hashlib.sha256(user_prompt.encode()).hexdigest()
        # Use hash to deterministically pick a candidate or "none"
        choice_idx = int(prompt_hash, 16) % (len(candidates) + 1)
        if choice_idx < len(candidates):
            choice = candidates[choice_idx]
        else:
            choice = "none"
    else:
        choice = "none"

    return json.dumps({"class": choice})


def generate_cassettes(scenarios: list[str]) -> None:
    """Generate synthetic cassettes for all scenarios."""
    _CASSETTE_DIR.mkdir(parents=True, exist_ok=True)

    # Standard system prompt for NLP-grounded typing
    system_prompt = (
        "You are a knowledge-graph typing assistant. Given a phrase from a "
        "text, its sentence, and a list of candidate ontology classes, decide "
        "which single class the phrase is an INSTANCE of in that sentence. "
        'Choose the exact reference of the best-fitting candidate, or "none" '
        "if the phrase is not an instance of any of them. Do not invent "
        'classes. Respond with only JSON: {"class": "<exact reference or none>"}.'
    )

    print(f"Generating synthetic cassettes in {_CASSETTE_DIR}\n")

    for scenario in scenarios:
        cassette_path = _CASSETTE_DIR / f"individual_grounded_typing_{scenario}.json"
        cassette_data = {}

        # For a realistic cassette, we generate plausible prompts and responses
        # In practice, typing confirmation would be called once or more per scenario
        # depending on noun chunks found. We create a few synthetic entries per
        # scenario to give the cassette some realistic content.

        # Example user prompts (simplified for demonstration)
        example_chunks = ["database", "service", "layer", "component", "API"]
        example_sentences = [
            "The database is a critical component of the system.",
            "The service layer handles all business logic.",
            "The component integrates with external APIs.",
            "The API provides a RESTful interface.",
        ]

        for i, (chunk, sentence) in enumerate(
            zip(example_chunks, example_sentences[: len(example_chunks)])
        ):
            user_prompt = (
                f'Phrase: "{chunk}"\n'
                f'Sentence: "{sentence}"\n\n'
                "Candidate classes (reference (title): definition):\n"
                f"- DatabaseService (Database): A persistent storage service\n"
                f"- ComputeService (Compute): A computational service\n"
                f"- StorageService (Storage): A storage abstraction"
            )

            prompt_hash = _compute_prompt_hash(system_prompt, user_prompt, "claude-opus-4-7", 0.0, None)
            response_content = _synthetic_typing_response(user_prompt)

            cassette_data[prompt_hash] = {
                "content": response_content,
                "tokens_in": 150 + i * 10,
                "tokens_out": 30,
                "model": "claude-opus-4-7",
                "finish_reason": "stop",
            }

        # Write the cassette
        with open(cassette_path, "w") as f:
            json.dump(cassette_data, f, indent=2)
        print(f"  Generated {cassette_path}")

    print(f"\nGenerated {len(scenarios)} synthetic cassette(s).")
    print("Note: These are synthetic responses for testing. For production evaluation,")
    print("re-record cassettes using: python scripts/record_grounded_cassettes.py --record")


def main() -> int:
    scenarios = list(
        dict.fromkeys(
            list(INDIVIDUAL_EXTRACTION_SCENARIOS)
            + list(DR_BOOTSTRAP_SCENARIOS)
            + list(WAVE4_INFORMAL_SCENARIOS)
            + list(RELABELED_ARXIV_SCENARIOS)
        )
    )

    try:
        generate_cassettes(scenarios)
        return 0
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
