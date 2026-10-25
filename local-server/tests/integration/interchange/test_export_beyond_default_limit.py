"""
Whole-graph exports include every entity, not the repository's default page of 100.

The repository list methods default to ``limit=100``; exporters mean "everything"
and must pass ``limit=None``. Each test seeds more than 100 of the entity kind the
format exports and asserts none are dropped.
"""

import uuid
import xml.etree.ElementTree as ET

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import RDF, SKOS
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.interchange.graphml import GraphMLSerializer
from adapters.interchange.owl import OWLSerializer
from adapters.interchange.skos import SKOSSerializer
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.interchange.value_objects import SerializationScope, SerializationScopeType
from domain.ontology.entities import (
    Class,
    ConceptScheme,
    Individual,
    PropertyDefinition,
    Relationship,
    Taxonomy,
)

INDIVIDUAL_COUNT = 130
CLASS_COUNT = 110
RELATIONSHIP_COUNT = 120
WHOLE_GRAPH = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)


@pytest.fixture
def ontology_repo():
    """SQLite ontology repository on an in-memory database."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return SQLiteOntologyRepository(sessionmaker(bind=engine))


@pytest.fixture
def large_ontology(ontology_repo):
    """One scheme with >100 classes, >100 individuals, and >100 relationships."""
    taxonomy = ontology_repo.save_taxonomy(
        Taxonomy(id=str(uuid.uuid4()), identifier="big_tax", title="Big Taxonomy")
    )
    scheme = ontology_repo.save_concept_scheme(
        ConceptScheme(
            id=str(uuid.uuid4()),
            taxonomy_id=taxonomy.id,
            identifier="big_scheme",
            title="Big Scheme",
        )
    )
    classes = [
        ontology_repo.save_class(
            Class(
                id=str(uuid.uuid4()),
                identifier=f"class_{i:03d}",
                concept_scheme_id=scheme.id,
                taxonomy_id=taxonomy.id,
                title=f"Class {i:03d}",
            )
        )
        for i in range(CLASS_COUNT)
    ]
    individuals = [
        ontology_repo.save_individual(
            Individual(id=str(uuid.uuid4()), class_ids=[classes[0].id], title=f"Ind {i:03d}")
        )
        for i in range(INDIVIDUAL_COUNT)
    ]
    knows = ontology_repo.save_property_definition(
        PropertyDefinition(id=str(uuid.uuid4()), identifier="knows", title="Knows")
    )
    relationships = [
        ontology_repo.save_relationship(
            Relationship(
                id=str(uuid.uuid4()),
                source_id=individuals[i].id,
                target_id=individuals[i + 1].id,
                property_definition_id=knows.id,
            )
        )
        for i in range(RELATIONSHIP_COUNT)
    ]
    return {
        "classes": classes,
        "individuals": individuals,
        "relationships": relationships,
        "knows": knows,
    }


def _titles_in(exported: bytes, prefix: str) -> set[str]:
    text = exported.decode("utf-8")
    return {title for title in (f"{prefix} {i:03d}" for i in range(1000)) if title in text}


class TestOWLExportBeyondDefaultLimit:
    def test_exports_every_individual(self, ontology_repo, large_ontology):
        exported = OWLSerializer(ontology_repo).serialize(WHOLE_GRAPH)

        assert len(_titles_in(exported, "Ind")) == INDIVIDUAL_COUNT

    def test_exports_every_class_and_relationship(self, ontology_repo, large_ontology):
        exported = OWLSerializer(ontology_repo).serialize(WHOLE_GRAPH)

        assert len(_titles_in(exported, "Class")) == CLASS_COUNT
        graph = Graph().parse(data=exported, format="turtle")
        knows_triples = [
            triple
            for triple in graph
            if isinstance(triple[1], URIRef) and str(triple[1]).endswith(large_ontology["knows"].id)
        ]
        assert len(knows_triples) == RELATIONSHIP_COUNT


class TestSKOSExportBeyondDefaultLimit:
    def test_exports_every_class_in_scheme(self, ontology_repo, large_ontology):
        exported = SKOSSerializer(ontology_repo).serialize(WHOLE_GRAPH)

        graph = Graph().parse(data=exported, format="turtle")
        assert len(set(graph.subjects(RDF.type, SKOS.Concept))) >= CLASS_COUNT
        assert len(_titles_in(exported, "Class")) == CLASS_COUNT


class TestGraphMLExportBeyondDefaultLimit:
    def test_exports_every_individual_and_relationship(self, ontology_repo, large_ontology):
        exported = GraphMLSerializer(ontology_repo).serialize(WHOLE_GRAPH)

        assert len(_titles_in(exported, "Ind")) == INDIVIDUAL_COUNT
        assert len(_titles_in(exported, "Class")) == CLASS_COUNT
        root = ET.fromstring(exported)
        edge_ids = {element.get("id") for element in root.iter() if element.tag.endswith("edge")}
        relationship_ids = {rel.id for rel in large_ontology["relationships"]}
        assert relationship_ids <= edge_ids
