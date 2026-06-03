#!/usr/bin/env python
"""
Regenerate cassettes by running orchestrators with fixture data and mock LLM responses.

This script:
1. Loads fixture input/expected files
2. Sets up the required ontology entities
3. Runs the orchestrator with a RecordingLLMProvider
4. The RecordingLLMProvider wraps a FakeLLMProvider that returns expected.json responses
5. The generated cassettes contain the correct prompt hashes
"""

import asyncio
import json
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent.parent))

import tempfile

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.ontology.entities import Class, ConceptScheme, PropertyDefinition, Taxonomy
from domain.pipelines.entities import PipelineType
from domain.pipelines.refinement.neighborhood import SchemaNeighborhoodTraversal
from domain.pipelines.schema_node_connection_refinement.orchestrator import (
    ConnectionRefinementOrchestrator,
    ConnectionRefinementState,
)
from domain.pipelines.schema_node_definition_refinement.orchestrator import (
    DefinitionRefinementOrchestrator,
    DefinitionRefinementState,
)
from tests.fakes.fake_llm_provider import FakeLLMProvider
from tests.integration.pipelines._harness.cassettes import RecordingLLMProvider


def create_test_database():
    """Create a temporary test database."""
    tmpdir = tempfile.mkdtemp()
    db_path = Path(tmpdir) / "test.db"
    db_url = f"sqlite:///{db_path}"

    engine = create_engine(db_url)
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine)
    return SQLiteOntologyRepository(SessionLocal)


async def regenerate_definition_cassettes():
    """Regenerate definition refinement cassettes."""
    print("Regenerating definition refinement cassettes...")

    cassettes_dir = (
        Path(__file__).parent.parent / "tests" / "integration" / "pipelines" / "_cassettes"
    )
    fixtures_dir = (
        Path(__file__).parent.parent
        / "tests"
        / "integration"
        / "fixtures"
        / "pipelines"
        / "schema_node_definition_refinement"
    )

    cassettes_dir.mkdir(parents=True, exist_ok=True)

    scenarios = sorted([d.name for d in fixtures_dir.iterdir() if d.is_dir()])

    for scenario in scenarios:
        fixture_dir = fixtures_dir / scenario
        input_file = fixture_dir / "input.json"
        expected_file = fixture_dir / "expected.json"
        cassette_path = cassettes_dir / f"definition_refinement_{scenario}.json"

        if not input_file.exists() or not expected_file.exists():
            print(f"  Skipping {scenario}: missing fixtures")
            continue

        with open(input_file) as f:
            fixture_input = json.load(f)
        with open(expected_file) as f:
            fixture_expected = json.load(f)

        try:
            # Setup ontology
            ontology_repo = create_test_database()

            tax = Taxonomy(
                id="test-ontology-123",
                identifier="test_ontology",
                title="Test Ontology",
                description="Test ontology",
            )
            ontology_repo.save_taxonomy(tax)

            scheme = ConceptScheme(
                id=str(uuid4()),
                identifier="test_scheme",
                taxonomy_id=tax.id,
                title="Test Scheme",
                description="Test scheme",
            )
            ontology_repo.save_concept_scheme(scheme)

            node_id = fixture_input.get("node_id", str(uuid4()))
            current_description = fixture_input.get("current_description", "")

            cls = Class(
                id=node_id,
                identifier=fixture_input.get("identifier", f"test_{scenario}"),
                concept_scheme_id=scheme.id,
                taxonomy_id=tax.id,
                title=fixture_input.get("title", scenario),
                description=current_description,
            )
            ontology_repo.save_class(cls)

            # Create LLM provider that returns expected descriptions as definitions
            # For no-regress fixtures, return empty (pipeline abstains)
            is_no_regress = fixture_input.get("is_no_regress", False)
            if is_no_regress:
                # No-regress: pipeline should abstain (return no candidates)
                expected_defs = []
            else:
                # Regular fixture: return expected description as candidate
                expected_description = fixture_expected.get("result", {}).get(
                    "expected_description", ""
                )
                if expected_description:
                    expected_defs = [
                        {
                            "definition": expected_description,
                            "confidence": 0.9,
                        }
                    ]
                else:
                    expected_defs = []
            llm_response = json.dumps(expected_defs)
            fake_provider = FakeLLMProvider(response_content=llm_response)

            # Record responses to cassette
            recording_provider = RecordingLLMProvider(fake_provider, cassette_path)

            # Run orchestrator
            traversal = SchemaNeighborhoodTraversal(ontology_repo=ontology_repo)
            orchestrator = DefinitionRefinementOrchestrator(
                llm_provider=recording_provider,
                traversal=traversal,
            )

            model = fixture_input.get("model", "claude-opus-4-7")
            temperature = fixture_input.get("temperature", 0.0)

            state = DefinitionRefinementState(
                run_id=str(uuid4()),
                pipeline_type=PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
                input_data={
                    "node_id": node_id,
                    "current_definition": current_description,
                    "model": model,
                    "temperature": temperature,
                },
            )

            await orchestrator.execute(state)
            recording_provider.flush()

            print(f"  ✓ {cassette_path.name}")
        except Exception as e:
            print(f"  ✗ {scenario}: {e}")


async def regenerate_connection_cassettes():
    """Regenerate connection refinement cassettes."""
    print("\nRegenerating connection refinement cassettes...")

    cassettes_dir = (
        Path(__file__).parent.parent / "tests" / "integration" / "pipelines" / "_cassettes"
    )
    fixtures_dir = (
        Path(__file__).parent.parent
        / "tests"
        / "integration"
        / "fixtures"
        / "pipelines"
        / "schema_node_connection_refinement"
    )

    cassettes_dir.mkdir(parents=True, exist_ok=True)

    scenarios = sorted([d.name for d in fixtures_dir.iterdir() if d.is_dir()])

    for scenario in scenarios:
        fixture_dir = fixtures_dir / scenario
        input_file = fixture_dir / "input.json"
        expected_file = fixture_dir / "expected.json"
        cassette_path = cassettes_dir / f"connection_refinement_{scenario}.json"

        if not input_file.exists() or not expected_file.exists():
            print(f"  Skipping {scenario}: missing fixtures")
            continue

        with open(input_file) as f:
            fixture_input = json.load(f)
        with open(expected_file) as f:
            fixture_expected = json.load(f)

        try:
            # Setup ontology
            ontology_repo = create_test_database()

            tax = Taxonomy(
                id="test-ontology-123",
                identifier="test_ontology",
                title="Test Ontology",
                description="Test ontology",
            )
            ontology_repo.save_taxonomy(tax)

            scheme = ConceptScheme(
                id=str(uuid4()),
                identifier="test_scheme",
                taxonomy_id=tax.id,
                title="Test Scheme",
                description="Test scheme",
            )
            ontology_repo.save_concept_scheme(scheme)

            # Create default properties
            for prop_label in ["inherits_from", "implements", "uses", "depends_on", "related_to"]:
                prop = PropertyDefinition(
                    id=str(uuid4()),
                    identifier=prop_label,
                    title=prop_label.replace("_", " ").title(),
                    description=f"Property: {prop_label}",
                )
                ontology_repo.save_property_definition(prop)

            scope_id = fixture_input.get("scope_id", str(uuid4()))
            scope_cls = Class(
                id=scope_id,
                identifier=fixture_input.get("scope_identifier", f"test_{scenario}"),
                concept_scheme_id=scheme.id,
                taxonomy_id=tax.id,
                title=fixture_input.get("scope_title", scenario),
                description=fixture_input.get("scope_description", ""),
            )
            ontology_repo.save_class(scope_cls)

            # Create LLM provider that returns expected deltas
            expected_deltas = fixture_expected.get("result", {}).get("deltas", [])
            llm_response = json.dumps(expected_deltas) if expected_deltas is not None else "[]"
            fake_provider = FakeLLMProvider(response_content=llm_response)

            # Record responses to cassette
            recording_provider = RecordingLLMProvider(fake_provider, cassette_path)

            # Run orchestrator
            traversal = SchemaNeighborhoodTraversal(ontology_repo=ontology_repo)
            orchestrator = ConnectionRefinementOrchestrator(
                llm_provider=recording_provider,
                traversal=traversal,
            )

            model = fixture_input.get("model", "claude-opus-4-7")
            temperature = fixture_input.get("temperature", 0.0)

            state = ConnectionRefinementState(
                run_id=str(uuid4()),
                pipeline_type=PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT,
                input_data={
                    "scope_id": scope_id,
                    "candidates": fixture_input.get("candidates", []),
                    "model": model,
                    "temperature": temperature,
                },
            )

            await orchestrator.execute(state)
            recording_provider.flush()

            print(f"  ✓ {cassette_path.name}")
        except Exception as e:
            print(f"  ✗ {scenario}: {e}")


async def main():
    """Main entry point."""
    await regenerate_definition_cassettes()
    await regenerate_connection_cassettes()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
