"""
Check the domain layer's dependency rules.

1. No infrastructure imports: domain/ never imports adapters, sqlalchemy,
   fastapi, etc.
2. The cross-context rule (rearchitecture/domain_model_design.md §11): a
   bounded context (a package under domain/) may depend on another context's
   ports, entities, value objects, exceptions, public functions and the public
   methods of its application service. So, inside another context, it never
   - imports a private (``_``) name or a private module,
   - imports anything but the service class from an application service module
     (``services.py`` or ``*_service.py``); value objects, constants and pure
     functions come from their own modules,
   - constructs that context's application service (``*Service(...)``): the
     service is injected at the composition root.
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


# The one cross-context import of shared ambient state the rule still allows
# (rearchitecture/domain_model_design.md §11, "Known exception"): proposal apply
# sets the change-event correlation context around its writes.
KNOWN_EXCEPTIONS: dict[tuple[str, str], frozenset[str]] = {
    ("versioning", "domain.interchange.services"): frozenset(
        {"get_current_batch_run_id", "set_batch_run_context"}
    ),
}


def _is_service_module(module_parts: list[str]) -> bool:
    """Whether a module (its parts under domain.<context>) is an application service module."""
    return bool(module_parts) and (
        module_parts[-1] == "services" or module_parts[-1].endswith("_service")
    )


def _context_of(path: Path, domain_path: Path) -> str | None:
    """The bounded context a domain file belongs to; None for the shared kernel (domain/*.py)."""
    parts = path.relative_to(domain_path).parts
    return parts[0] if len(parts) > 1 else None


def _is_private(part: str) -> bool:
    return part.startswith("_") and not (part.startswith("__") and part.endswith("__"))


class CrossContextChecker(ast.NodeVisitor):
    """AST visitor for the cross-context rule, from one context's point of view."""

    def __init__(self, own_context: str, contexts: set[str]):
        self.own_context = own_context
        self.contexts = contexts
        self.violations: list[tuple[int, str]] = []
        # Local names bound to another context's application service classes,
        # and to another context's modules (for ``module.FooService(...)``)
        self._foreign_services: set[str] = set()
        self._foreign_modules: set[str] = set()

    def _foreign_context(self, module: str) -> str | None:
        parts = module.split(".")
        if len(parts) < 2 or parts[0] != "domain":
            return None
        context = parts[1]
        if context not in self.contexts or context == self.own_context:
            return None
        return context

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if not self._foreign_context(alias.name):
                continue
            if any(_is_private(part) for part in alias.name.split(".")[2:]):
                self.violations.append((node.lineno, f"import {alias.name}: a private module"))
            # import domain.x.services as s, then s.FooService(...); unaliased,
            # the call names the whole dotted path
            self._foreign_modules.add(alias.asname or alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        if node.level == 0 and self._foreign_context(module):
            module_parts = module.split(".")[2:]
            if any(_is_private(part) for part in module_parts):
                self.violations.append((node.lineno, f"from {module} import ...: a private module"))
            service_module = _is_service_module(module_parts)
            allowed = KNOWN_EXCEPTIONS.get((self.own_context, module), frozenset())
            for alias in node.names:
                local = alias.asname or alias.name
                if _is_private(alias.name):
                    self.violations.append(
                        (node.lineno, f"from {module} import {alias.name}: a private name")
                    )
                elif (
                    service_module
                    and not alias.name.endswith("Service")
                    and alias.name not in allowed
                ):
                    self.violations.append(
                        (
                            node.lineno,
                            f"from {module} import {alias.name}: import it from its own "
                            "module (value objects, ports, exceptions, functions), not the "
                            "service module",
                        )
                    )
                if alias.name.endswith("Service"):
                    self._foreign_services.add(local)
                else:
                    self._foreign_modules.add(local)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        name = None
        if isinstance(func, ast.Name) and func.id in self._foreign_services:
            name = func.id
        elif (
            isinstance(func, ast.Attribute)
            and _dotted(func.value) in self._foreign_modules
            and func.attr.endswith("Service")
        ):
            name = f"{_dotted(func.value)}.{func.attr}"
        if name:
            self.violations.append(
                (
                    node.lineno,
                    f"{name}(...): constructs another context's service; "
                    "inject it at the composition root",
                )
            )
        self.generic_visit(node)


def _dotted(node: ast.expr) -> str | None:
    """a.b.c for a Name or an Attribute chain of Names, else None."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else None
    return None


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
    contexts = {
        child.name
        for child in domain_path.iterdir()
        if child.is_dir() and not child.name.startswith("_")
    }

    for py_file in domain_path.rglob("*.py"):
        try:
            with open(py_file, "r") as f:
                source = f.read()
            tree = ast.parse(source)
            checker = ImportChecker(str(py_file))
            checker.visit(tree)
            relative_path = py_file.relative_to(domain_path.parent)

            for line_no, import_stmt, banned_module in checker.violations:
                violations_found = True
                print(f"{relative_path}:{line_no}: {import_stmt} " f"(banned: {banned_module})")

            own_context = _context_of(py_file, domain_path)
            if own_context:
                cross = CrossContextChecker(own_context, contexts)
                cross.visit(tree)
                for line_no, message in cross.violations:
                    violations_found = True
                    print(f"{relative_path}:{line_no}: {message} (cross-context rule)")
        except SyntaxError as e:
            print(f"Syntax error in {py_file}: {e}")
            violations_found = True
        except Exception as e:
            print(f"Error checking {py_file}: {e}")
            violations_found = True

    if violations_found:
        print("\nDomain layer breaks its dependency rules!")
        return 1

    print("✓ Domain layer imports are clean, and contexts depend on each other by the rule")
    return 0


if __name__ == "__main__":
    exit_code = check_domain_imports()
    sys.exit(exit_code)
