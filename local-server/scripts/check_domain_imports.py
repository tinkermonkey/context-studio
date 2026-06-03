"""
Check that domain layer files do not import from infrastructure packages.

This script scans all Python files under domain/ and ensures they don't
import from prohibited packages like adapters, sqlalchemy, fastapi, etc.
"""

import ast
import sys
from pathlib import Path

BANNED_IMPORTS = {
    "adapters",
    "sqlalchemy",
    "fastapi",
    "pydantic",
    "sentence_transformers",
    "spacy",
    "networkx",
    "rdflib",
    "duckdb",
    "openai",
    "anthropic",
    "httpx",
    "uvicorn",
    "utils",
}


class ImportChecker(ast.NodeVisitor):
    """AST visitor to check for banned imports"""

    def __init__(self, filename: str):
        self.filename = filename
        self.violations: list[tuple[int, str, str]] = []

    def visit_Import(self, node: ast.Import) -> None:
        """Check 'import X' statements"""
        for alias in node.names:
            module_name = alias.name.split(".")[0]
            if module_name in BANNED_IMPORTS:
                self.violations.append((node.lineno, f"import {alias.name}", module_name))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Check 'from X import Y' statements"""
        if node.module:
            module_name = node.module.split(".")[0]
            if module_name in BANNED_IMPORTS:
                self.violations.append(
                    (
                        node.lineno,
                        f"from {node.module} import ...",
                        module_name,
                    )
                )
        self.generic_visit(node)


def check_domain_imports() -> int:
    """
    Check all domain files for banned imports.

    Returns:
        0 if no violations found, 1 if violations found
    """
    domain_path = Path(__file__).parent.parent / "domain"

    if not domain_path.exists():
        print(f"Error: domain directory not found at {domain_path}")
        return 1

    violations_found = False

    for py_file in domain_path.rglob("*.py"):
        try:
            with open(py_file, "r") as f:
                source = f.read()
            tree = ast.parse(source)
            checker = ImportChecker(str(py_file))
            checker.visit(tree)

            for line_no, import_stmt, banned_module in checker.violations:
                violations_found = True
                relative_path = py_file.relative_to(domain_path.parent)
                print(f"{relative_path}:{line_no}: {import_stmt} " f"(banned: {banned_module})")
        except SyntaxError as e:
            print(f"Syntax error in {py_file}: {e}")
            violations_found = True
        except Exception as e:
            print(f"Error checking {py_file}: {e}")
            violations_found = True

    if violations_found:
        print("\nDomain layer contains banned imports!")
        return 1

    print("✓ Domain layer imports are clean")
    return 0


if __name__ == "__main__":
    exit_code = check_domain_imports()
    sys.exit(exit_code)
