"""
Contract tests verifying request schema fields align with orchestrator expectations.

These tests ensure that Pydantic request schemas define exactly the fields
that orchestrators will read from input_data, preventing silent mismatches
between HTTP contracts and domain orchestrator implementations.
"""

from typing import get_type_hints

from adapters.web.schemas.pipelines import (
    SchemaConnectionRefinementRunRequest,
    SchemaDefinitionRefinementRunRequest,
)


class TestDefinitionRefinementSchemaContract:
    """Verify SchemaDefinitionRefinementRunRequest fields match orchestrator consumption."""

    def test_schema_fields_cover_orchestrator_input_consumption(self):
        """
        Assert that all fields consumed from input_data by DefinitionRefinementOrchestrator
        are present in SchemaDefinitionRefinementRunRequest.
        """
        # Get schema field names
        schema_hints = get_type_hints(SchemaDefinitionRefinementRunRequest)
        schema_fields = set(schema_hints.keys()) - {
            "implementation_id",
            "configuration_ref",
        }

        # Fields read from input_data by the orchestrator
        input_fields = {"node_id", "current_definition", "groundings", "extraction_usages"}

        # Assert that schema contains all input_data fields
        assert input_fields.issubset(schema_fields), (
            f"Schema is missing input fields: {input_fields - schema_fields}"
        )


class TestConnectionRefinementSchemaContract:
    """Verify SchemaConnectionRefinementRunRequest fields match orchestrator consumption."""

    def test_schema_fields_cover_orchestrator_input_consumption(self):
        """
        Assert that all fields consumed from input_data by ConnectionRefinementOrchestrator
        are present in SchemaConnectionRefinementRunRequest.
        """
        # Get schema field names
        schema_hints = get_type_hints(SchemaConnectionRefinementRunRequest)
        schema_fields = set(schema_hints.keys()) - {
            "implementation_id",
            "configuration_ref",
        }

        # Fields read from input_data by the orchestrator
        input_fields = {"scope_id", "current_connections", "groundings", "extraction_usages"}

        # Assert that schema contains all input_data fields
        assert input_fields.issubset(schema_fields), (
            f"Schema is missing input fields: {input_fields - schema_fields}"
        )
