"""
Integration tests (#1461): the DR importer brings in every node attribute as an
attribute definition (datatype, is_required, allowed_values, description),
keyed by the DR attribute name, and a re-import of the same spec changes nothing.

Built on the 0.10.0 spec snapshot: 829 attributes, 251 of them required (its
api.license also lists a required "name" it has no attribute for).
"""

import dataclasses
import json
import os
import shutil
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.ontology.services import OntologyService
from domain.ontology.value_objects import DataType
from scripts.dr_ontology_loader import (
    DR_SOURCE,
    attribute_identifier,
    import_dr_ontology,
    prune_stale,
)
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.integration.pipelines._harness.dr_spec import dr_spec_dir

SPEC_VERSION = "0.10.0"


class _NoOpEventPublisher:
    def publish(self, event):  # noqa: ANN001, ARG002
        return []


def _parts(url):
    engine = create_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    repo = SQLiteOntologyRepository(sessionmaker(bind=engine))
    service = OntologyService(
        repository=repo,
        embedding_service=FakeEmbeddingService(),
        event_publisher=_NoOpEventPublisher(),
        schema_index=None,
    )
    return service, repo


@pytest.fixture(scope="module")
def imported_db(tmp_path_factory):
    """A database with the snapshot imported, built once and copied per test."""
    path = tmp_path_factory.mktemp("attributes") / "spec.db"
    service, repo = _parts(f"sqlite:///{path}")
    import_dr_ontology(service, repo, dr_spec_dir(SPEC_VERSION))
    return path


@pytest.fixture
def parts():
    return _parts("sqlite:///:memory:")


@pytest.fixture
def imported(imported_db, tmp_path):
    """The snapshot, imported."""
    path = tmp_path / "local.db"
    path.write_bytes(imported_db.read_bytes())
    return _parts(f"sqlite:///{path}")


@pytest.fixture
def spec(tmp_path):
    """A writable copy of the 0.10.0 snapshot."""
    copy = tmp_path / "spec"
    shutil.copytree(dr_spec_dir(SPEC_VERSION), copy)
    return copy


def attributes_of(repo):
    return repo.list_attribute_definitions(limit=None)


def by_dr_name(repo, spec_node_id, name):
    cls = next(
        c
        for c in repo.list_classes(limit=None)
        if any(
            r.source == DR_SOURCE and r.identifier == spec_node_id for r in c.external_references
        )
    )
    return next(
        a
        for a in repo.list_attribute_definitions(class_id=cls.id, limit=None)
        if any(r.source == DR_SOURCE and r.identifier == name for r in a.external_references)
    )


def test_every_attribute_is_imported(parts, spec):
    service, repo = parts

    summary = import_dr_ontology(service, repo, spec)

    attributes = attributes_of(repo)
    assert summary.attribute_definitions_created == 829
    assert len(attributes) == 829
    assert sum(a.is_required for a in attributes) == 251
    assert all(any(r.source == DR_SOURCE for r in a.external_references) for a in attributes)


def test_a_reimport_of_the_same_spec_changes_nothing(imported, spec):
    service, repo = imported
    before = {a.id: dataclasses.asdict(a) for a in attributes_of(repo)}

    summary = import_dr_ontology(service, repo, spec)

    assert summary.attribute_definitions_created == 0
    assert summary.stale == []
    assert {a.id: dataclasses.asdict(a) for a in attributes_of(repo)} == before


def test_an_attribute_keeps_its_name_type_enum_and_schema(imported, spec):
    service, repo = imported

    sampler = by_dr_name(repo, "apm.traceconfiguration", "samplerParam")
    assert sampler.identifier == "sampler_param"
    assert sampler.title == "samplerParam"
    assert sampler.datatype is DataType.NUMBER
    (reference,) = sampler.external_references
    assert reference.metadata["schema"] == {"minimum": 0, "maximum": 1}

    enums = [a for a in attributes_of(repo) if a.allowed_values]
    assert enums
    assert all(isinstance(v, str) for a in enums for v in a.allowed_values)


def test_an_untyped_attribute_is_a_string_marked_untyped(imported, spec):
    service, repo = imported

    example = by_dr_name(repo, "api.parameter", "example")

    assert example.datatype is DataType.STRING
    assert example.external_references[0].metadata["schema"] == {"type": None}


def test_a_spec_change_updates_the_attribute_in_place(imported, spec):
    service, repo = imported
    sampler = by_dr_name(repo, "apm.traceconfiguration", "samplerParam")
    path = spec / "schemas" / "nodes" / "apm" / "traceconfiguration.node.schema.json"
    schema = json.loads(path.read_text())
    attributes = schema["properties"]["attributes"]
    attributes["properties"]["samplerParam"]["description"] = "The sampling ratio."
    attributes["properties"]["samplerParam"]["maximum"] = 0.5
    attributes["required"] = [*attributes.get("required", []), "samplerParam"]
    path.write_text(json.dumps(schema))

    summary = import_dr_ontology(service, repo, spec)

    updated = by_dr_name(repo, "apm.traceconfiguration", "samplerParam")
    assert summary.attribute_definitions_created == 0
    assert updated.id == sampler.id
    assert updated.description == "The sampling ratio."
    assert updated.is_required
    assert updated.external_references[0].metadata["schema"] == {"minimum": 0, "maximum": 0.5}


def test_an_attribute_the_spec_dropped_is_stale_and_prunable(imported, spec):
    service, repo = imported
    path = spec / "schemas" / "nodes" / "apm" / "traceconfiguration.node.schema.json"
    schema = json.loads(path.read_text())
    del schema["properties"]["attributes"]["properties"]["samplerParam"]
    path.write_text(json.dumps(schema))

    summary = import_dr_ontology(service, repo, spec)

    assert summary.stale == ["AttributeDefinition 'samplerParam' (samplerParam)"]
    (stale,) = summary.stale_entities
    assert prune_stale(service, summary.stale_entities) == [stale]
    assert repo.get_attribute_definition(stale.id) is None


@pytest.mark.parametrize(
    "name, identifier",
    [
        ("operationId", "operation_id"),
        ("$ref", "ref"),
        ("http_method", "http_method"),
        ("x-source-reference", "x_source_reference"),
        ("URLTemplate", "url_template"),
    ],
)
def test_attribute_identifiers_are_snake_case(name, identifier):
    assert attribute_identifier(name) == identifier
