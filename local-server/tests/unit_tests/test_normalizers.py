"""Unit tests for reference normalizers."""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from datetime import datetime, UTC
from unittest.mock import Mock

from reference_api.normalizers import ResultNormalizer
from reference_api.models import (
    SourceType, DBpediaSearchResponse, DBpediaSearchResult, DBpediaResourceResponse, ConceptNetQueryResponse, ConceptNetConceptResponse, ConceptNetRelatedResponse,
    WikidataSparqlResponse, WikidataEntityResponse,
    SchemaOrgSearchResponse, SchemaOrgSearchResult, SchemaOrgEntityResponse, SchemaOrgEntity,
    SchemaOrgPropertyResponse, SchemaOrgPropertyData
)


class TestResultNormalizer:
    """Test suite for ResultNormalizer class."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for testing."""
        settings = Mock()
        settings.reference_sources.default_language = "en"
        return settings

    @pytest.fixture
    def normalizer(self, mock_settings):
        """Create ResultNormalizer instance for testing."""
        return ResultNormalizer(mock_settings)

    def test_normalize_dbpedia_search_response_success(self, normalizer):
        """Test successful DBpedia search response normalization."""
        # Create test response
        results = [
            DBpediaSearchResult(
                uri="http://dbpedia.org/resource/Python",
                label="Python (programming language)",
                description="High-level programming language",
                score=0.95,
                types=["ProgrammingLanguage", "Language"]
            ),
            DBpediaSearchResult(
                uri="http://dbpedia.org/resource/Python_(snake)",
                label="Python",
                description="Large family of snakes",
                score=0.85,
                types=["Animal", "Reptile"]
            )
        ]

        response = DBpediaSearchResponse(
            success=True,
            source=SourceType.DBPEDIA,
            retrieved_at=datetime.now(UTC),
            query="python",
            total_results=2,
            results=results
        )

        # Normalize
        nodes, links = normalizer.normalize_dbpedia_search_response(response, "python")

        # Verify results
        assert len(nodes) == 2
        assert len(links) == 0  # DBpedia search doesn't provide links

        # Check first node
        assert nodes[0].id == "dbpedia:http://dbpedia.org/resource/Python"
        assert nodes[0].source == SourceType.DBPEDIA
        assert nodes[0].title == "Python (programming language)"
        assert nodes[0].definition == "High-level programming language"
        assert nodes[0].attributes["uri"] == "http://dbpedia.org/resource/Python"
        assert nodes[0].attributes["types"] == ["ProgrammingLanguage", "Language"]
        assert nodes[0].relevance_score == 1.0  # Max score normalized to 1.0

        # Check second node
        assert nodes[1].relevance_score == pytest.approx(0.894, rel=1e-2)  # 0.85/0.95

    def test_normalize_dbpedia_search_response_empty(self, normalizer):
        """Test DBpedia search response with no results."""
        response = DBpediaSearchResponse(
            success=True,
            source=SourceType.DBPEDIA,
            retrieved_at=datetime.now(UTC),
            query="nonexistent",
            total_results=0,
            results=[]
        )

        nodes, links = normalizer.normalize_dbpedia_search_response(response, "nonexistent")

        assert len(nodes) == 0
        assert len(links) == 0

    def test_normalize_dbpedia_search_response_failure(self, normalizer):
        """Test failed DBpedia search response."""
        response = DBpediaSearchResponse(
            success=False,
            source=SourceType.DBPEDIA,
            retrieved_at=datetime.now(UTC),
            error="API error",
            results=[]
        )

        nodes, links = normalizer.normalize_dbpedia_search_response(response, "test")

        assert len(nodes) == 0
        assert len(links) == 0

    def test_normalize_dbpedia_resource_response_success(self, normalizer):
        """Test successful DBpedia resource response normalization."""
        response = DBpediaResourceResponse(
            success=True,
            source=SourceType.DBPEDIA,
            retrieved_at=datetime.now(UTC),
            resource_uri="http://dbpedia.org/resource/Python",
            data_url="http://dbpedia.org/data/Python.json",
            data={
                "http://www.w3.org/2000/01/rdf-schema#label": [
                    {"value": "Python (programming language)"}
                ],
                "http://dbpedia.org/ontology/abstract": [
                    {"value": "Python is a high-level programming language."}
                ]
            }
        )

        nodes, links = normalizer.normalize_dbpedia_resource_response(response, "python")

        assert len(nodes) == 1
        assert len(links) == 0

        node = nodes[0]
        assert node.id == "dbpedia:http://dbpedia.org/resource/Python"
        assert node.source == SourceType.DBPEDIA
        assert node.title == "Python (programming language)"
        assert node.definition == "Python is a high-level programming language."
        assert node.attributes["uri"] == "http://dbpedia.org/resource/Python"
        assert node.attributes["data_url"] == "http://dbpedia.org/data/Python.json"
        assert node.relevance_score == 1.0

    def test_normalize_conceptnet_query_response_success(self, normalizer):
        """Test successful ConceptNet query response normalization."""
        edges = [
            {
                "@id": "/e/test1",
                "start": {"@id": "/c/en/dog", "label": "dog"},
                "rel": {"@id": "/r/IsA", "label": "IsA"},
                "end": {"@id": "/c/en/animal", "label": "animal"},
                "weight": 0.8,
                "sources": []
            },
            {
                "@id": "/e/test2",
                "start": {"@id": "/c/en/dog", "label": "dog"},
                "rel": {"@id": "/r/ExternalURL", "label": "ExternalURL"},
                "end": {"@id": "http://dbpedia.org/resource/Dog"},
                "weight": 1.0,
                "sources": []
            }
        ]

        response = ConceptNetQueryResponse(
            success=True,
            source=SourceType.CONCEPTNET,
            retrieved_at=datetime.now(UTC),
            edges=edges
        )

        nodes, links = normalizer.normalize_conceptnet_query_response(response, "dog")

        # Should have 2 nodes (dog, animal) and 2 links (IsA relation + external URL)
        assert len(nodes) == 2
        assert len(links) == 2

        # Check nodes
        dog_node = next(n for n in nodes if "dog" in n.title)
        assert dog_node.id == "conceptnet:/c/en/dog"
        assert dog_node.source == SourceType.CONCEPTNET
        assert dog_node.title == "dog"
        assert dog_node.attributes["language"] == "en"
        assert dog_node.relevance_score == 0.8

        animal_node = next(n for n in nodes if "animal" in n.title)
        assert animal_node.id == "conceptnet:/c/en/animal"

        # Check links
        isa_link = next(l for l in links if l.predicate == "IsA")
        assert isa_link.source == SourceType.CONCEPTNET
        assert isa_link.subject == "conceptnet:/c/en/dog"
        assert isa_link.object == "conceptnet:/c/en/animal"
        assert isa_link.weight == 0.8

        external_link = next(l for l in links if l.predicate == "externalURL")
        assert external_link.source == SourceType.CONCEPTNET
        assert external_link.subject == "conceptnet:/c/en/dog"
        assert external_link.object == "dbpedia:http://dbpedia.org/resource/Dog"
        assert external_link.attributes["link_type"] == "external_reference"

    def test_normalize_wikidata_sparql_response_success(self, normalizer):
        """Test successful Wikidata SPARQL response normalization."""
        response = WikidataSparqlResponse(
            success=True,
            source=SourceType.WIKIDATA,
            retrieved_at=datetime.now(UTC),
            results={
                "results": {
                    "bindings": [
                        {
                            "item": {"value": "http://www.wikidata.org/entity/Q28865"},
                            "itemLabel": {"value": "Python"},
                            "itemDescription": {"value": "programming language"},
                            "property": {"value": "http://www.wikidata.org/prop/direct/P31"},
                            "propertyLabel": {"value": "instance of"},
                            "object": {"value": "http://www.wikidata.org/entity/Q9143"},
                            "objectLabel": {"value": "programming language"}
                        }
                    ]
                }
            }
        )

        nodes, links = normalizer.normalize_wikidata_sparql_response(response, "python")

        # Should have 2 nodes (Python entity and programming language object) and 1 link
        assert len(nodes) == 2
        assert len(links) == 1

        # Check main entity node
        python_node = next(n for n in nodes if n.title == "Python")
        assert python_node.id == "wikidata:http://www.wikidata.org/entity/Q28865"
        assert python_node.source == SourceType.WIKIDATA
        assert python_node.definition == "programming language"
        assert python_node.relevance_score == 1.0

        # Check object node
        lang_node = next(n for n in nodes if n.title == "programming language")
        assert lang_node.id == "wikidata:http://www.wikidata.org/entity/Q9143"
        assert lang_node.relevance_score == 0.8

        # Check link
        link = links[0]
        assert link.subject == "wikidata:http://www.wikidata.org/entity/Q28865"
        assert link.predicate == "instance of"
        assert link.object == "wikidata:http://www.wikidata.org/entity/Q9143"
        assert link.weight == 1.0

    def test_normalize_schema_org_search_response_success(self, normalizer):
        """Test successful Schema.org search response normalization."""
        results = [
            SchemaOrgSearchResult(
                type="entity",
                identifier="Person",
                title="Person",
                definition="A person (alive, dead, undead, or fictional).",
                relevance_score=0.95
            ),
            SchemaOrgSearchResult(
                type="property",
                identifier="name",
                title="name",
                definition="The name of the item.",
                relevance_score=0.85
            )
        ]

        response = SchemaOrgSearchResponse(
            success=True,
            source=SourceType.SCHEMA_ORG,
            retrieved_at=datetime.now(UTC),
            query="person",
            search_type="both",
            total_results=2,
            results=results
        )

        nodes, links = normalizer.normalize_schema_org_search_response(response, "person")

        assert len(nodes) == 2
        assert len(links) == 0  # Schema.org search doesn't provide relationship data

        # Check Person entity
        person_node = next(n for n in nodes if n.title == "Person")
        assert person_node.id == "schema_org:Person"
        assert person_node.source == SourceType.SCHEMA_ORG
        assert person_node.definition == "A person (alive, dead, undead, or fictional)."
        assert person_node.attributes["type"] == "entity"
        assert person_node.source_url == "https://schema.org/Person"
        assert person_node.relevance_score == 0.95

        # Check name property
        name_node = next(n for n in nodes if n.title == "name")
        assert name_node.id == "schema_org:name"
        assert name_node.attributes["type"] == "property"

    def test_normalize_schema_org_entity_response_success(self, normalizer):
        """Test successful Schema.org entity response normalization."""
        entity = SchemaOrgEntity(
            id="schema_org_Person",
            identifier="Person",
            title="Person",
            definition="A person (alive, dead, undead, or fictional).",
            parent_identifier="Thing",
            properties=[],
            children=[]
        )

        response = SchemaOrgEntityResponse(
            success=True,
            source=SourceType.SCHEMA_ORG,
            retrieved_at=datetime.now(UTC),
            identifier="Person",
            entity=entity
        )

        nodes, links = normalizer.normalize_schema_org_entity_response(response, "Person")

        assert len(nodes) == 1
        assert len(links) == 0

        node = nodes[0]
        assert node.id == "schema_org:Person"
        assert node.source == SourceType.SCHEMA_ORG
        assert node.title == "Person"
        assert node.definition == "A person (alive, dead, undead, or fictional)."
        assert node.attributes["parent_identifier"] == "Thing"
        assert node.relevance_score == 1.0

    def test_normalize_conceptnet_concept_response_success(self, normalizer):
        """Test successful ConceptNet concept response normalization."""
        response = ConceptNetConceptResponse(
            success=True,
            source=SourceType.CONCEPTNET,
            retrieved_at=datetime.now(UTC),
            concept="/c/en/dog",
            data={"label": "dog", "additional_info": "test"}
        )

        nodes, links = normalizer.normalize_conceptnet_concept_response(response, "/c/en/dog")

        assert len(nodes) == 1
        assert len(links) == 0

        node = nodes[0]
        assert node.id == "conceptnet:/c/en/dog"
        assert node.source == SourceType.CONCEPTNET
        assert node.title == "dog"
        assert node.definition is None
        assert node.attributes["concept_uri"] == "/c/en/dog"
        assert node.relevance_score == 1.0

    def test_normalize_conceptnet_related_response_success(self, normalizer):
        """Test successful ConceptNet related concepts response normalization."""
        related_concepts = [
            {"@id": "/c/en/animal", "label": "animal", "weight": 0.8},
            {"@id": "/c/en/pet", "label": "pet", "weight": 0.7}
        ]

        response = ConceptNetRelatedResponse(
            success=True,
            source=SourceType.CONCEPTNET,
            retrieved_at=datetime.now(UTC),
            concept="/c/en/dog",
            related=related_concepts
        )

        nodes, links = normalizer.normalize_conceptnet_related_response(response, "/c/en/dog")

        assert len(nodes) == 2
        assert len(links) == 0

        # Check first related concept
        animal_node = next(n for n in nodes if n.title == "animal")
        assert animal_node.id == "conceptnet:/c/en/animal"
        assert animal_node.relevance_score == 0.8

        # Check second related concept
        pet_node = next(n for n in nodes if n.title == "pet")
        assert pet_node.relevance_score == 0.7

    def test_normalize_wikidata_entity_response_success(self, normalizer):
        """Test successful Wikidata entity response normalization."""
        response = WikidataEntityResponse(
            success=True,
            source=SourceType.WIKIDATA,
            retrieved_at=datetime.now(UTC),
            entity_id="Q28865",
            entity_url="http://www.wikidata.org/entity/Q28865",
            data={
                "labels": {
                    "en": {"value": "Python"}
                },
                "descriptions": {
                    "en": {"value": "programming language"}
                }
            }
        )

        nodes, links = normalizer.normalize_wikidata_entity_response(response, "Q28865")

        assert len(nodes) == 1
        assert len(links) == 0

        node = nodes[0]
        assert node.id == "wikidata:http://www.wikidata.org/entity/Q28865"
        assert node.source == SourceType.WIKIDATA
        assert node.title == "Python"
        assert node.definition == "programming language"
        assert node.attributes["entity_id"] == "Q28865"
        assert node.relevance_score == 1.0

    def test_normalize_schema_org_property_response_success(self, normalizer):
        """Test successful Schema.org property response normalization."""
        property_data = SchemaOrgPropertyData(
            id="schema_org_name",
            identifier="name",
            title="name",
            definition="The name of the item.",
            domain_includes=["Thing"],
            range_includes=["Text"],
            inverse_of=[],
            used_by_entities=[]
        )

        response = SchemaOrgPropertyResponse(
            success=True,
            source=SourceType.SCHEMA_ORG,
            retrieved_at=datetime.now(UTC),
            identifier="name",
            property=property_data
        )

        nodes, links = normalizer.normalize_schema_org_property_response(response, "name")

        assert len(nodes) == 1
        assert len(links) == 0

        node = nodes[0]
        assert node.id == "schema_org:name"
        assert node.source == SourceType.SCHEMA_ORG
        assert node.title == "name"
        assert node.definition == "The name of the item."
        assert node.attributes["domain_includes"] == ["Thing"]
        assert node.attributes["range_includes"] == ["Text"]
        assert node.relevance_score == 1.0

    def test_language_filtering_conceptnet(self, normalizer):
        """Test that ConceptNet normalization filters by configured language."""
        # Test with Spanish concepts when default language is English
        edges = [
            {
                "@id": "/e/test1",
                "start": {"@id": "/c/es/perro", "label": "perro"},  # Spanish
                "rel": {"@id": "/r/IsA", "label": "IsA"},
                "end": {"@id": "/c/es/animal", "label": "animal"},  # Spanish
                "weight": 0.8,
                "sources": []
            },
            {
                "@id": "/e/test2",
                "start": {"@id": "/c/en/dog", "label": "dog"},  # English
                "rel": {"@id": "/r/IsA", "label": "IsA"},
                "end": {"@id": "/c/en/animal", "label": "animal"},  # English
                "weight": 0.8,
                "sources": []
            }
        ]

        response = ConceptNetQueryResponse(
            success=True,
            source=SourceType.CONCEPTNET,
            retrieved_at=datetime.now(UTC),
            edges=edges
        )

        nodes, links = normalizer.normalize_conceptnet_query_response(response, "dog")

        # Should only include English concepts since default_language is "en"
        assert len(nodes) == 2  # dog and animal (both English)
        assert all("/c/en/" in node.attributes["concept_uri"] for node in nodes)

    def test_error_handling_malformed_data(self, normalizer):
        """Test error handling with malformed response data."""
        # Test with missing required fields
        response = WikidataSparqlResponse(
            success=True,
            source=SourceType.WIKIDATA,
            retrieved_at=datetime.now(UTC),
            results={"malformed": "data"}  # Missing expected structure
        )

        nodes, links = normalizer.normalize_wikidata_sparql_response(response, "test")

        # Should handle gracefully and return empty results
        assert len(nodes) == 0
        assert len(links) == 0