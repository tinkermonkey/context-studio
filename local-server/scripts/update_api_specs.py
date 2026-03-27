"""
Update API specifications and generate front-end types.

This script generates OpenAPI specs from the FastAPI application
and can be extended to generate TypeScript types for the front-end.
"""

import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app


def main():
    """Generate OpenAPI spec from FastAPI application"""
    try:
        # Get the OpenAPI schema from the FastAPI app
        openapi_schema = app.openapi()

        # Define output path
        output_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "documentation",
            "openapi.json"
        )

        # Write the schema to file
        with open(output_path, "w") as f:
            json.dump(openapi_schema, f, indent=2)

        # Count endpoints for verification
        paths = openapi_schema.get("paths", {})
        endpoint_count = sum(len(methods) for methods in paths.values())

        print(f"✓ OpenAPI spec generated: {output_path}")
        print(f"  Total endpoints: {endpoint_count}")
        print(f"  Paths: {list(paths.keys())}")

        return 0
    except Exception as e:
        print(f"✗ Error generating OpenAPI spec: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
