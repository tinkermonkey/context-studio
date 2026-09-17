#!/usr/bin/env python
"""
Helper script to prepare and validate cassette re-recording setup.

This script:
1. Validates API configuration
2. Shows cassette recording plan
3. Provides step-by-step instructions
4. Optionally performs dry-run checks

Usage:
    python scripts/prepare_cassette_recording.py
    python scripts/prepare_cassette_recording.py --check-config
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_settings


def check_api_configuration() -> bool:
    """Check if API credentials are configured."""
    settings = get_settings()
    llm_config = settings.llm

    print("\n" + "=" * 70)
    print("LLM API Configuration Check")
    print("=" * 70)

    has_any_key = False

    # Check OpenAI
    if llm_config.openai_api_key:
        print("✓ OpenAI API key: CONFIGURED")
        has_any_key = True
    else:
        print("✗ OpenAI API key: NOT CONFIGURED")

    # Check Anthropic
    if llm_config.anthropic_api_key:
        print("✓ Anthropic API key: CONFIGURED")
        has_any_key = True
    else:
        print("✗ Anthropic API key: NOT CONFIGURED")

    # Check OpenRouter
    if llm_config.openrouter_api_key:
        print("✓ OpenRouter API key: CONFIGURED")
        has_any_key = True
    else:
        print("✗ OpenRouter API key: NOT CONFIGURED")

    print()
    if not has_any_key:
        print("ERROR: No LLM provider API keys configured!")
        print("\nTo configure, edit config.json and add:")
        print(json.dumps({
            "llm": {
                "openrouter_api_key": "sk-or-...",  # For default pipeline
                "anthropic_api_key": "sk-ant-...",   # For grounded_v1 pipeline
            }
        }, indent=2))
        return False

    print("✓ At least one API key is configured")
    return has_any_key


def show_recording_plan() -> None:
    """Display the cassette recording plan."""
    print("\n" + "=" * 70)
    print("Cassette Re-Recording Plan")
    print("=" * 70)

    print("\nDefault Pipeline (individual_extraction_default):")
    print("  Scenarios: 14 (dev + bootstrap + wave4)")
    print("  Model: google/gemini-3-flash-preview (via OpenRouter)")
    print("  Command: python scripts/record_default_cassettes.py --record")
    print("  Cost: Very low (Gemini 3 Flash is cheap)")

    print("\nGrounded Variant (individual_grounded_typing):")
    print("  Scenarios: 16 (dev + bootstrap + wave4 + arxiv)")
    print("  Model: claude-opus-4-7 (via Anthropic)")
    print("  Command: python scripts/record_grounded_cassettes.py --record")
    print("  Cost: Moderate (multiple calls per scenario, ~50-100 total)")

    print("\nTotal Cassettes Affected: ~30 files to re-record")
    print("Total LLM Calls: ~14 + 50-100 = 60-120 API calls")


def show_step_by_step_instructions() -> None:
    """Display step-by-step instructions."""
    print("\n" + "=" * 70)
    print("Step-by-Step Instructions")
    print("=" * 70)

    steps = [
        ("1. Verify Configuration", [
            "python scripts/prepare_cassette_recording.py --check-config",
            "Ensure all needed API keys are configured in config.json",
        ]),
        ("2. Dry-Run: Default Pipeline", [
            "python scripts/record_default_cassettes.py",
            "Review which scenarios will be recorded and confirm plan",
        ]),
        ("3. Dry-Run: Grounded Variant", [
            "python scripts/record_grounded_cassettes.py",
            "Review which scenarios will be recorded and confirm plan",
        ]),
        ("4. Record Default Pipeline Cassettes", [
            "python scripts/record_default_cassettes.py --record",
            "Waits for completion (usually a few seconds per scenario)",
        ]),
        ("5. Record Grounded Variant Cassettes", [
            "python scripts/record_grounded_cassettes.py --record",
            "Waits for completion (may take several minutes)",
        ]),
        ("6. Verify Cassette Files", [
            "ls -la tests/integration/fixtures/cassettes/individual_extraction_default/ | wc -l",
            "ls -la tests/integration/fixtures/cassettes/individual_grounded_typing/ | wc -l",
            "Confirm both directories have expected number of cassette files",
        ]),
        ("7. Run Quality Tournament", [
            "python scripts/quality_tournament.py --pipeline individual",
            "Tournament evaluates both variants against dev/holdout splits",
            "Metrics written to experiments/reports/",
        ]),
        ("8. Check Tournament Results", [
            "cat experiments/reports/quality_tournament_*.json | tail",
            "Verify: dev strict-F1 ≥ 0.917 AND soft-F1 ≥ 0.928",
            "No regression from baseline means prompts are acceptable",
        ]),
        ("9. Commit Changes", [
            "git add tests/integration/fixtures/cassettes/",
            "git add experiments/reports/",
            "git commit -m 'Phase 3: Re-record cassettes after prompt updates'",
        ]),
    ]

    for step_title, commands in steps:
        print(f"\n{step_title}")
        print("-" * len(step_title))
        for cmd in commands:
            if cmd.startswith("python") or cmd.startswith("ls") or cmd.startswith("cat") or cmd.startswith("git"):
                print(f"  $ {cmd}")
            else:
                print(f"    {cmd}")


def show_troubleshooting() -> None:
    """Display troubleshooting tips."""
    print("\n" + "=" * 70)
    print("Troubleshooting")
    print("=" * 70)

    issues = [
        ("CassetteStaleError in Tests", [
            "Cause: Prompts changed since last cassette recording",
            "Fix: Re-record cassettes using this script's instructions",
        ]),
        ("API Key Not Found", [
            "Cause: config.json missing or API key not set",
            "Fix: Edit config.json and add your API key to llm section",
        ]),
        ("Record Script Times Out", [
            "Cause: LLM API is slow or unresponsive",
            "Fix: Run during off-peak hours, or use --only flag for subsets",
        ]),
        ("Quality Gate Fails (metrics regress)", [
            "Cause: New prompts produce lower-quality extractions",
            "Fix: Iterate on prompt wording and re-record cassettes",
        ]),
        ("Cassette File Corrupt", [
            "Cause: Interrupted cassette write or disk error",
            "Fix: Delete the problematic cassette and re-record that scenario",
        ]),
    ]

    for issue, details in issues:
        print(f"\n{issue}")
        for detail in details:
            print(f"  {detail}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare and validate cassette re-recording setup"
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Check and display API configuration",
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Show cassette recording plan",
    )
    parser.add_argument(
        "--instructions",
        action="store_true",
        help="Show step-by-step instructions",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Show all sections (default when no args)",
    )
    args = parser.parse_args()

    # Show all sections by default, or when --full is specified
    if not any([args.check_config, args.plan, args.instructions]) or args.full:
        check_api_configuration()
        show_recording_plan()
        show_step_by_step_instructions()
        show_troubleshooting()
    else:
        if args.check_config:
            if not check_api_configuration():
                return 1
        if args.plan:
            show_recording_plan()
        if args.instructions:
            show_step_by_step_instructions()

    print("\n" + "=" * 70)
    print("For detailed information, see CASSETTE_RECORDING_GUIDE.md")
    print("=" * 70 + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
