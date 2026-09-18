#!/usr/bin/env python
"""
Re-hash cassettes after prompt changes.

When extraction prompts change, their hashes change. This script updates
cassette files by recomputing hashes for the current prompts.

The script:
1. Finds all cassette files for a scenario
2. Reads the fixture to get the prompt inputs (text, model, temperature)
3. Builds prompts using the current ExtractionService
4. Computes new hashes
5. Re-indexes cassette entries with new hashes

Usage (from local-server/, venv active):
    python scripts/rehash_cassettes.py
"""

import json
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import Mock
from uuid import uuid4

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

sys.path.insert(0, str(Path(__file__).parent.parent))

from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.connection import (
    create_local_db_engine,
    create_session_factory,
)
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.extraction.services import ExtractionService
from domain.ontology.ports import OntologyRepository
from domain.ontology.services import OntologyService
from scripts.dr_ontology_loader import DR_TAXONOMY_IDENTIFIER, import_dr_ontology
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.integration.pipelines._harness.cassettes import _compute_prompt_hash
from tests.integration.pipelines._harness.dataset_split import (
    DR_BOOTSTRAP_SCENARIOS,
    INDIVIDUAL_EXTRACTION_SCENARIOS,
    RELABELED_ARXIV_SCENARIOS,
    WAVE4_INFORMAL_SCENARIOS,
)
from tests.integration.pipelines.conftest import _find_dr_spec_dir
from tests.fixtures.pipeline_fixtures import load_fixture


def rehash_cassettes() -> int:
    """Re-hash all cassette files with new prompt hashes."""
    print("Re-hashing cassettes after prompt changes...")

    spec_dir = _find_dr_spec_dir()
    if spec_dir is None:
        print("ERROR: DR spec checkout not found")
        return 1

    # Load DR ontology once
    engine = create_local_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    repo = SQLiteOntologyRepository(session_factory)
    ontology_service = OntologyService(
        repository=repo,
        embedding_service=FakeEmbeddingService(),
        event_publisher=InProcessEventPublisher(),
        schema_index=None,
    )
    import_dr_ontology(ontology_service, repo, spec_dir)
    dr_taxonomy = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)

    if dr_taxonomy is None:
        print("ERROR: DR taxonomy not loaded")
        return 1

    # Create extraction service
    extraction_service = ExtractionService(
        ontology_repo=repo,
        embedding_service=FakeEmbeddingService(),
        llm=Mock(),
        nlp=Mock(),
        reference_sources=[],
        event_publisher=InProcessEventPublisher(),
        extraction_repo=Mock(),
        extraction_run_repo=Mock(),
    )

    # Collect all scenarios
    all_scenarios = set()
    for scenario_set in [
        INDIVIDUAL_EXTRACTION_SCENARIOS,
        DR_BOOTSTRAP_SCENARIOS,
        WAVE4_INFORMAL_SCENARIOS,
        RELABELED_ARXIV_SCENARIOS,
    ]:
        if isinstance(scenario_set, dict):
            all_scenarios.update(scenario_set.keys())
        else:
            all_scenarios.update(scenario_set)

    # Find cassette directories
    cassette_base = (
        Path(__file__).parent.parent / "tests" / "integration" / "fixtures" / "cassettes"
    )
    cassette_dirs = [
        cassette_base / "individual_grounded_typing",
        cassette_base / "individual_extraction_default",
    ]

    updated_count = 0

    for cassette_dir in cassette_dirs:
        if not cassette_dir.exists():
            print(f"  Skipping {cassette_dir.name}: directory not found")
            continue

        print(f"\n  Processing {cassette_dir.name}...")

        for cassette_file in sorted(cassette_dir.glob("individual_*.json")):
            # Extract scenario name
            stem = cassette_file.stem
            if stem.startswith("individual_grounded_typing_"):
                scenario = stem.replace("individual_grounded_typing_", "")
            elif stem.startswith("individual_extraction_"):
                scenario = stem.replace("individual_extraction_", "")
            elif stem.startswith("individual_canon_"):
                scenario = stem.replace("individual_canon_", "")
            else:
                continue

            if scenario not in all_scenarios:
                continue

            try:
                # Load fixture
                fixture = dict(load_fixture("individual_extraction", scenario))
                text = fixture.get("text", "")
                model = fixture.get("model", "claude-opus-4-7")
                temperature = fixture.get("temperature", 0.0)

                # Load cassette
                with open(cassette_file) as f:
                    cassette_data = json.load(f)

                # Build prompts and compute new hashes
                system_prompt, user_prompt = extraction_service._build_individual_extraction_prompt(
                    text, dr_taxonomy
                )
                new_hash = _compute_prompt_hash(system_prompt, user_prompt, model, temperature, None)

                # Re-index cassette with new hash
                if cassette_data:
                    # Get the first entry (assumes all entries have same model/temperature)
                    first_entry = next(iter(cassette_data.values()))

                    # Create new cassette with updated hash
                    new_cassette = {new_hash: first_entry}

                    # Write back
                    with open(cassette_file, "w") as f:
                        json.dump(new_cassette, f, indent=2)

                    print(f"    ✓ {scenario}")
                    updated_count += 1
            except Exception as e:
                print(f"    ERROR {scenario}: {e}")

    print(f"\n✓ Updated {updated_count} cassette(s)")
    return 0


if __name__ == "__main__":
    sys.exit(rehash_cassettes())
