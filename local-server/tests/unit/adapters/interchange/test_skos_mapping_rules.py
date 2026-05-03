"""
Unit tests for SKOS adapter mapping rules.

Tests each mapping rule to ensure correct serialization and deserialization:
- Taxonomy ↔ skos:ConceptScheme
- ConceptScheme ↔ skos:ConceptScheme (with dct:isPartOf)
- Class ↔ skos:Concept
- Hierarchy (parent_class_id) ↔ skos:broader/narrower
- Title ↔ skos:prefLabel
- Description ↔ skos:definition
- external_references ↔ dct:source + skos:exactMatch
"""

import sys
import os

sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ),
)

from rdflib import Graph, Namespace, RDF

from domain.ontology.entities import Taxonomy, ConceptScheme, Class
from domain.ontology.value_objects import ExternalReference
from domain.interchange.value_objects import SerializationScope, SerializationScopeType
from adapters.interchange.skos import SKOSSerializer

SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
DCT = Namespace("http://purl.org/dc/terms/")
LOCAL = Namespace("http://context-studio.local/ontology/")


class FakeOntologyRepo:
    """Fake repository for testing serialization."""

    def __init__(self):
        self.taxonomies = {}
        self.schemes = {}
        self.classes = {}

    def get_taxonomy(self, taxonomy_id):
        return self.taxonomies.get(taxonomy_id)

    def list_taxonomies(self):
        return list(self.taxonomies.values())

    def get_concept_scheme(self, scheme_id):
        return self.schemes.get(scheme_id)

    def list_concept_schemes(self, taxonomy_id=None):
        if taxonomy_id is None:
            return list(self.schemes.values())
        return [s for s in self.schemes.values() if s.taxonomy_id == taxonomy_id]

    def get_class(self, class_id):
        return self.classes.get(class_id)

    def list_classes(self, concept_scheme_id=None, **kwargs):
        if concept_scheme_id is None:
            return list(self.classes.values())
        return [
            c for c in self.classes.values() if c.concept_scheme_id == concept_scheme_id
        ]


class TestSKOSTaxonomyMapping:
    """Test Taxonomy ↔ skos:ConceptScheme mapping."""

    def test_export_taxonomy_as_concept_scheme(self):
        """Test that Taxonomy is exported as skos:ConceptScheme."""
        repo = FakeOntologyRepo()
        taxonomy = Taxonomy(
            id="tax-1",
            title="Biology",
            description="Biological classification",
        )
        repo.taxonomies["tax-1"] = taxonomy

        serializer = SKOSSerializer(repo)
        scope = SerializationScope(
            scope_type=SerializationScopeType.TAXONOMY,
            taxonomy_id="tax-1",
        )
        result = serializer.serialize(scope)

        # Parse result and verify structure
        graph = Graph()
        graph.parse(data=result, format="turtle")

        tax_uri = LOCAL["tax-1"]
        assert (tax_uri, RDF.type, SKOS.ConceptScheme) in graph

    def test_export_taxonomy_title_as_pref_label(self):
        """Test that Taxonomy.title maps to skos:prefLabel."""
        repo = FakeOntologyRepo()
        taxonomy = Taxonomy(
            id="tax-1",
            title="Physics",
            description="Study of matter and energy",
        )
        repo.taxonomies["tax-1"] = taxonomy

        serializer = SKOSSerializer(repo)
        scope = SerializationScope(
            scope_type=SerializationScopeType.TAXONOMY,
            taxonomy_id="tax-1",
        )
        result = serializer.serialize(scope)

        graph = Graph()
        graph.parse(data=result, format="turtle")

        tax_uri = LOCAL["tax-1"]
        labels = list(graph.objects(tax_uri, SKOS.prefLabel))
        assert len(labels) == 1
        assert str(labels[0]) == "Physics"

    def test_export_taxonomy_description_as_definition(self):
        """Test that Taxonomy.description maps to skos:definition."""
        repo = FakeOntologyRepo()
        taxonomy = Taxonomy(
            id="tax-1",
            title="Chemistry",
            description="Study of chemical reactions",
        )
        repo.taxonomies["tax-1"] = taxonomy

        serializer = SKOSSerializer(repo)
        scope = SerializationScope(
            scope_type=SerializationScopeType.TAXONOMY,
            taxonomy_id="tax-1",
        )
        result = serializer.serialize(scope)

        graph = Graph()
        graph.parse(data=result, format="turtle")

        tax_uri = LOCAL["tax-1"]
        definitions = list(graph.objects(tax_uri, SKOS.definition))
        assert len(definitions) == 1
        assert str(definitions[0]) == "Study of chemical reactions"


class TestSKOSConceptSchemeMapping:
    """Test ConceptScheme ↔ skos:ConceptScheme mapping."""

    def test_export_concept_scheme_with_parent_taxonomy(self):
        """Test that ConceptScheme with parent Taxonomy uses dct:isPartOf."""
        repo = FakeOntologyRepo()
        taxonomy = Taxonomy(id="tax-1", title="Biology")
        repo.taxonomies["tax-1"] = taxonomy

        scheme = ConceptScheme(
            id="scheme-1",
            taxonomy_id="tax-1",
            title="Organisms",
            description="Living organisms",
        )
        repo.schemes["scheme-1"] = scheme

        serializer = SKOSSerializer(repo)
        scope = SerializationScope(
            scope_type=SerializationScopeType.SCHEME,
            scheme_id="scheme-1",
        )
        result = serializer.serialize(scope)

        graph = Graph()
        graph.parse(data=result, format="turtle")

        scheme_uri = LOCAL["scheme-1"]
        tax_uri = LOCAL["tax-1"]

        assert (scheme_uri, RDF.type, SKOS.ConceptScheme) in graph
        assert (scheme_uri, DCT.isPartOf, tax_uri) in graph


class TestSKOSClassMapping:
    """Test Class ↔ skos:Concept mapping."""

    def test_export_class_as_concept(self):
        """Test that Class is exported as skos:Concept."""
        repo = FakeOntologyRepo()
        class_entity = Class(
            id="class-1",
            concept_scheme_id="scheme-1",
            taxonomy_id="tax-1",
            title="Dog",
            description="A domesticated mammal",
        )
        repo.classes["class-1"] = class_entity

        serializer = SKOSSerializer(repo)
        scope = SerializationScope(
            scope_type=SerializationScopeType.ENTITY_SET,
            entity_ids=("class-1",),
        )
        result = serializer.serialize(scope)

        graph = Graph()
        graph.parse(data=result, format="turtle")

        class_uri = LOCAL["class-1"]
        assert (class_uri, RDF.type, SKOS.Concept) in graph

    def test_export_class_in_scheme(self):
        """Test that Class links to its ConceptScheme via skos:inScheme."""
        repo = FakeOntologyRepo()
        class_entity = Class(
            id="class-1",
            concept_scheme_id="scheme-1",
            taxonomy_id="tax-1",
            title="Cat",
        )
        repo.classes["class-1"] = class_entity

        serializer = SKOSSerializer(repo)
        scope = SerializationScope(
            scope_type=SerializationScopeType.ENTITY_SET,
            entity_ids=("class-1",),
        )
        result = serializer.serialize(scope)

        graph = Graph()
        graph.parse(data=result, format="turtle")

        class_uri = LOCAL["class-1"]
        scheme_uri = LOCAL["scheme-1"]
        assert (class_uri, SKOS.inScheme, scheme_uri) in graph


class TestSKOSHierarchyMapping:
    """Test Class hierarchy (parent_class_id) ↔ skos:broader/narrower."""

    def test_export_class_hierarchy(self):
        """Test that parent_class_id maps to skos:broader."""
        repo = FakeOntologyRepo()
        parent = Class(
            id="parent-1",
            concept_scheme_id="scheme-1",
            taxonomy_id="tax-1",
            title="Animal",
        )
        child = Class(
            id="child-1",
            concept_scheme_id="scheme-1",
            taxonomy_id="tax-1",
            title="Dog",
            parent_class_id="parent-1",
        )
        repo.classes["parent-1"] = parent
        repo.classes["child-1"] = child

        serializer = SKOSSerializer(repo)
        scope = SerializationScope(
            scope_type=SerializationScopeType.ENTITY_SET,
            entity_ids=("parent-1", "child-1"),
        )
        result = serializer.serialize(scope)

        graph = Graph()
        graph.parse(data=result, format="turtle")

        child_uri = LOCAL["child-1"]
        parent_uri = LOCAL["parent-1"]

        assert (child_uri, SKOS.broader, parent_uri) in graph
        assert (parent_uri, SKOS.narrower, child_uri) in graph


class TestSKOSExternalReferenceMapping:
    """Test external_references ↔ dct:source + skos:exactMatch."""

    def test_export_external_references(self):
        """Test that external_references map to dct:source."""
        repo = FakeOntologyRepo()
        class_entity = Class(
            id="class-1",
            concept_scheme_id="scheme-1",
            taxonomy_id="tax-1",
            title="Dog",
            external_references=[
                ExternalReference(
                    source="dbpedia",
                    identifier="Dog",
                    uri="http://dbpedia.org/resource/Dog",
                ),
                ExternalReference(
                    source="wikidata",
                    identifier="Q144",
                    uri="https://www.wikidata.org/wiki/Q144",
                ),
            ],
        )
        repo.classes["class-1"] = class_entity

        serializer = SKOSSerializer(repo)
        scope = SerializationScope(
            scope_type=SerializationScopeType.ENTITY_SET,
            entity_ids=("class-1",),
        )
        result = serializer.serialize(scope)

        graph = Graph()
        graph.parse(data=result, format="turtle")

        class_uri = LOCAL["class-1"]
        sources = list(graph.objects(class_uri, DCT.source))
        assert len(sources) >= 2

    def test_export_exact_match(self):
        """Test that external references also create skos:exactMatch."""
        repo = FakeOntologyRepo()
        class_entity = Class(
            id="class-1",
            concept_scheme_id="scheme-1",
            taxonomy_id="tax-1",
            title="Dog",
            external_references=[
                ExternalReference(
                    source="dbpedia",
                    identifier="Dog",
                    uri="http://dbpedia.org/resource/Dog",
                ),
            ],
        )
        repo.classes["class-1"] = class_entity

        serializer = SKOSSerializer(repo)
        scope = SerializationScope(
            scope_type=SerializationScopeType.ENTITY_SET,
            entity_ids=("class-1",),
        )
        result = serializer.serialize(scope)

        graph = Graph()
        graph.parse(data=result, format="turtle")

        class_uri = LOCAL["class-1"]
        exact_matches = list(graph.objects(class_uri, SKOS.exactMatch))
        assert len(exact_matches) >= 1
