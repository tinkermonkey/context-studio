#!/usr/bin/env python3
"""
Extract OpenAPI specifications for operations and schemas for data models.
This script extracts relevant parts from openapi.json and creates spec files
that can be used to update the DR model.
"""

import json
import yaml
from pathlib import Path

# Load the OpenAPI specification
openapi_file = Path("local-server/documentation/openapi.json")
with open(openapi_file) as f:
    openapi_spec = json.load(f)

# Output directory for extracted specs
output_dir = Path("openapi_extracts")
output_dir.mkdir(exist_ok=True)

# API operation mappings (operation_id -> path and method)
operation_mappings = {
    "create-structure-node": {"path": "/api/structure_nodes/", "method": "post"},
    "list-structure-nodes": {"path": "/api/structure_nodes/", "method": "get"},
    "get-structure-node": {"path": "/api/structure_nodes/{node_id}", "method": "get"},
    "update-structure-node": {"path": "/api/structure_nodes/{node_id}", "method": "put"},
    "delete-structure-node": {"path": "/api/structure_nodes/{node_id}", "method": "delete"},
    "search-structure-nodes": {"path": "/api/structure_nodes/find", "method": "post"},
    "create-node-link": {"path": "/api/structure_nodes/links", "method": "post"},
    "list-node-links": {"path": "/api/structure_nodes/links", "method": "get"},
    "create-predicate": {"path": "/api/predicates/", "method": "post"},
    "list-predicates": {"path": "/api/predicates/", "method": "get"},
    "find-similar-predicates": {"path": "/api/predicates/{id}/find-similar", "method": "post"},
    "graph-query": {"path": "/api/graph/sparql/query", "method": "post"},
    "graph-stats": {"path": "/api/graph/stats", "method": "get"},
    "rag-extract": {"path": "/api/rag/extract", "method": "post"},
    "rag-get-trace": {"path": "/api/rag/trace/{request_id}", "method": "get"},
    "reference-search": {"path": "/api/reference/search", "method": "get"},
    "create-pipeline-flavor": {"path": "/api/pipeline-flavors", "method": "post"},
    "list-pipeline-flavors": {"path": "/api/pipeline-flavors", "method": "get"},
    "list-datasets": {"path": "/api/datasets", "method": "get"},
    "switch-dataset": {"path": "/api/datasets/{dataset_id}/activate", "method": "post"},
}

# Extract API operation specs
operations_output = output_dir / "operations"
operations_output.mkdir(exist_ok=True)

print("Extracting API operation specs...")
for op_id, mapping in operation_mappings.items():
    path = mapping["path"]
    method = mapping["method"]

    if path in openapi_spec["paths"] and method in openapi_spec["paths"][path]:
        operation_spec = openapi_spec["paths"][path][method]

        # Create a clean spec with just the operation details
        extracted_spec = {
            "operationId": operation_spec.get("operationId", ""),
            "summary": operation_spec.get("summary", ""),
            "description": operation_spec.get("description", ""),
            "parameters": operation_spec.get("parameters", []),
            "requestBody": operation_spec.get("requestBody"),
            "responses": operation_spec.get("responses", {}),
            "tags": operation_spec.get("tags", [])
        }

        # Wrap in full OpenAPI structure with required properties
        # Note: DR validator expects OpenAPI 3.0.x format
        full_spec = {
            "openapi": {
                "openapi": "3.0.3",
                "info": {
                    "title": operation_spec.get("summary", "API"),
                    "version": "1.0.0"
                },
                "paths": {
                    path: {
                        method: extracted_spec
                    }
                }
            }
        }

        # Write to YAML file
        output_file = operations_output / f"{op_id}.yaml"
        with open(output_file, "w") as f:
            yaml.dump(full_spec, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        print(f"  ✓ {op_id} -> {output_file}")
    else:
        print(f"  ✗ {op_id} not found at {method.upper()} {path}")

# Data model schema mappings
schema_mappings = {
    "structure-node": ["NodeOut", "NodeCreate", "NodeUpdate"],
    "structure-node-link": ["NodeLinkOut", "NodeLinkCreate"],
    "predicate": ["PredicateOut", "PredicateCreate"],
    "pipeline-flavor": ["PipelineFlavor", "CreatePipelineFlavorRequest", "UpdatePipelineFlavorRequest"],
    "change-event": ["ChangeEvent"],  # May not exist in OpenAPI
    "external-predicate": ["ExternalPredicateOut", "ExternalPredicateSearchResult"],
    "external-concept": ["ExternalConcept"],  # May not exist in OpenAPI
    "dataset": ["DatasetResponse", "CreateDatasetRequest"],
    "rag-trace": ["RAGExtractionResponse"],
    "rag-metrics": ["RAGMetrics"],  # May not exist in OpenAPI
}

# Extract data model schemas
schemas_output = output_dir / "schemas"
schemas_output.mkdir(exist_ok=True)

print("\nExtracting data model schemas...")
components_schemas = openapi_spec.get("components", {}).get("schemas", {})

for model_id, schema_names in schema_mappings.items():
    extracted_schemas = {}

    for schema_name in schema_names:
        if schema_name in components_schemas:
            extracted_schemas[schema_name] = components_schemas[schema_name]
            print(f"  ✓ {model_id}: {schema_name}")
        else:
            print(f"  ✗ {model_id}: {schema_name} not found")

    if extracted_schemas:
        # Create a combined schema definition with proper JSON Schema structure
        combined_schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "title": f"{model_id} schemas",
            "description": f"Combined schemas for {model_id} data model",
            "definitions": extracted_schemas
        }

        # Write all schemas for this model to a single file
        output_file = schemas_output / f"{model_id}.yaml"
        with open(output_file, "w") as f:
            yaml.dump(combined_schema, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

print(f"\nExtraction complete! Files written to {output_dir}/")
print(f"  Operations: {operations_output}/")
print(f"  Schemas: {schemas_output}/")
