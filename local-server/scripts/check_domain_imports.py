"""
Import boundary linter for the domain/ package.

Verifies that domain/ code does not import from infrastructure, adapter, or
framework packages. Enforces the hexagonal architecture dependency rule:
domain must depend only on itself and Python stdlib.

Usage:
    python scripts/check_domain_imports.py

Exit codes:
    0 - No violations found
    1 - One or more violations found
"""
import ast
import sys
from pathlib import Path

# Files explicitly exempted from the boundary check
EXEMPT_FILES = {
    "domain/ontology/compat.py",
}

# Packages that domain/ code must not import from
FORBIDDEN_MODULES = {
    # Application layers
    "database", "services", "adapters", "api",
    "graph", "nlp", "llm", "rag",
    "reference_api", "reference_db",
    "embeddings", "pipeline",
    "utils", "config",
    # Frameworks
    "sqlalchemy", "fastapi", "uvicorn", "pydantic",
    "aiofiles", "starlette",
}


def check_file(filepath: Path, repo_root: Path) -> list:
    """Return list of (filepath, line_number, import_name) violation tuples."""
    relative = filepath.relative_to(repo_root)
    if str(relative) in EXEMPT_FILES:
        return []

    violations = []
    source = filepath.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError as e:
        print(f"WARNING: Could not parse {filepath}: {e}")
        return []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in FORBIDDEN_MODULES:
                    violations.append((relative, node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                if top in FORBIDDEN_MODULES:
                    violations.append((relative, node.lineno, node.module))

    return violations


def main():
    repo_root = Path(__file__).parent.parent  # local-server/
    domain_dir = repo_root / "domain"

    if not domain_dir.exists():
        print(f"ERROR: domain/ directory not found at {domain_dir}")
        sys.exit(1)

    all_violations = []
    for py_file in sorted(domain_dir.rglob("*.py")):
        all_violations.extend(check_file(py_file, repo_root))

    if all_violations:
        print("DOMAIN IMPORT BOUNDARY VIOLATIONS:")
        for filepath, lineno, module in all_violations:
            print(f"  {filepath}:{lineno} — forbidden import: {module}")
        sys.exit(1)
    else:
        file_count = sum(1 for _ in domain_dir.rglob("*.py"))
        print(f"OK: Checked {file_count} files. No violations.")
        sys.exit(0)


if __name__ == "__main__":
    main()
