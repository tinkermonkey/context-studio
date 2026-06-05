#!/usr/bin/env python
"""
Regenerate quality test cassettes for individual_extraction and schema_extraction pipelines.

This script:
1. Loads fixture input/expected files from quality test directories
2. Sets up the required ontology and other infrastructure
3. Runs the orchestrators with a RecordingLLMProvider that wraps FakeLLMProvider
4. The FakeLLMProvider returns expected.json responses
5. The generated cassettes contain the correct prompt hashes for deterministic testing
"""

import asyncio
import json
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.extraction_repo import SQLiteExtractionRepository
from adapters.persistence.sqlite.extraction_run_repo import SQLiteExtractionRunRepository
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.extraction.services import ExtractionService
from domain.ontology.entities import ConceptScheme, Taxonomy
from domain.pipelines.entities import PipelineType
from domain.pipelines.individual_extraction import (
    IndividualExtractionOrchestrator,
    IndividualExtractionState,
)
from domain.pipelines.schema_extraction import (
    SchemaExtractionOrchestrator,
    SchemaExtractionState,
)
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_llm_provider import FakeLLMProvider
from tests.fakes.fake_nlp_processor import FakeNLPProcessor
from tests.fakes.fake_reference_source import FakeReferenceSource
from tests.integration.pipelines._harness.cassettes import (
    RecordingLLMProvider,
)


def create_test_database():
    """Create a temporary test database."""
    tmpdir = tempfile.mkdtemp()
    db_path = Path(tmpdir) / "test.db"
    db_url = f"sqlite:///{db_path}"

    engine = create_engine(db_url)
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal, db_url


async def regenerate_individual_extraction_cassettes():
    """Regenerate individual_extraction quality cassettes."""
    print("Regenerating individual_extraction quality cassettes...")

    base_path = Path(__file__).parent.parent
    cassettes_dir = (
        base_path / "tests" / "integration" / "fixtures" / "cassettes"
        / "individual_extraction"
    )
    fixtures_dir = (
        base_path / "tests" / "integration" / "fixtures" / "pipelines"
        / "individual_extraction"
    )

    cassettes_dir.mkdir(parents=True, exist_ok=True)

    quality_scenarios = [
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

    failed_scenarios = []

    for scenario in quality_scenarios:
        fixture_dir = fixtures_dir / scenario
        input_file = fixture_dir / "input.json"
        expected_file = fixture_dir / "expected.json"
        cassette_path = cassettes_dir / f"individual_extraction_{scenario}.json"

        if not input_file.exists() or not expected_file.exists():
            print(f"  Skipping {scenario}: missing fixtures")
            continue

        with open(input_file) as f:
            fixture_input = json.load(f)
        with open(expected_file) as f:
            fixture_expected = json.load(f)

        try:
            # Setup ontology and databases
            session_factory, db_url = create_test_database()
            ontology_repo = SQLiteOntologyRepository(session_factory)
            extraction_repo = SQLiteExtractionRepository(session_factory)
            extraction_run_repo = SQLiteExtractionRunRepository(session_factory)

            # Create ontology with test data
            tax = Taxonomy(
                id="test-ontology-123",
                identifier="test_ontology",
                title="Test Ontology",
                description="Test ontology for quality testing",
            )
            ontology_repo.save_taxonomy(tax)

            scheme = ConceptScheme(
                id=str(uuid4()),
                identifier="test_scheme",
                taxonomy_id=tax.id,
                title="Test Scheme",
                description="Test scheme for quality testing",
            )
            ontology_repo.save_concept_scheme(scheme)

            # Create LLM provider that returns expected triples
            expected_triples = fixture_expected.get("result", {}).get("triples", [])
            llm_response = json.dumps(expected_triples)
            fake_provider = FakeLLMProvider(response_content=llm_response)

            # Record responses to cassette
            recording_provider = RecordingLLMProvider(fake_provider, cassette_path)

            # Create extraction service with recording provider
            embedding_service = FakeEmbeddingService()
            event_publisher = InProcessEventPublisher()

            extraction_service = ExtractionService(
                ontology_repo=ontology_repo,
                embedding_service=embedding_service,
                llm=recording_provider,
                nlp=FakeNLPProcessor(),
                reference_sources=[FakeReferenceSource()],
                event_publisher=event_publisher,
                extraction_repo=extraction_repo,
                extraction_run_repo=extraction_run_repo,
            )

            # Run orchestrator
            orchestrator = IndividualExtractionOrchestrator(
                llm_provider=recording_provider,
                extraction_service=extraction_service,
            )

            model = fixture_input.get("model", "claude-opus-4-7")
            temperature = fixture_input.get("temperature", 0.0)
            text = fixture_input.get("text", "")

            state = IndividualExtractionState(
                run_id=str(uuid4()),
                pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
                input_data={
                    "text": text,
                    "ontology_id": fixture_input.get("ontology_id", tax.id),
                    "model": model,
                    "temperature": temperature,
                },
            )

            await orchestrator.execute(state)
            recording_provider.flush()

            print(f"  ✓ {cassette_path.name}")
        except Exception as e:
            print(f"  ✗ {scenario}: {e}")
            failed_scenarios.append(scenario)

    return failed_scenarios


async def regenerate_schema_extraction_cassettes():
    """Regenerate schema_extraction quality cassettes."""
    print("\nRegenerating schema_extraction quality cassettes...")

    base_path = Path(__file__).parent.parent
    cassettes_dir = (
        base_path / "tests" / "integration" / "fixtures" / "cassettes"
        / "schema_extraction"
    )
    fixtures_dir = (
        base_path / "tests" / "integration" / "fixtures" / "pipelines"
        / "schema_extraction"
    )

    cassettes_dir.mkdir(parents=True, exist_ok=True)

    quality_scenarios = [
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

    failed_scenarios = []

    for scenario in quality_scenarios:
        fixture_dir = fixtures_dir / scenario
        input_file = fixture_dir / "input.json"
        expected_file = fixture_dir / "expected.json"
        cassette_path = cassettes_dir / f"schema_extraction_{scenario}.json"

        if not input_file.exists() or not expected_file.exists():
            print(f"  Skipping {scenario}: missing fixtures")
            continue

        with open(input_file) as f:
            fixture_input = json.load(f)
        with open(expected_file) as f:
            fixture_expected = json.load(f)

        try:
            # Setup ontology and databases
            session_factory, db_url = create_test_database()
            ontology_repo = SQLiteOntologyRepository(session_factory)
            SQLiteExtractionRepository(session_factory)
            SQLiteExtractionRunRepository(session_factory)

            # Create ontology with test data
            tax = Taxonomy(
                id="test-ontology-123",
                identifier="test_ontology",
                title="Test Ontology",
                description="Test ontology for quality testing",
            )
            ontology_repo.save_taxonomy(tax)

            scheme = ConceptScheme(
                id=str(uuid4()),
                identifier="test_scheme",
                taxonomy_id=tax.id,
                title="Test Scheme",
                description="Test scheme for quality testing",
            )
            ontology_repo.save_concept_scheme(scheme)

            # Create LLM provider that returns expected classes
            expected_classes = fixture_expected.get("result", {}).get("extracted_classes", [])
            llm_response = json.dumps(expected_classes)
            fake_provider = FakeLLMProvider(response_content=llm_response)

            # Record responses to cassette
            recording_provider = RecordingLLMProvider(fake_provider, cassette_path)

            # Run orchestrator (schema extraction doesn't use extraction_service)
            orchestrator = SchemaExtractionOrchestrator(
                llm_provider=recording_provider,
                ontology_repo=ontology_repo,
            )

            fixture_input.get("model", "claude-opus-4-7")
            fixture_input.get("temperature", 0.0)

            # Convert text to documents list if needed
            pipeline_input = fixture_input.copy()
            if "text" in pipeline_input and "documents" not in pipeline_input:
                pipeline_input["documents"] = [pipeline_input.pop("text")]

            state = SchemaExtractionState(
                run_id=str(uuid4()),
                pipeline_type=PipelineType.SCHEMA_EXTRACTION,
                input_data=pipeline_input,
            )

            await orchestrator.execute(state)
            recording_provider.flush()

            print(f"  ✓ {cassette_path.name}")
        except Exception as e:
            print(f"  ✗ {scenario}: {e}")
            failed_scenarios.append(scenario)

    return failed_scenarios


async def main():
    """Main entry point."""
    individual_failures = await regenerate_individual_extraction_cassettes()
    schema_failures = await regenerate_schema_extraction_cassettes()

    all_failures = individual_failures + schema_failures

    if all_failures:
        print(f"\n❌ Regeneration FAILED for {len(all_failures)} scenario(s): {all_failures}")
        sys.exit(1)

    print("\n✓ Quality cassette regeneration completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
