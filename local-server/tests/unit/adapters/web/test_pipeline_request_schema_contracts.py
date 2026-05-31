"""
Contract tests verifying request schema fields align with orchestrator expectations.

These tests ensure that Pydantic request schemas define exactly the fields
that orchestrators will read from input_data, preventing silent mismatches
between HTTP contracts and domain orchestrator implementations.
"""

import inspect
from typing import get_type_hints

from adapters.web.schemas.pipelines import (
    SchemaConnectionRefinementRunRequest,
    SchemaDefinitionRefinementRunRequest,
)
from domain.pipelines.schema_node_connection_refinement.orchestrator import (
    ConnectionRefinementOrchestrator,
)
from domain.pipelines.schema_node_definition_refinement.orchestrator import (
    DefinitionRefinementOrchestrator,
)


class TestDefinitionRefinementSchemaContract:
    """Verify SchemaDefinitionRefinementRunRequest fields match orchestrator consumption."""

    def test_schema_fields_cover_orchestrator_input_consumption(self):
        """
        Assert that all fields read by DefinitionRefinementOrchestrator.execute()
        are present in SchemaDefinitionRefinementRunRequest.
        """
        # Get schema field names
        schema_hints = get_type_hints(SchemaDefinitionRefinementRunRequest)
        schema_fields = set(schema_hints.keys()) - {
            "implementation_id",
            "configuration_ref",
        }

        # Get the execute() method to inspect what it reads
        execute_source = inspect.getsource(DefinitionRefinementOrchestrator.execute)

        # Verify critical fields are in schema and are read by orchestrator
        required_fields = {"node_id", "current_definition"}
        optional_fields = {"groundings", "extraction_usages"}

        for field in required_fields:
            assert field in schema_fields, (
                f"Required field '{field}' missing from "
                f"SchemaDefinitionRefinementRunRequest"
            )
            assert f'"{field}"' in execute_source or f"'{field}'" in execute_source, (
                f"Field '{field}' not read by DefinitionRefinementOrchestrator.execute()"
            )

        for field in optional_fields:
            assert f'"{field}"' in execute_source or f"'{field}'" in execute_source, (
                f"Optional field '{field}' should be read by "
                f"DefinitionRefinementOrchestrator.execute()"
            )


class TestConnectionRefinementSchemaContract:
    """Verify SchemaConnectionRefinementRunRequest fields match orchestrator consumption."""

    def test_schema_fields_cover_orchestrator_input_consumption(self):
        """
        Assert that all fields read by ConnectionRefinementOrchestrator.execute()
        are present in SchemaConnectionRefinementRunRequest.
        """
        # Get schema field names
        schema_hints = get_type_hints(SchemaConnectionRefinementRunRequest)
        schema_fields = set(schema_hints.keys()) - {
            "implementation_id",
            "configuration_ref",
        }

        # Get the execute() method to inspect what it reads
        execute_source = inspect.getsource(ConnectionRefinementOrchestrator.execute)

        # Verify critical fields are in schema and are read by orchestrator
        required_fields = {"scope_id", "current_connections"}
        optional_fields = {"groundings", "extraction_usages"}

        for field in required_fields:
            assert field in schema_fields, (
                f"Required field '{field}' missing from "
                f"SchemaConnectionRefinementRunRequest"
            )
            assert f'"{field}"' in execute_source or f"'{field}'" in execute_source, (
                f"Field '{field}' not read by ConnectionRefinementOrchestrator.execute()"
            )

        for field in optional_fields:
            assert f'"{field}"' in execute_source or f"'{field}'" in execute_source, (
                f"Optional field '{field}' should be read by "
                f"ConnectionRefinementOrchestrator.execute()"
            )
