"""
Integration tests for the DR spec drift re-import (#1464) over real SQLite and
the 0.10.0 DR spec snapshot: a dry run reports hand edits and stores nothing;
the real run proposes them; once the proposal is applied, a second dry run
reports no drift. Moves are followed by DR id, whether or not Context Studio
already made the move.
"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from adapters.chat.proposal_tools import DrSpecDriftTool
from adapters.events.in_process import InProcessEventPublisher
from adapters.interchange.dr_drift import DrDriftPlanner
from adapters.interchange.dr_predicates import DrPredicateRules
from adapters.interchange.dr_relationships import (
    DR_SOURCE,
    DR_TAXONOMY_IDENTIFIER,
    DrRelationshipRules,
    dr_predicate_catalog,
    dr_property_definitions,
)
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.connection import create_local_db_engine
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.proposal_repo import SQLiteChangeProposalRepository
from adapters.web.drift_routes import router as drift_router
from domain.ontology.services import OntologyService
from domain.versioning.drift import DriftError, DriftImportService
from domain.versioning.proposal_service import ProposalService
from domain.versioning.proposals import OperationStatus, ProposalSource, ProposalStatus
from domain.versioning.revert_service import RevertService
from scripts.dr_ontology_loader import import_dr_ontology
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.integration.pipelines._harness.dr_spec import MODEL_DR_SPEC_VERSION, dr_spec_dir
from tests.utils.change_recording import wire_change_recorder


@pytest.fixture(scope="module")
def spec_db():
    """The 0.10.0 spec imported once; each test copies the database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "spec.db"
        engine = create_local_db_engine(f"sqlite:///{path}")
        Base.metadata.create_all(engine)
        repo = SQLiteOntologyRepository(session_factory=sessionmaker(bind=engine))
        service = OntologyService(repo, FakeEmbeddingService(), InProcessEventPublisher())
        import_dr_ontology(service, repo, dr_spec_dir(MODEL_DR_SPEC_VERSION))
        engine.dispose()
        yield path


@pytest.fixture()
def spec(tmp_path):
    """A copy of the 0.10.0 spec to hand-edit."""
    copy = tmp_path / "spec"
    shutil.copytree(dr_spec_dir(MODEL_DR_SPEC_VERSION), copy)
    return copy


@pytest.fixture()
def world(spec_db, tmp_path):
    db = tmp_path / "local.db"
    db.write_bytes(spec_db.read_bytes())
    engine = create_local_db_engine(f"sqlite:///{db}")
    session_factory = sessionmaker(bind=engine)
    repo = SQLiteOntologyRepository(session_factory=session_factory)
    change_repo = SQLiteChangeRepository(session_factory=session_factory)
    publisher = InProcessEventPublisher()
    wire_change_recorder(publisher, change_repo)
    ontology = OntologyService(repo, FakeEmbeddingService(), publisher)
    proposals = ProposalService(
        SQLiteChangeProposalRepository(session_factory),
        ontology,
        repo,
        RevertService(change_repo=change_repo, ontology_repo=repo),
        apply_rules=[DrRelationshipRules(repo), DrPredicateRules(repo)],  # as app.py wires it
    )
    drift = DriftImportService(proposals, ontology, DrDriftPlanner(repo))

    class World:
        pass

    w = World()
    w.repo, w.ontology, w.proposals, w.drift = repo, ontology, proposals, drift
    yield w
    engine.dispose()


# ------------------------------------------------------------ spec editing


def _node_file(spec, node_id):
    layer, type_name = node_id.split(".", 1)
    return spec / "schemas" / "nodes" / layer / f"{type_name}.node.schema.json"


def _edit_node(spec, node_id, change):
    path = _node_file(spec, node_id)
    data = json.loads(path.read_text())
    change(data)
    path.write_text(json.dumps(data))


def _relationship_files(spec):
    return sorted((spec / "schemas" / "relationships").glob("*/*.relationship.schema.json"))


def _move_node(spec, node_id, layer):
    """Move a node type to another layer, as DR does when it lands a move."""
    old_layer, type_name = node_id.split(".", 1)
    new_id = f"{layer}.{type_name}"
    path = _node_file(spec, node_id)
    data = json.loads(path.read_text())
    data["properties"]["spec_node_id"]["const"] = new_id
    data["properties"]["layer_id"]["const"] = layer
    path.unlink()
    target = _node_file(spec, new_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data))
    for rel in _relationship_files(spec):
        data = json.loads(rel.read_text())
        props = data["properties"]
        touched = False
        for end in ("source", "destination"):
            if props[f"{end}_spec_node_id"]["const"] == node_id:
                props[f"{end}_spec_node_id"]["const"] = new_id
                props[f"{end}_layer"]["const"] = layer
                touched = True
        if touched:
            props.pop("id", None)
            rel.write_text(json.dumps(data))
    return new_id


def _delete_node(spec, node_id):
    _node_file(spec, node_id).unlink()
    for rel in _relationship_files(spec):
        props = json.loads(rel.read_text())["properties"]
        if node_id in (
            props["source_spec_node_id"]["const"],
            props["destination_spec_node_id"]["const"],
        ):
            rel.unlink()


def _add_relationship(spec, source, predicate, destination, cardinality="one-to-many"):
    path = spec / "schemas" / "relationships" / source.split(".")[0]
    path = (
        path
        / f"{source.split('.')[1]}.{predicate}.{destination.split('.')[1]}.relationship.schema.json"
    )
    path.write_text(
        json.dumps(
            {
                "title": f"{source} {predicate} {destination}",
                "description": f"Defines relationship: {source} {predicate} {destination}",
                "properties": {
                    "source_spec_node_id": {"const": source},
                    "source_layer": {"const": source.split(".")[0]},
                    "destination_spec_node_id": {"const": destination},
                    "destination_layer": {"const": destination.split(".")[0]},
                    "predicate": {"const": predicate},
                    "cardinality": {"const": cardinality},
                },
            }
        )
    )
    return f"{source}.{predicate}.{destination}"


def _set_relationship(spec, rel_id, key, value):
    for rel in _relationship_files(spec):
        data = json.loads(rel.read_text())
        props = data["properties"]
        full = (
            f"{props['source_spec_node_id']['const']}.{props['predicate']['const']}"
            f".{props['destination_spec_node_id']['const']}"
        )
        if full == rel_id:
            props[key] = {"const": value}
            rel.write_text(json.dumps(data))
            return
    raise AssertionError(f"No relationship {rel_id}")


def _class(repo, node_id):
    for scheme in repo.list_concept_schemes(limit=None):
        for cls in repo.list_classes(concept_scheme_id=scheme.id, limit=None):
            if any(
                r.source == DR_SOURCE and r.identifier == node_id for r in cls.external_references
            ):
                return cls
    return None


def _property(repo, relationship_id):
    return dr_property_definitions(repo).get(relationship_id)


def _apply_all(world, proposal):
    applied = world.proposals.apply(proposal.id, [o.id for o in proposal.operations])
    failed = {
        o.seq: o.reason for o in applied.operations if o.status is not OperationStatus.APPLIED
    }
    assert failed == {}
    return applied


def _changes(plan):
    return {(e.kind, e.source_id, e.change) for e in plan.entries}


# ------------------------------------------------------------------ tests


def test_an_unchanged_spec_reports_no_drift(world, spec):
    result = world.drift.reimport(str(spec))
    assert result.plan.entries == []
    assert result.proposal is None


def test_hand_edits_are_reported_proposed_and_cleared_once_applied(world, spec):
    _edit_node(spec, "api.contact", lambda d: d.update(description="Who to contact about the API."))
    _edit_node(
        spec,
        "business.product",
        lambda d: d["properties"]["attributes"]["properties"].update(
            documentation={"type": "string", "description": "Notes", "maxLength": 200},
            launched={"type": "boolean"},
        ),
    )
    _set_relationship(
        spec, "business.product.composes.business.contract", "cardinality", "one-to-many"
    )
    new_rel = _add_relationship(spec, "business.product", "serves", "business.businessactor")
    _delete_node(spec, "api.license")

    dry = world.drift.reimport(str(spec))

    assert world.proposals.count_proposals() == 0  # a dry run stores nothing
    assert dry.dry_run and dry.proposal is not None and dry.proposal.operations
    assert {
        ("class", "api.contact", "update"),
        ("attribute", "business.product#documentation", "update"),
        ("attribute", "business.product#launched", "create"),
        ("property", "business.product.composes.business.contract", "update"),
        ("property", new_rel, "create"),
        ("class", "api.license", "delete"),
    } <= _changes(dry.plan)
    contact = next(e for e in dry.plan.entries if e.source_id == "api.contact")
    assert contact.fields["description"]["source"] == "Who to contact about the API."

    real = world.drift.reimport(str(spec), dry_run=False)

    proposal = real.proposal
    assert proposal.source is ProposalSource.BUNDLE
    assert proposal.source_detail == "bundle:dr_spec"
    assert proposal.source_revision.spec_version == MODEL_DR_SPEC_VERSION
    assert all(o.status is OperationStatus.PENDING for o in proposal.operations)
    _apply_all(world, proposal)

    assert world.drift.reimport(str(spec)).plan.entries == []
    assert _class(world.repo, "api.license") is None
    product = _class(world.repo, "business.product")
    attributes = {
        a.title: a for a in world.repo.list_attribute_definitions(class_id=product.id, limit=None)
    }
    assert attributes["launched"].datatype.value == "boolean"


def _write_catalog(spec, catalog):
    (spec / "dist" / "base.json").write_text(json.dumps({"predicates": catalog}))


SEMANTICS = {
    "directionality": "unidirectional",
    "transitivity": False,
    "symmetry": False,
    "reflexivity": False,
}


def _synced_catalog(world, spec, *extra):
    """Give the spec a full catalog of the taxonomy's predicates (plus extra), synced in."""
    names = {*dr_predicate_catalog(world.repo), *extra}
    catalog = {
        name: {
            "inverse": f"{name}-by",
            "category": "structural",
            "description": f"{name} relation",
            "semantics": SEMANTICS,
        }
        for name in names
    }
    _write_catalog(spec, catalog)
    _apply_all(world, world.drift.reimport(str(spec), dry_run=False).proposal)
    assert world.drift.reimport(str(spec)).plan.entries == []
    return catalog


def test_predicate_catalog_drift_is_proposed_and_cleared_once_applied(world, spec):
    """#1481: a new predicate is a create, a changed DR field an update."""
    catalog = _synced_catalog(world, spec)
    serves = next(iter(sorted(catalog)))
    catalog[serves] = {**catalog[serves], "category": "behavioral"}
    catalog["guards"] = {
        "inverse": "guarded-by",
        "category": "security",
        "description": "Protects another element",
        "semantics": SEMANTICS,
    }
    _write_catalog(spec, catalog)
    _add_relationship(spec, "business.product", "guards", "business.businessactor")
    new_rel = "business.product.guards.business.businessactor"

    dry = world.drift.reimport(str(spec))

    predicates = {(e.source_id, e.change) for e in dry.plan.entries if e.kind == "predicate"}
    assert predicates == {("guards", "create"), (serves, "update")}
    kinds = [o.kind.value for o in dry.plan.operations]
    assert kinds.index("predicate") < kinds.index("property")
    real = world.drift.reimport(str(spec), dry_run=False)
    _apply_all(world, real.proposal)

    taxonomy = world.repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
    guards = world.repo.get_predicate_by_identifier(taxonomy.id, "guards")
    assert guards.description == "Protects another element"
    assert dr_predicate_catalog(world.repo)[serves]["category"] == "behavioral"
    assert _property(world.repo, new_rel).canonical_predicate == "guards"
    assert world.drift.reimport(str(spec)).plan.entries == []


def test_a_predicate_the_spec_drops_is_deleted_after_its_types(world, spec):
    catalog = _synced_catalog(world, spec, "obsolete")
    taxonomy = world.repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
    unused = "obsolete"
    assert world.repo.get_predicate_by_identifier(taxonomy.id, unused) is not None
    del catalog[unused]
    _write_catalog(spec, catalog)

    real = world.drift.reimport(str(spec), dry_run=False)
    _apply_all(world, real.proposal)

    assert world.repo.get_predicate_by_identifier(taxonomy.id, unused) is None


def test_a_relationship_type_on_a_predicate_the_catalog_lacks_stops_the_drift(world, spec):
    _synced_catalog(world, spec)
    _add_relationship(spec, "business.product", "guards", "business.businessactor")

    with pytest.raises(DriftError, match="guards"):
        world.drift.reimport(str(spec))


def test_a_move_dr_landed_moves_the_class_and_its_relationship_types(world, spec):
    product = _class(world.repo, "business.product")
    new_id = _move_node(spec, "business.product", "application")

    plan = world.drift.reimport(str(spec)).plan

    entry = next(e for e in plan.entries if e.kind == "class")
    assert (entry.source_id, entry.change, entry.entity_id) == (new_id, "move", product.id)
    assert ("property", "application.product.composes.business.contract", "update") in _changes(
        plan
    )
    assert not any(e.change in ("create", "delete") for e in plan.entries)

    _apply_all(world, world.drift.reimport(str(spec), dry_run=False).proposal)

    moved = world.repo.get_class(product.id)
    application = world.repo.get_by_identifier("application")
    assert moved.concept_scheme_id == application.id
    assert _class(world.repo, new_id).id == product.id
    assert world.drift.reimport(str(spec)).plan.entries == []


def test_a_move_made_in_context_studio_and_landed_only_swaps_the_dr_ids(world, spec):
    product = _class(world.repo, "business.product")
    application = world.repo.get_by_identifier("application")
    world.ontology.move_class_to_scheme(product.id, application.id)
    new_id = _move_node(spec, "business.product", "application")

    plan = world.drift.reimport(str(spec)).plan

    entry = next(e for e in plan.entries if e.kind == "class")
    assert entry.change == "move"
    assert "concept_scheme_id" not in entry.fields
    assert entry.fields["external_references"] == {"taxonomy": "business.product", "source": new_id}
    _apply_all(world, world.drift.reimport(str(spec), dry_run=False).proposal)
    assert world.drift.reimport(str(spec)).plan.entries == []


def test_a_new_run_supersedes_the_open_proposal_of_an_earlier_one(world, spec):
    _edit_node(spec, "api.contact", lambda d: d.update(description="First"))
    first = world.drift.reimport(str(spec), dry_run=False).proposal
    _edit_node(spec, "api.contact", lambda d: d.update(description="Second"))

    second = world.drift.reimport(str(spec), dry_run=False).proposal

    assert world.proposals.get(first.id).status is ProposalStatus.DONE
    assert all(
        o.status is OperationStatus.REJECTED for o in world.proposals.get(first.id).operations
    )
    assert second.operations[0].fields["description"] == "Second"


def test_no_drift_records_the_spec_revision_on_the_taxonomy(world, spec):
    taxonomy = world.repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
    world.ontology.set_taxonomy_source_revision(taxonomy.id, None)

    world.drift.reimport(str(spec), dry_run=False)

    revision = world.repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER).source_revision
    assert revision.spec_version == MODEL_DR_SPEC_VERSION


def test_a_directory_that_isnt_a_spec_is_refused(world, tmp_path):
    with pytest.raises(DriftError, match="not a DR spec directory"):
        world.drift.reimport(str(tmp_path))


# ------------------------------------------------------------ REST and MCP


@pytest.fixture()
def client(world):
    app = FastAPI()
    app.include_router(drift_router)
    app.state.drift_import_service = world.drift
    app.state.proposal_service = world.proposals
    return TestClient(app)


def test_rest_dry_run_reports_and_the_real_run_proposes(client, world, spec):
    _edit_node(spec, "api.contact", lambda d: d.update(description="Who to contact."))

    dry = client.post("/api/v1/interchange/dr-spec/drift", json={"spec_dir": str(spec)})

    assert dry.status_code == 200, dry.text
    body = dry.json()
    assert body["dry_run"] is True
    assert body["source_revision"]["spec_version"] == MODEL_DR_SPEC_VERSION
    (entry,) = body["entries"]
    assert (entry["kind"], entry["source_id"], entry["change"]) == (
        "class",
        "api.contact",
        "update",
    )
    assert entry["fields"]["description"]["source"] == "Who to contact."
    assert body["proposal"]["dry_run"] is True
    assert world.proposals.count_proposals() == 0

    real = client.post(
        "/api/v1/interchange/dr-spec/drift", json={"spec_dir": str(spec), "dry_run": False}
    ).json()

    assert real["proposal"]["source"] == "bundle"
    assert real["proposal"]["status"] == "open"
    assert world.proposals.count_proposals() == 1


def test_rest_refuses_a_directory_that_isnt_a_spec(client, tmp_path):
    response = client.post(
        "/api/v1/interchange/dr-spec/drift", json={"spec_dir": str(tmp_path / "nowhere")}
    )
    assert response.status_code == 422
    assert "not a DR spec directory" in response.json()["detail"]


async def test_mcp_tool_reports_by_default_and_proposes_on_request(world, spec):
    _edit_node(spec, "api.contact", lambda d: d.update(description="Who to contact."))
    tool = DrSpecDriftTool(world.drift)

    dry = await tool.execute({"spec_dir": str(spec)})
    real = await tool.execute({"spec_dir": str(spec), "dry_run": False})
    missing = await tool.execute({"spec_dir": "/nowhere"})

    report = json.loads(dry.content)
    assert report["dry_run"] is True and report["total"] == 1
    assert report["entries"][0]["source_id"] == "api.contact"
    assert "proposal" not in report and report["operations"] == 1
    proposed = json.loads(real.content)
    assert proposed["proposal"]["status"] == "open"
    assert real.entities[0].id == proposed["proposal"]["id"]
    assert world.proposals.count_proposals() == 1
    assert missing.is_error
