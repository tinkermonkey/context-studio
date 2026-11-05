# ruff: noqa: E501 - the golden packs are verbatim text
"""
Golden tests: evidence packs for DR relationship types match DR's claimEvidence.

The pinned DR spec snapshot (0.10.0) is imported into a real SQLite workspace
and EvidencePackBuilder builds the pack for three relationship types. The
`DR_EVIDENCE` strings are the verbatim output of DR's `claimEvidence(
[relationship id, destination type], source type)` (cli/scripts/spec-enrich/
lib/intent.ts, DR main) run against the same snapshot. The facts must agree
(relationship types between the pair with predicate meanings; the named type's
predicate, same-pair predicates and reverse predicates); the formatting is
Context Studio's own and is pinned separately.
"""

import json
import os
import re
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from adapters.interchange.dr_relationships import dr_property_definitions
from adapters.persistence.sqlite.connection import create_local_db_engine, create_session_factory
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.ontology.evidence import ContextPolicy, EvidencePackBuilder
from scripts.dr_ontology_loader import import_dr_ontology
from scripts.import_dr_model import build_import_service
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.integration.pipelines._harness.dr_spec import MODEL_DR_SPEC_VERSION, dr_spec_dir

DR_EVIDENCE = {
    "motivation.requirement.realizes.motivation.goal": """\
Relationship schemas between motivation.requirement, motivation.goal (exact list, 9 schemas):
  motivation.goal.aggregates.motivation.goal  (aggregates: Whole-part relationship where part can exist independently)
  motivation.goal.aggregates.motivation.requirement  (aggregates: Whole-part relationship where part can exist independently)
  motivation.goal.influence.motivation.goal  (influence: Element affects or impacts another element)
  motivation.goal.influence.motivation.requirement  (influence: Element affects or impacts another element)
  motivation.goal.realizes.motivation.goal  (realizes: Element implements or makes concrete another element)
  motivation.goal.specializes.motivation.goal  (specializes: Type-subtype relationship (inheritance))
  motivation.requirement.aggregates.motivation.goal  (aggregates: Whole-part relationship where part can exist independently)
  motivation.requirement.associated-with.motivation.goal  (associated-with: Generic relationship indicating elements are related or connected)
  motivation.requirement.realizes.motivation.goal  (realizes: Element implements or makes concrete another element)

Relationship motivation.requirement.realizes.motivation.goal: predicate realizes (Element implements or makes concrete another element); all predicates motivation.requirement -> motivation.goal: [aggregates, associated-with, realizes]; reverse direction motivation.goal -> motivation.requirement: [aggregates, influence]""",
    "testing.testcasesketch.validates.testing.coveragerequirement": """\
Relationship schemas between testing.testcasesketch, testing.coveragerequirement (exact list, 6 schemas):
  testing.coveragerequirement.flows-to.testing.coveragerequirement  (flows-to: Data or control flows from one element to another)
  testing.coveragerequirement.flows-to.testing.testcasesketch  (flows-to: Data or control flows from one element to another)
  testing.coveragerequirement.references.testing.coveragerequirement  (references: Pointer reference without functional dependency)
  testing.testcasesketch.references.testing.coveragerequirement  (references: Pointer reference without functional dependency)
  testing.testcasesketch.tests.testing.coveragerequirement  (tests: Element validates or verifies another element)
  testing.testcasesketch.validates.testing.coveragerequirement  (validates: Test element validates that a requirement or target is satisfied)

Relationship testing.testcasesketch.validates.testing.coveragerequirement: predicate validates (Test element validates that a requirement or target is satisfied); all predicates testing.testcasesketch -> testing.coveragerequirement: [references, tests, validates]; reverse direction testing.coveragerequirement -> testing.testcasesketch: [flows-to]""",
    "application.applicationservice.realizes.business.businessservice": """\
Relationship schemas between application.applicationservice, business.businessservice (exact list, 1 schemas):
  application.applicationservice.realizes.business.businessservice  (realizes: Element implements or makes concrete another element)

Relationship application.applicationservice.realizes.business.businessservice: predicate realizes (Element implements or makes concrete another element); all predicates application.applicationservice -> business.businessservice: [realizes]; reverse direction business.businessservice -> application.applicationservice: [none]""",
}

CS_TEXT = {
    "motivation.requirement.realizes.motivation.goal": """\
Relationship types between motivation_requirement, motivation_goal (exact list, 9 types):
  motivation_goal --[aggregates]--> motivation_goal  (aggregates: Whole-part relationship where part can exist independently)
  motivation_goal --[aggregates]--> motivation_requirement  (aggregates: Whole-part relationship where part can exist independently)
  motivation_goal --[influence]--> motivation_goal  (influence: Element affects or impacts another element)
  motivation_goal --[influence]--> motivation_requirement  (influence: Element affects or impacts another element)
  motivation_goal --[realizes]--> motivation_goal  (realizes: Element implements or makes concrete another element)
  motivation_goal --[specializes]--> motivation_goal  (specializes: Type-subtype relationship (inheritance))
  motivation_requirement --[aggregates]--> motivation_goal  (aggregates: Whole-part relationship where part can exist independently)
  motivation_requirement --[associated-with]--> motivation_goal  (associated-with: Generic relationship indicating elements are related or connected)
  motivation_requirement --[realizes]--> motivation_goal  (realizes: Element implements or makes concrete another element)

Relationship type motivation_requirement --[realizes]--> motivation_goal: predicate realizes (Element implements or makes concrete another element); all predicates motivation_requirement -> motivation_goal: [aggregates, associated-with, realizes]; reverse direction motivation_goal -> motivation_requirement: [aggregates, influence]""",
    "testing.testcasesketch.validates.testing.coveragerequirement": """\
Relationship types between testing_testcasesketch, testing_coveragerequirement (exact list, 6 types):
  testing_coveragerequirement --[flows-to]--> testing_coveragerequirement  (flows-to: Data or control flows from one element to another)
  testing_coveragerequirement --[flows-to]--> testing_testcasesketch  (flows-to: Data or control flows from one element to another)
  testing_coveragerequirement --[references]--> testing_coveragerequirement  (references: Pointer reference without functional dependency)
  testing_testcasesketch --[references]--> testing_coveragerequirement  (references: Pointer reference without functional dependency)
  testing_testcasesketch --[tests]--> testing_coveragerequirement  (tests: Element validates or verifies another element)
  testing_testcasesketch --[validates]--> testing_coveragerequirement  (validates: Test element validates that a requirement or target is satisfied)

Relationship type testing_testcasesketch --[validates]--> testing_coveragerequirement: predicate validates (Test element validates that a requirement or target is satisfied); all predicates testing_testcasesketch -> testing_coveragerequirement: [references, tests, validates]; reverse direction testing_coveragerequirement -> testing_testcasesketch: [flows-to]""",
    "application.applicationservice.realizes.business.businessservice": """\
Relationship types between application_applicationservice, business_businessservice (exact list, 1 types):
  application_applicationservice --[realizes]--> business_businessservice  (realizes: Element implements or makes concrete another element)

Relationship type application_applicationservice --[realizes]--> business_businessservice: predicate realizes (Element implements or makes concrete another element); all predicates application_applicationservice -> business_businessservice: [realizes]; reverse direction business_businessservice -> application_applicationservice: [none]""",
}

_PAIR_ROW = re.compile(r"^  (\S+)  \(([^:]+): (.*)\)$")
_PREDICATE_LINE = re.compile(
    r"^Relationship (\S+): predicate (\S+) \((.*)\); all predicates \S+ -> \S+: \[(.*)\]; "
    r"reverse direction \S+ -> \S+: \[(.*)\]$"
)


def _list(text: str) -> list[str]:
    return [] if text in ("", "none") else text.split(", ")


def _dr_facts(evidence: str) -> dict:
    """The facts in a DR claimEvidence block."""
    pair_block, predicate_block = evidence.split("\n\n")
    pair = sorted(_PAIR_ROW.match(row).groups() for row in pair_block.splitlines()[1:])
    rel_id, predicate, meaning, same, reverse = _PREDICATE_LINE.match(predicate_block).groups()
    return {
        "pair": pair,
        "predicate": (rel_id, predicate, meaning),
        "same": sorted(_list(same)),
        "reverse": sorted(_list(reverse)),
    }


@pytest.fixture(scope="module")
def workspace(tmp_path_factory):
    """The pinned DR spec imported into a file SQLite workspace, plus its predicate catalog."""
    db_path = tmp_path_factory.mktemp("dr_evidence") / "local.db"
    engine = create_local_db_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    repo = SQLiteOntologyRepository(session_factory)
    spec_dir = dr_spec_dir(MODEL_DR_SPEC_VERSION)
    import_dr_ontology(
        build_import_service(session_factory, FakeEmbeddingService()), repo, spec_dir
    )
    catalog = json.loads((spec_dir / "schemas" / "base" / "predicates.json").read_text())
    by_dr_id = dr_property_definitions(repo)
    return {
        "builder": EvidencePackBuilder(repo, catalog["predicates"]),
        "by_dr_id": by_dr_id,
        "dr_id_by_property": {prop.id: dr_id for dr_id, prop in by_dr_id.items()},
    }


@pytest.mark.parametrize("dr_id", sorted(DR_EVIDENCE))
def test_pack_facts_match_dr_claim_evidence(workspace, dr_id):
    prop = workspace["by_dr_id"][dr_id]
    pack = workspace["builder"].build_for_relationship_type(prop.id, ContextPolicy.NONE)
    dr_id_of = workspace["dr_id_by_property"]
    expected = _dr_facts(DR_EVIDENCE[dr_id])

    pair = sorted((dr_id_of[e.property_id], e.predicate, e.meaning) for e in pack.pair.edges)
    [context] = pack.predicates
    assert pair == expected["pair"]
    assert (dr_id_of[context.edge.property_id], context.edge.predicate, context.edge.meaning) == (
        expected["predicate"]
    )
    assert list(context.same_pair_predicates) == expected["same"]
    assert list(context.reverse_predicates) == expected["reverse"]


@pytest.mark.parametrize("dr_id", sorted(CS_TEXT))
def test_pack_text_is_pinned(workspace, dr_id):
    prop = workspace["by_dr_id"][dr_id]
    pack = workspace["builder"].build_for_relationship_type(prop.id, ContextPolicy.NONE)

    assert pack.text == CS_TEXT[dr_id]
