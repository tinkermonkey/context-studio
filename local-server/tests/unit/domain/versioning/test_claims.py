"""ClaimService and the claim entities (#1518), over fake repositories."""

import pytest

from domain.ontology.entities import (
    AttributeDefinition,
    Class,
    ConceptScheme,
    PropertyDefinition,
    Taxonomy,
)
from domain.ontology.exceptions import EntityNotFoundError
from domain.versioning.claims import (
    Claim,
    ClaimFilter,
    ClaimService,
    ClaimTriage,
    ClaimVerdict,
    NoteSource,
    Validity,
    score_triage,
)
from tests.fakes.fake_claim_repository import FakeClaimRepository
from tests.fakes.fake_ontology_repository import FakeOntologyRepository


@pytest.fixture()
def ontology():
    repo = FakeOntologyRepository()
    repo.save_taxonomy(Taxonomy(id="t", title="DR", identifier="dr"))
    repo.save_class(Class(id="c1", taxonomy_id="t", concept_scheme_id="s", title="Service"))
    repo.save_property_definition(PropertyDefinition(id="p1", identifier="serves", title="serves"))
    repo.save_attribute_definition(
        AttributeDefinition(
            id="a1", class_id="c1", identifier="name", title="Name", datatype="string"
        )
    )
    return repo


@pytest.fixture()
def service(ontology):
    return ClaimService(FakeClaimRepository(), ontology)


def claim(key="n#1", **kwargs):
    fields = {
        "taxonomy_id": "t",
        "text": "Name should be required",
        "note_ref": "n",
        "note_source": NoteSource.MAINTAINER,
    }
    fields.update(kwargs)
    return Claim(key=key, **fields)


class TestEntities:
    @pytest.mark.parametrize("missing", ["key", "text", "note_ref"])
    def test_a_claim_needs_a_key_text_and_note(self, missing):
        with pytest.raises(ValueError, match=missing):
            claim(**{missing: " "})

    def test_values_are_coerced_to_enums(self):
        assert claim(note_source="reviewer").note_source is NoteSource.REVIEWER
        assert ClaimTriage(validity="real_defect", model="m").validity is Validity.REAL_DEFECT

    @pytest.mark.parametrize("field_name", ["severity", "fix_scope"])
    def test_scores_run_from_0_to_3(self, field_name):
        with pytest.raises(ValueError, match=field_name):
            ClaimTriage(validity="real_defect", model="m", **{field_name: 4})
        with pytest.raises(ValueError, match=field_name):
            ClaimVerdict(validity="real_defect", adjudicated_by="user", **{field_name: -1})

    def test_a_verdict_names_who_gave_it(self):
        with pytest.raises(ValueError, match="adjudicated_by"):
            ClaimVerdict(validity="real_defect", adjudicated_by=" ")

    def test_unknown_validity_is_refused(self):
        with pytest.raises(ValueError):
            ClaimTriage(validity="maybe", model="m")


class TestSubmit:
    def test_unknown_affected_ids_move_to_unresolved_refs(self, service):
        stored = service.submit(
            "t", [claim(affected_ids=["c1", "p1", "a1", "spec.thing"], unresolved_refs=["x"])]
        )[0]

        assert stored.affected_ids == ["c1", "p1", "a1"]
        assert stored.unresolved_refs == ["x", "spec.thing"]

    def test_unknown_taxonomy_or_subject_is_refused(self, service):
        with pytest.raises(EntityNotFoundError):
            service.submit("nope", [claim(taxonomy_id="nope")])
        with pytest.raises(ValueError, match="n#1: subject missing"):
            service.submit("t", [claim(subject_id="missing")])

    def test_only_ids_in_the_taxonomy_resolve(self, service, ontology):
        ontology.save_taxonomy(Taxonomy(id="t2", title="House", identifier="house"))
        ontology.save_concept_scheme(ConceptScheme(id="s1", taxonomy_id="t", title="API"))
        ontology.save_concept_scheme(ConceptScheme(id="s2", taxonomy_id="t2", title="Rooms"))
        ontology.save_class(Class(id="c2", taxonomy_id="t2", concept_scheme_id="s2", title="Room"))
        ontology.save_property_definition(
            PropertyDefinition(id="p2", identifier="in", title="in", domain_class_id="c2")
        )
        ontology.save_attribute_definition(
            AttributeDefinition(
                id="a2", class_id="c2", identifier="area", title="Area", datatype="string"
            )
        )

        stored = service.submit(
            "t", [claim(affected_ids=["t", "s1", "c1", "t2", "s2", "c2", "p2", "a2"])]
        )[0]

        assert stored.affected_ids == ["t", "s1", "c1"]
        assert stored.unresolved_refs == ["t2", "s2", "c2", "p2", "a2"]
        with pytest.raises(ValueError, match="subject c2 is not in this taxonomy"):
            service.submit("t", [claim(subject_id="c2")])

    def test_ids_are_not_repeated(self, service):
        stored = service.submit(
            "t", [claim(affected_ids=["c1", "c1", "x.y"], unresolved_refs=["x.y"])]
        )[0]

        assert stored.affected_ids == ["c1"]
        assert stored.unresolved_refs == ["x.y"]

    def test_keys_and_note_refs_are_trimmed(self):
        assert (claim(key=" n#1 ").key, claim(note_ref=" n ").note_ref) == ("n#1", "n")

    def test_repeated_keys_or_another_taxonomy_are_refused(self, service, ontology):
        ontology.save_taxonomy(Taxonomy(id="t2", title="House", identifier="house"))
        with pytest.raises(ValueError, match="n#1"):
            service.submit("t", [claim(), claim()])
        with pytest.raises(ValueError, match="another taxonomy"):
            service.submit("t", [claim(taxonomy_id="t2")])

    def test_resubmitting_replaces_by_key(self, service):
        first = service.submit("t", [claim(subject_id="c1")])[0]
        again = service.submit("t", [claim(subject_id="c1", category_hint="attribute_typing")])[0]

        assert again.id == first.id
        assert service.count_claims(ClaimFilter(taxonomy_id="t")) == 1

    def test_deleting_a_notes_claims_keeps_the_keys_asked_for(self, service):
        service.submit("t", [claim("n#1"), claim("n#2"), claim("m#1", note_ref="m")])

        assert service.delete_note_claims("t", "n", keep_keys=["n#1"]) == 1
        keys = [c.key for c in service.list_claims(ClaimFilter(taxonomy_id="t"))]
        assert sorted(keys) == ["m#1", "n#1"]
        with pytest.raises(EntityNotFoundError):
            service.delete_note_claims("nope", "n")

    def test_in_taxonomy_names_the_ids_a_claim_may_name(self, service):
        assert service.in_taxonomy("t", {"t", "c1", "a1", "p1", "elsewhere"}) == {
            "t",
            "c1",
            "a1",
            "p1",
        }


class TestTriageAndVerdict:
    def test_triage_then_verdict_then_clear(self, service):
        stored = service.submit("t", [claim()])[0]

        triaged = service.save_triage(stored.id, ClaimTriage(validity="real_defect", model="m"))
        assert triaged.triage.validity is Validity.REAL_DEFECT
        judged = service.set_verdict(
            stored.id, ClaimVerdict(validity="judgment_call", adjudicated_by="user")
        )
        assert judged.verdict.validity is Validity.JUDGMENT_CALL
        assert service.set_verdict(stored.id, None).verdict is None

    def test_unknown_claim_is_refused(self, service):
        with pytest.raises(EntityNotFoundError):
            service.save_triage("nope", ClaimTriage(validity="real_defect", model="m"))
        with pytest.raises(EntityNotFoundError):
            service.set_verdict("nope", None)
        with pytest.raises(EntityNotFoundError):
            service.get("nope")

    def test_listing_an_unknown_taxonomy_is_refused(self, service):
        with pytest.raises(EntityNotFoundError):
            service.list_claims(ClaimFilter(taxonomy_id="nope"))


class TestScoreTriage:
    @staticmethod
    def judged(key, got, gold, **kwargs):
        triage = ClaimTriage(
            validity=got,
            model="m",
            validity_probabilities=kwargs.get("p", {got: 0.8}),
            category=kwargs.get("category", "other"),
            severity=kwargs.get("severity", 1),
            fix_scope=kwargs.get("fix_scope", 0),
            latency_ms=kwargs.get("latency", 100.0),
            cost_usd=kwargs.get("cost", 0.001),
        )
        verdict = ClaimVerdict(
            validity=gold,
            adjudicated_by="user",
            category=kwargs.get("gold_category", "other"),
            severity=kwargs.get("gold_severity", 1),
            fix_scope=kwargs.get("gold_fix_scope"),
        )
        return claim(key=key, triage=triage, verdict=verdict)

    def test_metrics_follow_dr_triage_bench(self):
        score = score_triage(
            [
                self.judged(
                    "a#1",
                    "real_defect",
                    "real_defect",
                    p={"real_defect": 0.9},
                    severity=3,
                    gold_severity=1,
                    fix_scope=2,
                    gold_fix_scope=1,
                    latency=300.0,
                ),
                self.judged(
                    "b#1",
                    "real_defect",
                    "works_as_designed",
                    p={"real_defect": 0.7, "works_as_designed": 0.2},
                    category="type_overlap",
                    gold_category=None,
                    latency=100.0,
                    cost=None,
                ),
                self.judged("c#1", "judgment_call", "judgment_call", p={}, latency=200.0),
                claim(key="untriaged#1"),  # no triage or verdict: left out
            ]
        )

        assert score.n == 3
        assert score.validity_accuracy == pytest.approx(2 / 3)
        assert score.mean_p_gold_validity == pytest.approx((0.9 + 0.2 + 0.0) / 3)
        assert score.category_accuracy == pytest.approx(1.0)  # b has no gold category
        assert score.severity_mae == pytest.approx(2 / 3)
        assert score.severity_within_1 == pytest.approx(2 / 3)
        assert score.fix_scope_mae == pytest.approx(1.0)  # only a has a gold fix scope
        assert score.median_latency_ms == 200.0
        assert score.mean_cost_usd == pytest.approx(0.002 / 3)
        assert score.misses == ("b#1",)

    def test_nothing_to_score(self):
        score = score_triage([claim()])
        assert score.n == 0
        assert score.validity_accuracy is None and score.median_latency_ms is None
