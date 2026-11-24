"""
Update API specifications.

Generates the OpenAPI spec from the FastAPI application and writes it to both the
back-end and the front-end documentation directories.

With --check nothing is written: the generated spec is compared with the committed
files, the stale ones are named, and the exit code is 1 if any differs.
"""

import argparse
import json
import os
import sys
from typing import Optional, Sequence

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LOCAL_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC_PATHS = (
    os.path.join(LOCAL_SERVER_DIR, "documentation", "openapi.json"),
    os.path.abspath(os.path.join(LOCAL_SERVER_DIR, "..", "ux", "documentation", "openapi.json")),
)


def generate_spec() -> dict:
    """Return the OpenAPI schema of the FastAPI application."""
    from app import app

    return app.openapi()


def render_spec(spec: dict) -> str:
    """Serialize a spec exactly as it is committed."""
    return json.dumps(spec, indent=2) + "\n"


def stale_spec_paths(spec: dict, paths: Sequence[str]) -> list:
    """Return the paths whose committed content differs from the generated spec (a missing file is stale)."""
    expected = render_spec(spec)
    stale = []
    for path in paths:
        try:
            with open(path) as f:
                current = f.read()
        except FileNotFoundError:
            current = None
        if current != expected:
            stale.append(path)
    return stale


def write_spec(spec: dict, paths: Sequence[str]) -> None:
    """Write the spec to every path, creating the directories."""
    text = render_spec(spec)
    for path in paths:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)
        print(f"✓ OpenAPI spec written: {path}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Regenerate the specs, or with --check only report whether they are stale."""
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="write nothing; exit 1 if a committed spec differs from the generated one",
    )
    args = parser.parse_args(argv)

    try:
        spec = generate_spec()
    except Exception as e:
        print(f"✗ Error generating OpenAPI spec: {e}", file=sys.stderr)
        return 1

    if args.check:
        stale = stale_spec_paths(spec, SPEC_PATHS)
        if stale:
            for path in stale:
                print(f"✗ stale: {path}", file=sys.stderr)
            print("  Regenerate with: python scripts/update_api_specs.py", file=sys.stderr)
            return 1
        print("✓ OpenAPI specs are up to date")
        return 0

    write_spec(spec, SPEC_PATHS)
    endpoint_count = sum(len(methods) for methods in spec.get("paths", {}).values())
    print(f"  Total endpoints: {endpoint_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
