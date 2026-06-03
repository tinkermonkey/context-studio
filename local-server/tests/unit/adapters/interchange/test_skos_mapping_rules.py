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

from rdflib import OWL, RDF, Graph, Namespace

from adapters.interchange.skos import SKOSSerializer
from domain.interchange.value_objects import SerializationScope, SerializationScopeType
from domain.ontology.entities import (
    Class,
    ConceptScheme,
    Individual,
    PropertyDefinition,
    Taxonomy,
)
from domain.ontology.value_objects import ExternalReference

SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
DCT = Namespace("http://purl.org/dc/terms/")
LOCAL = Namespace("http://context-studio.local/ontology/")


class FakeOntologyRepo:
    """Fake repository for testing serialization."""

    def __init__(self):
        self.taxonomies = {}
        self.schemes = {}
        self.classes = {}
        self.individuals = {}
        self.properties = {}

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

    def get_individual(self, individual_id):
        return self.individuals.get(individual_id)

    def get_property_definition(self, property_id):
        return self.properties.get(property_id)


class TestSKOSTaxonomyMapping:
    """Test Taxonomy ↔ skos:ConceptScheme mapping."""

    def test_export_taxonomy_as_concept_scheme(self):
        """Test that Taxonomy is exported as skos:ConceptScheme."""
        repo = FakeOntologyRepo()
        taxonomy = Taxonomy(
            id="tax-1",
            identifier="tax_test",
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
            identifier="tax_test",
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
            identifier="tax_test",
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
        taxonomy = Taxonomy(id="tax-1", identifier="tax_test", title="Biology")
        repo.taxonomies["tax-1"] = taxonomy

        scheme = ConceptScheme(
            id="scheme-1",
            taxonomy_id="tax-1",
            identifier="scheme_test",
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
            identifier="cls_test",
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
            identifier="cls_test",
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
            identifier="cls_test",
            title="Animal",
        )
        child = Class(
            id="child-1",
            concept_scheme_id="scheme-1",
            taxonomy_id="tax-1",
            identifier="cls_test",
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
            identifier="cls_test",
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
            identifier="cls_test",
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


class TestSKOSIndividualMapping:
    """Test Individual serialization in entity_set scope."""

    def test_export_individual_as_named_individual(self):
        """Test that Individual is exported as owl:NamedIndividual."""
        repo = FakeOntologyRepo()
        individual = Individual(
            id="ind-1",
            title="Fido",
            description="A specific dog",
            class_ids=["class-1"],
        )
        repo.individuals["ind-1"] = individual

        serializer = SKOSSerializer(repo)
        scope = SerializationScope(
            scope_type=SerializationScopeType.ENTITY_SET,
            entity_ids=("ind-1",),
        )
        result = serializer.serialize(scope)

        graph = Graph()
        graph.parse(data=result, format="turtle")

        ind_uri = LOCAL["ind-1"]
        assert (ind_uri, RDF.type, OWL.NamedIndividual) in graph

    def test_export_individual_title_as_pref_label(self):
        """Test that Individual.title maps to skos:prefLabel."""
        repo = FakeOntologyRepo()
        individual = Individual(
            id="ind-1",
            title="Fido",
            class_ids=["class-1"],
        )
        repo.individuals["ind-1"] = individual

        serializer = SKOSSerializer(repo)
        scope = SerializationScope(
            scope_type=SerializationScopeType.ENTITY_SET,
            entity_ids=("ind-1",),
        )
        result = serializer.serialize(scope)

        graph = Graph()
        graph.parse(data=result, format="turtle")

        ind_uri = LOCAL["ind-1"]
        labels = list(graph.objects(ind_uri, SKOS.prefLabel))
        assert len(labels) == 1
        assert str(labels[0]) == "Fido"

    def test_export_individual_with_class_membership(self):
        """Test that Individual class memberships are exported as rdf:type."""
        repo = FakeOntologyRepo()
        individual = Individual(
            id="ind-1",
            title="Fido",
            class_ids=["class-1", "class-2"],
        )
        repo.individuals["ind-1"] = individual

        serializer = SKOSSerializer(repo)
        scope = SerializationScope(
            scope_type=SerializationScopeType.ENTITY_SET,
            entity_ids=("ind-1",),
        )
        result = serializer.serialize(scope)

        graph = Graph()
        graph.parse(data=result, format="turtle")

        ind_uri = LOCAL["ind-1"]
        class_uri_1 = LOCAL["class-1"]
        class_uri_2 = LOCAL["class-2"]
        assert (ind_uri, RDF.type, class_uri_1) in graph
        assert (ind_uri, RDF.type, class_uri_2) in graph


class TestSKOSPropertyMapping:
    """Test PropertyDefinition serialization in entity_set scope."""

    def test_export_property_as_object_property(self):
        """Test that PropertyDefinition is exported as owl:ObjectProperty."""
        repo = FakeOntologyRepo()
        prop = PropertyDefinition(
            id="prop-1",
            identifier="has_part",
            title="hasPart",
            description="Indicates a part-whole relationship",
        )
        repo.properties["prop-1"] = prop

        serializer = SKOSSerializer(repo)
        scope = SerializationScope(
            scope_type=SerializationScopeType.ENTITY_SET,
            entity_ids=("prop-1",),
        )
        result = serializer.serialize(scope)

        graph = Graph()
        graph.parse(data=result, format="turtle")

        prop_uri = LOCAL["prop-1"]
        assert (prop_uri, RDF.type, OWL.ObjectProperty) in graph

    def test_export_property_title_as_pref_label(self):
        """Test that PropertyDefinition.title maps to skos:prefLabel."""
        repo = FakeOntologyRepo()
        prop = PropertyDefinition(
            id="prop-1",
            identifier="has_part",
            title="hasPart",
        )
        repo.properties["prop-1"] = prop

        serializer = SKOSSerializer(repo)
        scope = SerializationScope(
            scope_type=SerializationScopeType.ENTITY_SET,
            entity_ids=("prop-1",),
        )
        result = serializer.serialize(scope)

        graph = Graph()
        graph.parse(data=result, format="turtle")

        prop_uri = LOCAL["prop-1"]
        labels = list(graph.objects(prop_uri, SKOS.prefLabel))
        assert len(labels) == 1
        assert str(labels[0]) == "hasPart"
