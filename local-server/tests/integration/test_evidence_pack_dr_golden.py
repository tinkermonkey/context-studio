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

The attribute case does the same for the `type` attribute across the security
layer (`DR_ATTRIBUTE_EVIDENCE`), on the attribute definitions the DR importer
brings in from the snapshot's node schemas (`properties.attributes`). It pins
the attribute section's scope (the scheme), row order and clipping.

To regenerate the DR strings, from a documentation_robotics checkout at the
snapshot's commit (see tests/integration/fixtures/dr_spec/README.md):

    mkdir /tmp/drrun && cd /tmp/drrun && echo '{"type":"module"}' > package.json
    # schemas.ts: cli/scripts/spec-enrich/lib/schemas.ts, with its repoRoot import
    #   replaced by `const repoRoot = () => process.env.DR_ROOT as string;`
    # claim.ts: `import { loadNodeSchemas, loadRelationshipSchemas, loadPredicates,
    #   type NodeSchema } from "./schemas.ts"; function allNodes() { return loadNodeSchemas(); }`,
    #   then claimEvidence() copied verbatim from lib/intent.ts, then
    #   `const [subject, ...ids] = process.argv.slice(2); console.log(claimEvidence(ids, subject));`
    export DR_ROOT=<documentation_robotics checkout>   # node 24 runs .ts directly
    node claim.ts motivation.requirement motivation.requirement.realizes.motivation.goal motivation.goal
    node claim.ts testing.testcasesketch testing.testcasesketch.validates.testing.coveragerequirement testing.coveragerequirement
    node claim.ts application.applicationservice application.applicationservice.realizes.business.businessservice business.businessservice
    node claim.ts security.threat security.threat.type
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
from scripts.dr_ontology_loader import import_dr_ontology, slugify_spec_node_id
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
    "application.applicationservice.realizes.business.businessservice": """\
Relationship types between application_applicationservice, business_businessservice (exact list, 1 types):
  application_applicationservice --[realizes]--> business_businessservice [applicationservice_realizes_businessservice]  (realizes: Element implements or makes concrete another element)

Relationship type application_applicationservice --[realizes]--> business_businessservice [applicationservice_realizes_businessservice]: predicate realizes (Element implements or makes concrete another element); all predicates application_applicationservice -> business_businessservice: [realizes]; reverse direction business_businessservice -> application_applicationservice: [none]""",
    "motivation.requirement.realizes.motivation.goal": """\
Relationship types between motivation_requirement, motivation_goal (exact list, 9 types):
  motivation_goal --[aggregates]--> motivation_goal [goal_aggregates_goal]  (aggregates: Whole-part relationship where part can exist independently)
  motivation_goal --[aggregates]--> motivation_requirement [goal_aggregates_requirement]  (aggregates: Whole-part relationship where part can exist independently)
  motivation_goal --[influence]--> motivation_goal [goal_influence_goal]  (influence: Element affects or impacts another element)
  motivation_goal --[influence]--> motivation_requirement [goal_influence_requirement]  (influence: Element affects or impacts another element)
  motivation_goal --[realizes]--> motivation_goal [goal_realizes_goal]  (realizes: Element implements or makes concrete another element)
  motivation_goal --[specializes]--> motivation_goal [goal_specializes_goal]  (specializes: Type-subtype relationship (inheritance))
  motivation_requirement --[aggregates]--> motivation_goal [requirement_aggregates_goal]  (aggregates: Whole-part relationship where part can exist independently)
  motivation_requirement --[associated-with]--> motivation_goal [requirement_associated_with_goal]  (associated-with: Generic relationship indicating elements are related or connected)
  motivation_requirement --[realizes]--> motivation_goal [requirement_realizes_goal]  (realizes: Element implements or makes concrete another element)

Relationship type motivation_requirement --[realizes]--> motivation_goal [requirement_realizes_goal]: predicate realizes (Element implements or makes concrete another element); all predicates motivation_requirement -> motivation_goal: [aggregates, associated-with, realizes]; reverse direction motivation_goal -> motivation_requirement: [aggregates, influence]""",
    "testing.testcasesketch.validates.testing.coveragerequirement": """\
Relationship types between testing_testcasesketch, testing_coveragerequirement (exact list, 6 types):
  testing_coveragerequirement --[flows-to]--> testing_coveragerequirement [coveragerequirement_flows_to_coveragerequirement]  (flows-to: Data or control flows from one element to another)
  testing_coveragerequirement --[flows-to]--> testing_testcasesketch [coveragerequirement_flows_to_testcasesketch]  (flows-to: Data or control flows from one element to another)
  testing_coveragerequirement --[references]--> testing_coveragerequirement [coveragerequirement_references_coveragerequirement]  (references: Pointer reference without functional dependency)
  testing_testcasesketch --[references]--> testing_coveragerequirement [testcasesketch_references_coveragerequirement]  (references: Pointer reference without functional dependency)
  testing_testcasesketch --[tests]--> testing_coveragerequirement [testcasesketch_tests_coveragerequirement]  (tests: Element validates or verifies another element)
  testing_testcasesketch --[validates]--> testing_coveragerequirement [testcasesketch_validates_coveragerequirement]  (validates: Test element validates that a requirement or target is satisfied)

Relationship type testing_testcasesketch --[validates]--> testing_coveragerequirement [testcasesketch_validates_coveragerequirement]: predicate validates (Test element validates that a requirement or target is satisfied); all predicates testing_testcasesketch -> testing_coveragerequirement: [references, tests, validates]; reverse direction testing_coveragerequirement -> testing_testcasesketch: [flows-to]""",
}

DR_ATTRIBUTE_EVIDENCE = """\
Attribute 'type' as declared across layer security (6 types):
  actor.type: type=string enum[human|service|system|external-entity] required=true desc="Category of actor, per NIST AC-2 (Account Management) subject classification."
  countermeasure.type: type=string enum[technical|operational|management|physical] required=true desc="NIST SP 800-53 control family classification: technical (hardware/software mechanisms), op"
  evidence.type: type=string enum[log|signature|timestamp|hash|certificate|audit-trail] required=true desc="Category of evidence artifact, per NIST AU-10 (Non-repudiation)."
  policyaction.type: type=string enum[allow|deny|log|alert|redirect|rate-limit|challenge|quarantine|notify|mask|encrypt] required=true desc="Enforcement action type applied when the parent policy rule fires."
  secureresource.type: type=string enum[api|database|file|service|ui|stream] required=true desc="Category of protected resource, used to apply appropriate access control and audit policie"
  validationrule.type: type=string enum[regex|range|length|enum|custom] required=true desc="Validation mechanism type, per NIST SI-10 (Information Input Validation)."
"""

CS_ATTRIBUTE_TEXT = """\
Attribute 'type' as declared across scheme security (6 classes):
  security_actor.type: type=string enum[human|service|system|external-entity] required=true desc="Category of actor, per NIST AC-2 (Account Management) subject classification."
  security_countermeasure.type: type=string enum[technical|operational|management|physical] required=true desc="NIST SP 800-53 control family classification: technical (hardware/software mechanisms), op"
  security_evidence.type: type=string enum[log|signature|timestamp|hash|certificate|audit-trail] required=true desc="Category of evidence artifact, per NIST AU-10 (Non-repudiation)."
  security_policyaction.type: type=string enum[allow|deny|log|alert|redirect|rate-limit|challenge|quarantine|notify|mask|encrypt] required=true desc="Enforcement action type applied when the parent policy rule fires."
  security_secureresource.type: type=string enum[api|database|file|service|ui|stream] required=true desc="Category of protected resource, used to apply appropriate access control and audit policie"
  security_validationrule.type: type=string enum[regex|range|length|enum|custom] required=true desc="Validation mechanism type, per NIST SI-10 (Information Input Validation).\""""

_ATTRIBUTE_ROW = re.compile(
    r'^  (\w+)\.type: type=(\S+)(?: enum\[(.*)\])? required=(true|false)(?: desc="(.*)")?'
)
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


def _security_types(repo, spec_dir) -> dict[str, str]:
    """Every security class id -> its DR type name."""
    type_by_class_id = {}
    for path in sorted((spec_dir / "schemas" / "nodes" / "security").glob("*.node.schema.json")):
        spec_node_id = json.loads(path.read_text())["properties"]["spec_node_id"]["const"]
        cls = repo.get_by_identifier(slugify_spec_node_id(spec_node_id))
        type_by_class_id[cls.id] = spec_node_id.split(".")[1]
    return type_by_class_id


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
    type_by_class_id = _security_types(repo, spec_dir)
    catalog = json.loads((spec_dir / "schemas" / "base" / "predicates.json").read_text())
    by_dr_id = dr_property_definitions(repo)
    return {
        "repo": repo,
        "type_by_class_id": type_by_class_id,
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


def _threat_type_pack(workspace):
    threat = workspace["repo"].get_by_identifier("security_threat")
    return workspace["builder"].build_for_attribute(threat.id, "type", ContextPolicy.NONE)


def test_attribute_facts_match_dr_claim_evidence(workspace):
    [evidence] = _threat_type_pack(workspace).attributes
    type_of = workspace["type_by_class_id"]

    peers = sorted(
        (
            type_of[p.class_id],
            p.datatype,
            "|".join(p.allowed_values or ()),
            str(p.is_required).lower(),
            p.definition or "",  # DR rows without a desc parse as ""
        )
        for p in evidence.peers
    )
    expected = sorted(
        _ATTRIBUTE_ROW.match(row).groups(default="")
        for row in DR_ATTRIBUTE_EVIDENCE.splitlines()[1:]
    )
    assert peers == expected
    assert evidence.omitted == 0


def test_attribute_text_is_pinned(workspace):
    assert _threat_type_pack(workspace).text == CS_ATTRIBUTE_TEXT
