"""Schema Node Connection Refinement pipeline."""

from domain.pipelines.schema_node_connection_refinement.bootstrap import (
    register_schema_node_connection_refinement,
)

__all__ = ["register_schema_node_connection_refinement"]
