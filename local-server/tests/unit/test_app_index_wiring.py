"""
app.py builds the vector indexes on the ontology repository's SharedSessionFactory.

An index on a separate session factory waits out busy_timeout on the write lock
of every proposal apply or revert, then fails with "database is locked"
(see tests/integration/versioning/test_proposal_apply_index_sync.py). Booting
the app loads models and config, so this reads the composition root instead.
"""

import ast
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

APP_PY = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "app.py"
)


def _session_factory_args(tree: ast.AST) -> dict[str, list[str]]:
    """Constructor name -> the variable names passed as its first argument, in app.py."""
    found: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.args:
            first = node.args[0]
            if isinstance(first, ast.Name):
                found.setdefault(node.func.id, []).append(first.id)
    return found


def _assigned_from(tree: ast.AST, constructor: str) -> set[str]:
    """Variables assigned the result of calling `constructor`."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == constructor
        ):
            names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
    return names


def test_vector_indexes_share_the_ontology_repositorys_session_factory():
    with open(APP_PY) as f:
        tree = ast.parse(f.read())
    args = _session_factory_args(tree)
    shared = _assigned_from(tree, "SharedSessionFactory")

    assert len(shared) == 1, shared
    (shared_name,) = shared
    assert args["SQLiteOntologyRepository"] == [shared_name]
    assert args["SqliteSchemaVectorIndex"] == [shared_name]
    assert args["SqliteIndividualVectorIndex"] == [shared_name]
