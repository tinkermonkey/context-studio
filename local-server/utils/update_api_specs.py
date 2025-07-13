"""
Script to generate and update OpenAPI spec for the FastAPI app.
Saves the spec as documentation/openapi.json.
"""
import os
import sys
import json

# Ensure project root is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

def main():
    """Generate OpenAPI spec and save to documentation/openapi.json."""
    spec = app.openapi()
    doc_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "documentation")
    os.makedirs(doc_dir, exist_ok=True)
    out_path = os.path.join(doc_dir, "openapi.json")
    with open(out_path, "w") as f:
        json.dump(spec, f, indent=2)
    print(f"OpenAPI spec saved to {out_path}")

    # Also copy to ../ux/documentation/openapi.json
    ux_doc_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "../ux/documentation"))
    os.makedirs(ux_doc_dir, exist_ok=True)
    ux_out_path = os.path.join(ux_doc_dir, "openapi.json")
    with open(ux_out_path, "w") as f:
        json.dump(spec, f, indent=2)
    print(f"OpenAPI spec also copied to {ux_out_path}")

if __name__ == "__main__":
    main()
