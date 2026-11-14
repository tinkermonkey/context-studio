"""
Extracting a source into proposals (#1552), over real SQLite, the real readers,
the background run executor and the real orchestrators, with a fake extraction
port and a fake LLM (no model calls).

A PDF source is extracted through POST /api/sources/{id}/extract; the run
reads it chunk by chunk and ends in one proposal whose operations carry their
passages and near matches; applying it with "use existing" records provenance.
Re-extracting supersedes the earlier proposal. The source's last_extraction
follows the runs. A run whose provider refuses its requests stops at its first
chunk, and a failed run records what its model calls cost.
"""

import json
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.batch_repo import BatchRepository
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.connection import create_local_db_engine
from adapters.persistence.sqlite.entity_source_repo import SQLiteEntitySourceRepository
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.pipeline_run_repo import PipelineRepository
from adapters.persistence.sqlite.proposal_repo import SQLiteChangeProposalRepository
from adapters.persistence.sqlite.source_repo import SQLiteSourceRepository
from adapters.persistence.sqlite.transaction import SharedSessionFactory, SqliteTransactionScope
from adapters.pipelines.run_executor import BackgroundRunExecutor
from adapters.sources.file_store import LocalSourceFileStore
from adapters.sources.readers import source_readers
from adapters.web.sources_routes import router
from domain.extraction.services import ExtractionService
from domain.extraction.sources import SourceService
from domain.ontology.services import OntologyService
from domain.pipelines.entities import PipelineRunStatus
from domain.pipelines.exceptions import (
    LLMProviderError,
    LLMRateLimitError,
    LLMRequestRefusedError,
    LLMTransientError,
)
from domain.pipelines.individual_extraction.bootstrap import register_individual_extraction
from domain.pipelines.ports import LLMResponse
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from domain.pipelines.schema_extraction.bootstrap import register_schema_extraction
from domain.pipelines.source_extraction import SourceExtractionService
from domain.versioning.proposal_service import ProposalService
from domain.versioning.proposals import OperationStatus, ProposalStatus
from domain.versioning.revert_service import RevertService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_source_repository import FakePageFetcher
from tests.integration.sources.pdfs import scanned_pdf, text_pdf
from tests.unit.domain.pipelines.test_schema_extraction_orchestrator import _MockLLM
from tests.utils.change_recording import wire_change_recorder

PAGE_1 = ["Whirlpool WRF555SDFZ use and care guide", "The WRF555SDFZ is a Microservice."]
PAGE_2 = ["Parts and features", "The WRF555SDFZ is made by Acme. Acme Microservice."]
# The same kind of guide in French, as an install sheet's translated copy (#1575)
FRENCH_PAGE = [
    "INSTRUCTIONS D'INSTALLATION",
    "Support se fixe au mur avec les vis et le ruban de peintre.",
    "Placez le support sur le mur pour que la station tienne, et serrez les vis a la main.",
]


class FakeExtraction:
    """Finds the model, its maker and their relationship in whatever chunk it is given."""

    def __init__(self, house):
        self.house = house
        self.calls = 0

    def extract_triples(self, text, ontology_id, model, temperature, **_):
        self.calls += 1
        triples = []
        if "WRF555SDFZ" in text:
            start = text.index("WRF555SDFZ")
            triples.append(
                {
                    "subject": {"kind": "individual", "id": "", "label": "Whirlpool WRF555SDFZ"},
                    "predicate": {"property_definition_id": "", "label": "is_a"},
                    "object": {"kind": "class", "id": "", "label": "house_appliance"},
                    "confidence": 0.94,
                    "provenance": {"quote": "WRF555SDFZ", "start": start, "end": start + 10},
                    "near_matches": [
                        {
                            "entity_id": self.house["fridge"],
                            "label": "Kitchen refrigerator",
                            "similarity": 0.93,
                        }
                    ],
                }
            )
        if "made by Acme" in text:
            start = text.index("made by Acme")
            acme = text.index("Acme")
            triples += [
                {
                    "subject": {"kind": "individual", "id": "", "label": "Acme"},
                    "predicate": {"property_definition_id": "", "label": "is_a"},
                    "object": {"kind": "class", "id": "", "label": "Business"},
                    "confidence": 0.9,
                    "provenance": {"quote": "Acme", "start": acme, "end": acme + 4},
                },
                {
                    "subject": {"kind": "individual", "id": "", "label": "Whirlpool WRF555SDFZ"},
                    "predicate": {
                        "property_definition_id": self.house["made_by"],
                        "label": "made_by",
                    },
                    "object": {"kind": "individual", "id": "", "label": "Acme"},
                    "confidence": 0.86,
                    "provenance": {"quote": "made by Acme", "start": start, "end": start + 12},
                },
            ]
        return SimpleNamespace(
            triples=triples, warnings=[], metadata={"tokens_used": 1}, failure_reason=None
        )


@pytest.fixture()
def factory(tmp_path):
    engine = create_local_db_engine(f"sqlite:///{tmp_path / 'local.db'}")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


@pytest.fixture()
def parts(factory):
    shared = SharedSessionFactory(factory)
    repo = SQLiteOntologyRepository(session_factory=shared)
    change_repo = SQLiteChangeRepository(session_factory=shared)
    publisher = InProcessEventPublisher()
    wire_change_recorder(publisher, change_repo)
    ontology = OntologyService(repo, FakeEmbeddingService(), publisher)
    scope = SqliteTransactionScope(shared)
    proposals_repo = SQLiteChangeProposalRepository(shared)
    proposals = ProposalService(
        proposals_repo,
        ontology,
        repo,
        RevertService(change_repo=change_repo, ontology_repo=repo, transaction_scope=scope),
        transaction_scope=scope,
        entity_sources=SQLiteEntitySourceRepository(shared),
    )
    return SimpleNamespace(
        ontology=ontology, repo=repo, proposals=proposals, proposals_repo=proposals_repo
    )


@pytest.fixture()
def house(parts):
    ontology = parts.ontology
    taxonomy = ontology.create_taxonomy(title="House")
    scheme = ontology.create_scheme(taxonomy_id=taxonomy.id, title="Resources")
    appliance = ontology.create_class(scheme.id, "Appliance", identifier="house_appliance")
    business = ontology.create_class(scheme.id, "Business")
    made_by = ontology.create_property_definition(
        "made_by", "made by", domain_class_id=appliance.id, range_class_id=business.id
    )
    home = ontology.create_dataset(taxonomy.id, "home", "Home")
    ontology.create_dataset(taxonomy.id, "cabin", "Cabin")
    fridge = ontology.create_individual(appliance.id, "Kitchen refrigerator", dataset_id=home.id)
    return {
        "taxonomy": taxonomy.id,
        "made_by": made_by.id,
        "home": home.id,
        "fridge": fridge.id,
        "scheme": scheme.id,
    }


@pytest.fixture()
def extraction(house):
    return FakeExtraction(house)


@pytest.fixture()
def app(tmp_path, factory, parts, house, extraction):
    implementations = PipelineImplementationRegistry()
    configurations = PipelineConfigurationRegistry()
    register_individual_extraction(implementations, configurations)
    register_schema_extraction(implementations, configurations)
    runs = PipelineRepository(factory)
    executor = BackgroundRunExecutor(
        runs=runs,
        batches=BatchRepository(factory),
        implementations=implementations,
        configurations=configurations,
        llm_provider=_MockLLM(),
        app_state=SimpleNamespace(
            extraction_service=extraction,
            ontology_repo=parts.repo,
            proposal_service=parts.proposals,
        ),
        poll_seconds=0.05,
    )
    sources = SQLiteSourceRepository(factory)
    app = FastAPI()
    app.include_router(router)
    app.state.source_service = SourceService(
        sources=sources,
        ontology_repo=parts.repo,
        readers=source_readers(),
        fetcher=FakePageFetcher(),
        files=LocalSourceFileStore(tmp_path / "sources"),
    )
    app.state.source_extraction_service = SourceExtractionService(
        sources=sources,
        ontology_repo=parts.repo,
        implementations=implementations,
        configurations=configurations,
        submitter=executor,
        runs=runs,
        proposals=parts.proposals_repo,
    )
    app.state.executor = executor
    app.state.runs = runs
    app.state.extraction = extraction
    yield app
    executor.stop()


@pytest.fixture()
def client(app):
    return TestClient(app)


def add_pdf(client, house, pages=(PAGE_1, PAGE_2), name="wrf555.pdf"):
    response = client.post(
        "/api/sources",
        files={"file": (name, text_pdf(list(pages)), "application/pdf")},
        data={"taxonomy_id": house["taxonomy"], "dataset": "home"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def wait_for(predicate, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.02)
    raise AssertionError("condition not met in time")


def finished(app, run_id):
    run = app.state.runs.get(run_id)
    return run if run.status not in (PipelineRunStatus.PENDING, PipelineRunStatus.RUNNING) else None


def extract(client, source_id, **body):
    return client.post(f"/api/sources/{source_id}/extract", json={"dataset": "home", **body})


class TestExtractRoute:
    def test_extract_starts_a_background_run(self, client, app, house):
        source = add_pdf(client, house)

        response = extract(client, source["id"])

        assert response.status_code == 202, response.text
        [run] = response.json()["runs"]
        assert run["pipeline"] == "individual_extraction"
        stored = app.state.runs.get(run["run_id"])
        assert stored.status is PipelineRunStatus.PENDING
        assert stored.input_summary["source_id"] == source["id"]
        assert stored.input_summary["dataset_id"] == house["home"]
        assert stored.configuration_ref == "extraction-default"

    def test_schema_adds_a_schema_extraction_run(self, client, app, house):
        source = add_pdf(client, house)

        runs = extract(client, source["id"], schema=True).json()["runs"]

        assert [r["pipeline"] for r in runs] == ["individual_extraction", "schema_extraction"]
        schema_run = app.state.runs.get(runs[1]["run_id"])
        assert schema_run.input_summary["source_id"] == source["id"]
        extraction_ids = {
            app.state.runs.get(r["run_id"]).input_summary["extraction_id"] for r in runs
        }
        assert len(extraction_ids) == 1

    def test_a_source_that_is_not_ready_or_removed_is_a_conflict(self, client, house):
        failed = client.post(
            "/api/sources",
            files={"file": ("scan.pdf", scanned_pdf(), "application/pdf")},
            data={"taxonomy_id": house["taxonomy"], "dataset": "home"},
        ).json()
        assert extract(client, failed["id"]).status_code == 409

        removed = add_pdf(client, house)
        client.delete(f"/api/sources/{removed['id']}")
        assert extract(client, removed["id"]).status_code == 409

    @pytest.mark.parametrize("pages", ["0-2", "two", "3", "2-1"])
    def test_a_bad_page_range_is_unprocessable(self, client, house, pages):
        source = add_pdf(client, house)
        assert extract(client, source["id"], pages=pages).status_code == 422

    def test_an_unknown_dataset_source_or_configuration(self, client, house):
        source = add_pdf(client, house)
        assert extract(client, source["id"], dataset="garage").status_code == 404
        assert extract(client, "no-such-source").status_code == 404
        assert (
            extract(client, source["id"], configuration_ref="extraction-open-v1").status_code == 422
        )

    def test_a_named_implementation_runs_with_its_own_configuration(self, client, app, house):
        source = add_pdf(client, house)

        response = extract(client, source["id"], implementation_id="find_then_type")

        assert response.status_code == 202, response.text
        [run] = response.json()["runs"]
        stored = app.state.runs.get(run["run_id"])
        assert stored.implementation_id == "find_then_type"
        assert stored.configuration_ref == "extraction-find-then-type"
        assert stored.input_summary["source_id"] == source["id"]

    @pytest.mark.parametrize(
        "body, names",
        [
            ({"implementation_id": "no_such"}, "no_such"),
            # Registered for individual extraction, but it cannot extract a source
            ({"implementation_id": "open_v1"}, "open_v1"),
            (
                {"implementation_id": "find_then_type", "configuration_ref": "extraction-default"},
                "extraction-default",
            ),
        ],
    )
    def test_an_implementation_that_cannot_extract_the_source_is_unprocessable(
        self, client, app, house, body, names
    ):
        source = add_pdf(client, house)

        response = extract(client, source["id"], **body)

        assert response.status_code == 422, response.text
        assert names in response.json()["detail"]
        listed = client.get(f"/api/sources/{source['id']}").json()
        assert listed["last_extraction"] is None

    def test_a_source_of_boilerplate_only_is_extracted_only_when_asked(self, client, app, house):
        source = add_pdf(client, house, pages=(FRENCH_PAGE,), name="fr.pdf")

        refused = extract(client, source["id"])
        assert refused.status_code == 422
        assert "skip_boilerplate" in refused.json()["detail"]

        response = extract(client, source["id"], skip_boilerplate=False)
        assert response.status_code == 202, response.text
        [run] = response.json()["runs"]
        assert app.state.runs.get(run["run_id"]).input_summary["skip_boilerplate"] is False

    def test_a_never_extracted_source_has_no_last_extraction(self, client, house):
        source = add_pdf(client, house)
        assert source["last_extraction"] is None
        assert client.get(f"/api/sources/{source['id']}").json()["last_extraction"] is None


class TestExtractionToProposal:
    def test_a_pdf_extracts_into_one_proposal_that_applies_with_provenance(
        self, client, app, parts, house
    ):
        source = add_pdf(client, house)
        [run] = extract(client, source["id"]).json()["runs"]
        app.state.executor.start()
        done = wait_for(lambda: finished(app, run["run_id"]))

        assert done.status is PipelineRunStatus.COMPLETED, done.failure_reason
        assert done.proposal_id
        assert done.output_summary["proposal_id"] == done.proposal_id
        assert (done.items_done, done.items_total) == (1, 1)

        proposal = parts.proposals.get(done.proposal_id)
        assert proposal.title == "Extraction: wrf555"
        assert proposal.dataset_id == house["home"]
        assert proposal.client_metadata["run_id"] == run["run_id"]
        model, acme, made_by = proposal.operations
        assert (model.kind.value, model.ref, model.fields["title"]) == (
            "individual",
            "i1",
            "Whirlpool WRF555SDFZ",
        )
        assert model.probability == 0.94
        assert model.alternatives == [
            {"kind": "existing", "entity_id": house["fridge"], "similarity": 0.93}
        ]
        [evidence] = model.evidence
        page_2 = source["page_starts"][1]
        assert evidence["source_id"] == source["id"] and evidence["page"] == 1
        text = client.get(f"/api/sources/{source['id']}/text").json()["text"]
        assert text[evidence["start"] : evidence["end"]] == "WRF555SDFZ"
        assert acme.fields["title"] == "Acme"
        assert made_by.fields == {
            "source_id": "$i1",
            "target_id": "$i2",
            "property_definition_id": house["made_by"],
        }
        [link_evidence] = made_by.evidence
        assert link_evidence["page"] == 2 and link_evidence["start"] >= page_2
        assert text[link_evidence["start"] : link_evidence["end"]] == "made by Acme"

        last = client.get(f"/api/sources/{source['id']}").json()["last_extraction"]
        assert last["dataset_id"] == house["home"]
        assert last["runs"] == [
            {
                "run_id": run["run_id"],
                "pipeline": "individual_extraction",
                "status": "completed",
                "items_done": 1,
                "items_total": 1,
                "proposal_id": proposal.id,
                "operations": 3,
            }
        ]
        listed = client.get("/api/sources", params={"taxonomy_id": house["taxonomy"]}).json()
        assert listed["items"][0]["last_extraction"]["runs"][0]["operations"] == 3

        # Use the existing refrigerator: the create is dropped, the relationship repointed
        applied = parts.proposals.apply(
            proposal.id,
            [o.id for o in proposal.operations],
            chosen_alternatives={model.id: {"kind": "existing", "entity_id": house["fridge"]}},
        )
        assert all(o.status is OperationStatus.APPLIED for o in applied.operations)
        relationship = parts.repo.get_relationship(applied.operations[2].result_entity_id)
        assert relationship.source_id == house["fridge"]
        [fridge_source] = parts.proposals.sources_of(house["fridge"])
        assert (fridge_source.source_id, fridge_source.page, fridge_source.quote) == (
            source["id"],
            1,
            "WRF555SDFZ",
        )
        [edge_source] = parts.proposals.sources_of(relationship.id)
        assert edge_source.page == 2

    def test_re_extracting_supersedes_the_earlier_proposal(self, client, app, parts, house):
        source = add_pdf(client, house)
        [first] = extract(client, source["id"]).json()["runs"]
        app.state.executor.start()
        first_run = wait_for(lambda: finished(app, first["run_id"]))
        [second] = extract(client, source["id"]).json()["runs"]
        second_run = wait_for(lambda: finished(app, second["run_id"]))

        older = parts.proposals.get(first_run.proposal_id)
        assert older.status is ProposalStatus.DONE
        assert {o.status for o in older.operations} == {OperationStatus.REJECTED}
        assert {o.reason for o in older.operations} == {
            f"superseded by extraction proposal {second_run.proposal_id}"
        }
        assert parts.proposals.get(second_run.proposal_id).status is ProposalStatus.OPEN
        last = client.get(f"/api/sources/{source['id']}").json()["last_extraction"]
        assert [r["run_id"] for r in last["runs"]] == [second["run_id"]]

    def test_a_page_range_extracts_only_those_pages(self, client, app, parts, house):
        source = add_pdf(client, house)
        [run] = extract(client, source["id"], pages="2").json()["runs"]
        app.state.executor.start()
        done = wait_for(lambda: finished(app, run["run_id"]))

        operations = parts.proposals.get(done.proposal_id).operations
        assert {e["page"] for o in operations for e in o.evidence} == {2}

    def test_other_language_pages_are_skipped_and_counted(self, client, app, parts, house):
        source = add_pdf(client, house, pages=(PAGE_1, FRENCH_PAGE, PAGE_2))
        [run] = extract(client, source["id"]).json()["runs"]
        app.state.executor.start()
        done = wait_for(lambda: finished(app, run["run_id"]))

        summary = done.output_summary
        assert summary["skipped_sections_by_reason"] == {"other_language": 1}
        [section] = summary["skipped_sections"]
        assert (section["page_first"], section["page_last"]) == (2, 2)
        # The English pages either side are read, each as its own chunk
        assert [c["page_first"] for c in summary["metadata"]["chunks"]] == [1, 3]
        assert app.state.extraction.calls == 2
        assert done.proposal_id is not None

    def test_extractions_of_other_pages_stay_side_by_side(self, client, app, parts, house):
        source = add_pdf(client, house)
        [page_2] = extract(client, source["id"], pages=" 2 , 2-2").json()["runs"]
        app.state.executor.start()
        page_2_run = wait_for(lambda: finished(app, page_2["run_id"]))
        [whole] = extract(client, source["id"]).json()["runs"]
        whole_run = wait_for(lambda: finished(app, whole["run_id"]))

        page_2_proposal = parts.proposals.get(page_2_run.proposal_id)
        assert page_2_proposal.client_metadata["pages"] == "2"
        assert page_2_proposal.client_metadata["extraction_started_at"]
        assert page_2_proposal.status is ProposalStatus.OPEN
        assert parts.proposals.get(whole_run.proposal_id).client_metadata["pages"] is None

    def test_a_run_with_nothing_to_propose_completes_with_a_warning(self, client, app, house):
        source = add_pdf(client, house, pages=(["Nothing to see here."],), name="blank.pdf")
        [run] = extract(client, source["id"]).json()["runs"]
        app.state.executor.start()
        done = wait_for(lambda: finished(app, run["run_id"]))

        assert done.status is PipelineRunStatus.COMPLETED
        assert done.proposal_id is None
        assert any("Nothing to propose" in w for w in done.output_summary["warnings"])
        reason = "The run found no candidates in the text."
        assert done.output_summary["no_proposal_reason"] == reason
        assert done.output_summary["skipped_by_reason"] == {}
        last = client.get(f"/api/sources/{source['id']}").json()["last_extraction"]
        assert last["runs"][0]["proposal_id"] is None
        assert last["runs"][0]["operations"] is None

    def test_schema_extraction_proposes_classes_from_the_selected_pages(
        self, client, app, parts, house
    ):
        source = add_pdf(client, house)
        runs = extract(client, source["id"], schema=True, pages="2").json()["runs"]
        app.state.executor.start()
        schema_run = wait_for(lambda: finished(app, runs[1]["run_id"]))

        assert schema_run.status is PipelineRunStatus.COMPLETED, schema_run.failure_reason
        proposal = parts.proposals.get(schema_run.proposal_id)
        assert proposal.client_metadata["pipeline"] == "schema_extraction"
        [microservice] = [o for o in proposal.operations if o.fields.get("title") == "Microservice"]
        assert microservice.kind.value == "class"
        assert microservice.fields["concept_scheme_id"] == house["scheme"]
        assert microservice.fields["identifier"] == "microservice"
        assert microservice.evidence and {e["page"] for e in microservice.evidence} == {2}
        text = client.get(f"/api/sources/{source['id']}/text").json()["text"]
        assert all(text[e["start"] : e["end"]] == e["quote"] for e in microservice.evidence)
        assert (schema_run.items_done, schema_run.items_total) == (1, 1)
        last = client.get(f"/api/sources/{source['id']}").json()["last_extraction"]
        assert [r["pipeline"] for r in last["runs"]] == [
            "individual_extraction",
            "schema_extraction",
        ]


class TwoPassLLM:
    """
    Answers the extraction service's two passes as real models do (#1450): pass 1
    types each individual with an is_a triple whose property_definition_id is
    "is_a", copied from the prompt's example; pass 2 names the relationship.
    """

    IDENTIFIED = {
        "triples": [
            {
                "subject": {"kind": "individual", "id": "", "label": "WRF555SDFZ", "class_id": ""},
                "predicate": {"property_definition_id": "is_a", "label": "is_a"},
                "object": {"kind": "class", "id": "", "label": "house_appliance"},
                "confidence": 0.95,
                "provenance": {"text_offset_start": 0, "text_offset_end": 0, "raw": "WRF555SDFZ"},
            },
            {
                "subject": {"kind": "individual", "id": "", "label": "Acme", "class_id": ""},
                "predicate": {"property_definition_id": "is_a", "label": "is_a"},
                "object": {"kind": "class", "id": "", "label": "Business"},
                "confidence": 0.9,
                "provenance": {"text_offset_start": 0, "text_offset_end": 0, "raw": "Acme"},
            },
        ]
    }
    RELATED = {
        "triples": [
            {
                "subject": {"kind": "individual", "id": "", "label": "WRF555SDFZ"},
                "predicate": {"property_definition_id": "made_by", "label": "made_by"},
                "object": {"kind": "individual", "id": "", "label": "Acme"},
                "confidence": 0.85,
                "provenance": {
                    "text_offset_start": 0,
                    "text_offset_end": 0,
                    "raw": "WRF555SDFZ is made by Acme",
                },
            }
        ]
    }

    def complete(self, system_prompt, user_prompt, model, **_):
        identifying = "identify the individuals" in system_prompt
        content = json.dumps(self.IDENTIFIED if identifying else self.RELATED)
        return LLMResponse(content, 10, 20, duration_ms=5, finish_reason="stop", model=model)


class TestTwoPassExtractionToProposal:
    """The real orchestrator and extraction service, with a fake LLM, on a source."""

    @pytest.fixture()
    def extraction(self, parts):
        return ExtractionService(
            ontology_repo=parts.repo,
            embedding_service=FakeEmbeddingService(),
            llm=TwoPassLLM(),
            nlp=Mock(),
            reference_sources=[],
            event_publisher=InProcessEventPublisher(),
            extraction_repo=Mock(),
            extraction_run_repo=Mock(),
        )

    def test_typed_individuals_and_their_relationship_are_proposed(self, client, app, parts, house):
        source = add_pdf(client, house)
        [run] = extract(client, source["id"]).json()["runs"]
        app.state.executor.start()
        done = wait_for(lambda: finished(app, run["run_id"]))

        assert done.status is PipelineRunStatus.COMPLETED, done.failure_reason
        assert done.output_summary["no_proposal_reason"] is None
        assert done.output_summary["skipped_by_reason"] == {}
        proposal = parts.proposals.get(done.proposal_id)
        model, acme, made_by = proposal.operations
        assert (model.kind.value, model.ref, model.fields["title"]) == (
            "individual",
            "i1",
            "WRF555SDFZ",
        )
        assert (acme.kind.value, acme.ref, acme.fields["title"]) == ("individual", "i2", "Acme")
        assert made_by.kind.value == "relationship"
        assert made_by.fields == {
            "source_id": "$i1",
            "target_id": "$i2",
            "property_definition_id": house["made_by"],
        }
        text = client.get(f"/api/sources/{source['id']}/text").json()["text"]
        [link_evidence] = made_by.evidence
        assert text[link_evidence["start"] : link_evidence["end"]] == "WRF555SDFZ is made by Acme"


def _long_pages(count):
    """Pages of about 7000 characters of plain sentences: a chunk each."""
    return [
        [
            f"Section {page} line {line} names the WRF555SDFZ ice maker once more."
            for line in range(110)
        ]
        for page in range(count)
    ]


class RefusingLLM:
    """A provider that rejects its API key, counting the requests it was sent."""

    def __init__(self):
        self.calls = 0

    def complete(self, *args, **kwargs):
        self.calls += 1
        raise LLMRequestRefusedError("OpenRouter API key is invalid or unauthorized")


class NeverRelatingLLM(TwoPassLLM):
    """Answers the identify pass; every answer to the derive pass is cut short."""

    def __init__(self):
        self.calls = 0

    def complete(self, system_prompt, user_prompt, model, **_):
        self.calls += 1
        response = super().complete(system_prompt, user_prompt, model)
        if "identify the individuals" in system_prompt:
            return response
        return LLMResponse(response.content[:30], 10, 20, 5, finish_reason="length", model=model)

    def forget(self, **request):
        pass


class FailingFirstLLM(TwoPassLLM):
    """Fails its first requests with these errors, in order, then answers."""

    def __init__(self, *failures):
        self._failures = list(failures)
        self.calls = 0

    def complete(self, system_prompt, user_prompt, model, **_):
        self.calls += 1
        if self._failures:
            raise self._failures.pop(0)
        return super().complete(system_prompt, user_prompt, model)


def _run_to_end(client, app, house, pages):
    """Extract a PDF of these pages and return its run once it has ended."""
    source = add_pdf(client, house, pages=pages)
    [run] = extract(client, source["id"]).json()["runs"]
    app.state.executor.start()
    return wait_for(lambda: finished(app, run["run_id"]))


class TestFailedExtractionRun:
    """
    The real orchestrator and extraction service over a provider that fails,
    run by the executor: what the stored run says of the failure and its cost.
    """

    @pytest.fixture()
    def extraction(self, parts, llm):
        return ExtractionService(
            ontology_repo=parts.repo,
            embedding_service=FakeEmbeddingService(),
            llm=llm,
            nlp=Mock(),
            reference_sources=[],
            event_publisher=InProcessEventPublisher(),
            extraction_repo=Mock(),
            extraction_run_repo=Mock(),
            sleep=lambda seconds: None,
        )

    class TestProviderDownForTheFirstChunk:
        """Chunk 1 is lost to provider failures; the provider then answers."""

        ATTEMPTS = {
            "server errors": (
                [LLMTransientError("OpenRouter API error: 503")] * 3,
                "The LLM request for identify_individuals still failed after 3 attempts:"
                " OpenRouter API error: 503",
            ),
            # The rate limit was met once, by the last attempt, and never asked again
            "a rate limit at the last attempt": (
                [
                    LLMTransientError("OpenRouter API error: 503"),
                    LLMTransientError("OpenRouter API error: 503"),
                    LLMRateLimitError("OpenRouter rate limit exceeded"),
                ],
                "The LLM gave no complete answer for identify_individuals in 3 attempts"
                " that failed in different ways, the last with: OpenRouter rate limit exceeded",
            ),
            # A direct provider's outage, which its SDK already retried: one request
            "an outage the SDK retried": (
                [LLMProviderError("The anthropic provider answered with a server error: 529")],
                "The anthropic provider answered with a server error: 529",
            ),
        }

        @pytest.fixture(params=list(ATTEMPTS))
        def attempts(self, request):
            return self.ATTEMPTS[request.param]

        @pytest.fixture()
        def llm(self, attempts):
            return FailingFirstLLM(*attempts[0])

        def test_the_run_goes_on_and_tells_the_caller_why_the_chunk_failed(
            self, client, app, house, llm, attempts
        ):
            done = _run_to_end(client, app, house, _long_pages(4))

            reason = attempts[1]
            assert done.status is PipelineRunStatus.COMPLETED, done.failure_reason
            total = done.items_total
            assert total >= 3
            # The failed requests for chunk 1, then two passes for each later chunk
            assert llm.calls == len(attempts[0]) + 2 * (total - 1)
            failed = done.output_summary["failed_chunks"]
            assert [(c["index"], c["failure_reason"]) for c in failed] == [(0, reason)]
            assert done.output_summary["warnings"][0] == (
                f"Extraction failed for 1 of {total} chunks (chunk 1), so what they hold is"
                f" missing. First failure: {reason}"
            )

    class TestRejectedKey:
        @pytest.fixture()
        def llm(self):
            return RefusingLLM()

        def test_the_run_stops_at_its_first_chunk_and_says_why(self, client, app, house, llm):
            done = _run_to_end(client, app, house, _long_pages(4))

            assert done.status is PipelineRunStatus.FAILED
            assert done.items_total >= 3
            # One request in all, not one per chunk
            assert llm.calls == 1
            assert done.failure_reason == (
                f"Extraction stopped at chunk 1 of {done.items_total}, leaving"
                f" {done.items_total - 1} untried, because every later chunk would fail the"
                " same way: OpenRouter API key is invalid or unauthorized"
            )
            assert done.proposal_id is None
            assert done.llm_metadata["tokens_used"] == 0

    class TestRelationshipPassThatNeverCompletes:
        @pytest.fixture()
        def llm(self):
            return NeverRelatingLLM()

        def test_the_failed_run_records_the_tokens_of_every_attempt(self, client, app, house, llm):
            done = _run_to_end(client, app, house, (PAGE_1, PAGE_2))

            assert done.status is PipelineRunStatus.FAILED
            assert done.failure_reason.startswith(
                "Extraction failed for every chunk (1): The LLM response for"
                " derive_relationships was still incomplete after 3 attempts"
            )
            # The identify call and the three derive attempts, 30 tokens each
            assert llm.calls == 4
            assert done.llm_metadata["tokens_used"] == 120
            assert done.llm_metadata["model"]
