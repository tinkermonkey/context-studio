"""
Unit tests for the cross-context rule in scripts/check_domain_imports.py (#1633).
"""

import ast
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from scripts.check_domain_imports import CrossContextChecker, check_domain_imports

CONTEXTS = {"pipelines", "versioning", "ontology"}


def violations(source: str, own_context: str = "pipelines") -> list[str]:
    checker = CrossContextChecker(own_context, CONTEXTS)
    checker.visit(ast.parse(source))
    return [message for _, message in checker.violations]


class TestAllowed:
    @pytest.mark.parametrize(
        "source",
        [
            "from domain.versioning.proposals import OperationDraft",
            "from domain.versioning.ports import ChangeProposalRepository",
            "from domain.versioning.exceptions import ProposalNotFoundError",
            # The service class itself, received through the constructor
            "from domain.versioning.proposal_service import ProposalService\n"
            "def run(service: ProposalService):\n    return service.get('p')",
            # A context's own service and private names are its own business
            "from domain.pipelines._internal import _helper\n"
            "from domain.pipelines.thing_service import ThingService\nThingService()",
        ],
    )
    def test_passes(self, source):
        assert violations(source) == []


class TestRefused:
    def test_a_value_object_through_the_service_module(self):
        found = violations("from domain.versioning.proposal_service import OperationDraft")

        assert len(found) == 1
        assert "OperationDraft" in found[0]

    def test_a_private_name(self):
        found = violations("from domain.versioning.proposals import _reason")

        assert found == ["from domain.versioning.proposals import _reason: a private name"]

    def test_a_private_module(self):
        assert violations("from domain.ontology._cache import thing")
        assert violations("import domain.ontology._cache")

    def test_constructing_another_contexts_service(self):
        found = violations(
            "from domain.versioning.proposal_service import ProposalService\n"
            "service = ProposalService(repo)"
        )

        assert len(found) == 1
        assert "constructs another context's service" in found[0]

    def test_constructing_it_through_its_module(self):
        found = violations("from domain.ontology import services\nservices.OntologyService(repo)")

        assert len(found) == 1


def test_the_domain_layer_keeps_the_rule(capsys):
    """The real domain/ passes both checks."""
    assert check_domain_imports() == 0
