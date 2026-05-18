"""
Update API specifications and generate front-end types.

This script generates OpenAPI specs from the FastAPI application
and copies it to both the back-end and front-end documentation directories.
"""

import json
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app


def main():
    """Generate OpenAPI spec from FastAPI application and copy to both back-end and UX."""
    try:
        # Get the OpenAPI schema from the FastAPI app
        spec = app.openapi()

        # Define back-end output path
        backend_doc_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "documentation"
        )
        os.makedirs(backend_doc_dir, exist_ok=True)
        backend_output_path = os.path.join(backend_doc_dir, "openapi.json")

        # Write to back-end documentation directory
        with open(backend_output_path, "w") as f:
            json.dump(spec, f, indent=2)
            f.write("\n")

        print(f"✓ OpenAPI spec generated: {backend_output_path}")

        # Copy to UX documentation directory
        ux_doc_dir = os.path.abspath(
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "../ux/documentation",
            )
        )
        os.makedirs(ux_doc_dir, exist_ok=True)
        ux_output_path = os.path.join(ux_doc_dir, "openapi.json")

        with open(ux_output_path, "w") as f:
            json.dump(spec, f, indent=2)
            f.write("\n")

        print(f"✓ OpenAPI spec also copied to: {ux_output_path}")

        # Count endpoints for verification
        paths = spec.get("paths", {})
        endpoint_count = sum(len(methods) for methods in paths.values())
        print(f"  Total endpoints: {endpoint_count}")

        return 0
    except Exception as e:
        print(f"✗ Error generating OpenAPI spec: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
