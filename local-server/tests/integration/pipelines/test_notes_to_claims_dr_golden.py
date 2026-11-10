"""
Golden test for the notes-to-claims pipeline (#1519) against DR: three of DR's
maintainer notes, split as DR's split-notes.ts split them (claims.jsonl), on the
pinned DR spec.

The notes are DR's own (cli/scripts/spec-enrich/data/proposals/, the notes
behind the committed claims.jsonl snapshot). The fake LLM returns DR's split of
each note with its affected ids written as the Context Studio names the prompt's
context lists (DR spec ids mapped through the DR external references, as the
#1521 importer maps them), so the test pins what the pipeline does with a
split: the keys, the text, and how the names resolve.
"""

import asyncio
from pathlib import Path

import pytest

from adapters.interchange.dr_claims import DrIdResolver, read_jsonl
from adapters.interchange.dr_relationships import DR_TAXONOMY_IDENTIFIER
from adapters.persistence.sqlite.claim_repo import SQLiteClaimRepository
from adapters.persistence.sqlite.connection import create_local_db_engine, create_session_factory
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.pipelines.entities import PipelineType
from domain.pipelines.notes_to_claims import NotesToClaimsOrchestrator, NotesToClaimsState
from domain.pipelines.requested_via import REQUESTED_VIA, RequestedVia
from domain.versioning.claims import ClaimFilter, ClaimService
from scripts.dr_ontology_loader import import_dr_ontology
from scripts.import_dr_model import build_import_service
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_note_splitter import FakeNoteSplitter
from tests.integration.pipelines._harness.dr_spec import MODEL_DR_SPEC_VERSION, dr_spec_dir

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "dr_triage"

# DR's notes, as its split-notes.ts read them: {id, subject (spec node id), text}
DR_NOTES = [
    (
        "node:api.callback",
        "api.callback",
        "The callback's map-key name (e.g. 'onPaymentComplete') has no attribute, and it is"
        " unclear whether one node represents a named callback or a single expression entry."
        " The 'uses api.server' relationship is dubious because callback targets are resolved"
        " at runtime. The layer description mentions webhooks, but no webhook type exists;"
        " webhooks are an OpenAPI 3.1 concept and could be confused with callbacks.",
    ),
    (
        "node:api.components",
        "api.components",
        "The composes→api.paths edge is invalid: an OpenAPI 3.0 Components object has no paths"
        " or pathItems, which exist only in 3.1. components.responses holds Response objects,"
        " not a Responses map, so drop composes→api.responses. api.response appears under both"
        " aggregates and composes; pick one. The oauthflows→components association is spurious,"
        " because flows nest in securityscheme.",
    ),
    (
        "rel:api.callback",
        "api.callback",
        "callback uses server is questionable: a callback's target URL normally comes from the"
        " runtime expression, not a declared server. Any servers override lives on the"
        " callback's PathItem or operation, so this link duplicates a pathitem-to-server"
        " relationship and is better derived transitively through aggregates pathitem.",
    ),
]

# What the pipeline stores, by key: the names of the affected entities (Context
# Studio identifiers) and the names that resolved to nothing in the pinned spec.
EXPECTED = {
    "node:api.callback#1": (["api_callback"], []),
    "node:api.callback#2": (["api_callback", "api_callback.expression"], []),
    "node:api.callback#3": (["callback_uses_server"], []),
    "node:api.callback#4": (["api_callback"], []),
    "node:api.components#1": (["components_composes_paths"], []),
    "node:api.components#2": (["components_composes_responses"], []),
    "node:api.components#3": (
        ["components_aggregates_response", "components_composes_response"],
        [],
    ),
    "node:api.components#4": ([], ["api.oauthflows.associates.api.components"]),
    "rel:api.callback#1": (["callback_uses_server"], []),
    "rel:api.callback#2": (["callback_uses_server", "callback_aggregates_pathitem"], []),
}


@pytest.fixture(scope="module")
def dr(tmp_path_factory):
    """The pinned DR spec in a file SQLite workspace."""
    engine = create_local_db_engine(f"sqlite:///{tmp_path_factory.mktemp('dr_split') / 'local.db'}")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    repo = SQLiteOntologyRepository(session_factory)
    import_dr_ontology(
        build_import_service(session_factory, FakeEmbeddingService()),
        repo,
        dr_spec_dir(MODEL_DR_SPEC_VERSION),
    )
    yield repo, ClaimService(SQLiteClaimRepository(session_factory), repo)
    engine.dispose()


def name_of(repo, entity_id):
    """The Context Studio name the prompt's context gives an entity."""
    if (cls := repo.get_class(entity_id)) is not None:
        return cls.identifier
    if (prop := repo.get_property_definition(entity_id)) is not None:
        return prop.identifier
    attribute = repo.get_attribute_definition(entity_id)
    return f"{repo.get_class(attribute.class_id).identifier}.{attribute.identifier}"


def dr_split_in_context_studio_names(repo, claims):
    """DR's split of each note, its spec ids written as Context Studio names."""
    resolver = DrIdResolver(repo)

    def cs_name(dr_id):
        entity_id = resolver.resolve(dr_id)
        return name_of(repo, entity_id) if entity_id else dr_id

    by_note = {}
    for row in claims:
        by_note.setdefault(row["note_id"], []).append(
            {
                "text": row["text"],
                "category": row["category_hint"],
                "affected_ids": [cs_name(i) for i in row["affected_ids"]],
                "proposed_change": row["proposed_change"],
            }
        )
    return by_note


def test_dr_notes_split_into_dr_claims_with_resolved_entities(dr):
    repo, claims = dr
    note_ids = {note_id for note_id, _, _ in DR_NOTES}
    dr_claims = [c for c in read_jsonl(FIXTURES / "claims.jsonl.xz") if c["note_id"] in note_ids]
    split = dr_split_in_context_studio_names(repo, dr_claims)
    texts = {note_id: text for note_id, _, text in DR_NOTES}
    llm = FakeNoteSplitter({texts[note_id][:60]: rows for note_id, rows in split.items()})
    taxonomy = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
    notes = [
        {"ref": note_id, "subject": subject.replace(".", "_"), "text": text}
        for note_id, subject, text in DR_NOTES
    ]
    state = NotesToClaimsState(
        run_id="run-golden",
        pipeline_type=PipelineType.NOTES_TO_CLAIMS,
        input_data={
            "taxonomy_id": taxonomy.id,
            "scope": {"notes": notes},
            REQUESTED_VIA: RequestedVia.MCP.value,
        },
    )
    orchestrator = NotesToClaimsOrchestrator(llm, repo, claims, run_id="run-golden")

    result = asyncio.run(orchestrator.execute(state)).result

    stored = {c.key: c for c in claims.list_claims(ClaimFilter(taxonomy_id=taxonomy.id))}
    assert sorted(stored) == sorted(c["id"] for c in dr_claims) == sorted(EXPECTED)
    callback = repo.get_by_identifier("api_callback")
    resolver = DrIdResolver(repo)
    for row in dr_claims:
        claim = stored[row["id"]]
        assert claim.text == row["text"]
        assert claim.category_hint == row["category_hint"]
        assert claim.proposed_change == row["proposed_change"]
        assert claim.note_text == texts[row["note_id"]]
        affected, unresolved = EXPECTED[row["id"]]
        assert [name_of(repo, i) for i in claim.affected_ids] == affected, row["id"]
        assert claim.unresolved_refs == unresolved, row["id"]
        # The same entities the #1521 importer finds for DR's own ids
        assert claim.affected_ids == [
            e for e in (resolver.resolve(i) for i in row["affected_ids"]) if e
        ]
    assert stored["node:api.callback#1"].subject_id == callback.id
    assert (result["notes"], result["claims"], result["error_count"]) == (3, 10, 0)

    # The context names what the split names, by Context Studio identifier
    prompt = next(c["user"] for c in llm.calls if "map-key" in c["user"])
    assert prompt.startswith("Note about the class api_callback (scheme api):")
    assert "  - expression" in prompt
    assert "callback_uses_server: api_callback --[uses]--> api_server" in prompt
