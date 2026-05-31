"""
Unit tests for pipeline schemas, specifically testing extra field preservation.

Tests verify that type-specific fields survive Pydantic's model_dump() method
due to the extra="allow" configuration in PipelineRunRequest.
"""

from adapters.web.schemas.pipelines import (
    IndividualExtractionRunRequest,
    SchemaConnectionRefinementRunRequest,
    SchemaDefinitionRefinementRunRequest,
    SchemaExtractionRunRequest,
    SchemaGroundingRunRequest,
)


class TestPipelineRunRequestExtraFieldPreservation:
    """Test that type-specific fields are preserved through model_dump()."""

    def test_individual_extraction_text_field_survives_model_dump(self) -> None:
        """Test that text field is preserved in model_dump() for IndividualExtractionRunRequest."""
        request = IndividualExtractionRunRequest(
            text="sample text for extraction",
            ontology_id="test_ontology",
            implementation_id="default",
            configuration_ref="default",
        )

        dumped = request.model_dump()

        assert "text" in dumped
        assert dumped["text"] == "sample text for extraction"

    def test_individual_extraction_ontology_id_survives_model_dump(self) -> None:
        """Test that ontology_id field is preserved in model_dump()."""
        request = IndividualExtractionRunRequest(
            text="sample text",
            ontology_id="my_ontology",
            implementation_id="default",
            configuration_ref="default",
        )

        dumped = request.model_dump()

        assert "ontology_id" in dumped
        assert dumped["ontology_id"] == "my_ontology"

    def test_schema_extraction_documents_field_survives_model_dump(self) -> None:
        """Test that documents field is preserved in model_dump() for SchemaExtractionRunRequest."""
        request = SchemaExtractionRunRequest(
            documents=["doc1", "doc2", "doc3"],
            scope="my_scope",
            implementation_id="default",
            configuration_ref="default",
        )

        dumped = request.model_dump()

        assert "documents" in dumped
        assert dumped["documents"] == ["doc1", "doc2", "doc3"]

    def test_schema_extraction_scope_field_survives_model_dump(self) -> None:
        """Test that optional scope field is preserved in model_dump()."""
        request = SchemaExtractionRunRequest(
            documents=["doc1"],
            scope="custom_scope",
            implementation_id="default",
            configuration_ref="default",
        )

        dumped = request.model_dump()

        assert "scope" in dumped
        assert dumped["scope"] == "custom_scope"

    def test_schema_grounding_nodes_field_survives_model_dump(self) -> None:
        """Test that nodes field is preserved in model_dump() for SchemaGroundingRunRequest."""
        nodes = [{"id": "node1", "label": "Node 1"}, {"id": "node2", "label": "Node 2"}]
        request = SchemaGroundingRunRequest(
            nodes=nodes,
            sources=["source1"],
            implementation_id="default",
            configuration_ref="default",
        )

        dumped = request.model_dump()

        assert "nodes" in dumped
        assert dumped["nodes"] == nodes

    def test_schema_grounding_sources_field_survives_model_dump(self) -> None:
        """Test that sources field is preserved in model_dump()."""
        sources = ["dbpedia", "wikidata", "conceptnet"]
        request = SchemaGroundingRunRequest(
            nodes=[{"id": "n1"}],
            sources=sources,
            implementation_id="default",
            configuration_ref="default",
        )

        dumped = request.model_dump()

        assert "sources" in dumped
        assert dumped["sources"] == sources

    def test_schema_definition_refinement_nodes_field_survives_model_dump(self) -> None:
        """Test that nodes field is preserved for SchemaDefinitionRefinementRunRequest."""
        nodes = [{"id": "def_node1"}]
        request = SchemaDefinitionRefinementRunRequest(
            nodes=nodes,
            context=None,
            implementation_id="default",
            configuration_ref="default",
        )

        dumped = request.model_dump()

        assert "nodes" in dumped
        assert dumped["nodes"] == nodes

    def test_schema_connection_refinement_edges_field_survives_model_dump(
        self,
    ) -> None:
        """Test that edges field is preserved for SchemaConnectionRefinementRunRequest."""
        edges = [{"source": "n1", "target": "n2"}]
        request = SchemaConnectionRefinementRunRequest(
            edges=edges,
            strategy=None,
            implementation_id="default",
            configuration_ref="default",
        )

        dumped = request.model_dump()

        assert "edges" in dumped
        assert dumped["edges"] == edges

    def test_base_fields_preserved_in_all_request_types(self) -> None:
        """Test that base request fields are preserved for all types."""
        request = IndividualExtractionRunRequest(
            text="sample",
            ontology_id="test",
            implementation_id="my_impl",
            configuration_ref="my_config",
        )

        dumped = request.model_dump()

        assert dumped["implementation_id"] == "my_impl"
        assert dumped["configuration_ref"] == "my_config"

    def test_field_values_match_after_round_trip(self) -> None:
        """Test that field values are identical after model_dump() round trip."""
        original_text = "extraction text with special chars: éàü"
        original_ontology = "ontology_123"

        request = IndividualExtractionRunRequest(
            text=original_text,
            ontology_id=original_ontology,
        )

        dumped = request.model_dump()

        assert dumped["text"] == original_text
        assert dumped["ontology_id"] == original_ontology

    def test_multiple_type_specific_fields_preserved_together(self) -> None:
        """Test that multiple type-specific fields are all preserved simultaneously."""
        documents = ["doc1", "doc2"]
        scope = "test_scope"

        request = SchemaExtractionRunRequest(
            documents=documents,
            scope=scope,
            implementation_id="default",
            configuration_ref="v1",
        )

        dumped = request.model_dump()

        # Verify all type-specific fields are present
        assert "documents" in dumped
        assert "scope" in dumped
        # Verify base fields are also present
        assert "implementation_id" in dumped
        assert "configuration_ref" in dumped
        # Verify values match
        assert dumped["documents"] == documents
        assert dumped["scope"] == scope
