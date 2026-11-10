"""ClaimService and the claim entities (#1518), over fake repositories."""

import pytest

from domain.ontology.entities import AttributeDefinition, Class, PropertyDefinition, Taxonomy
from domain.ontology.exceptions import EntityNotFoundError
from domain.versioning.claims import (
    Claim,
    ClaimFilter,
    ClaimService,
    ClaimTriage,
    ClaimVerdict,
    NoteSource,
    Validity,
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
        with pytest.raises(EntityNotFoundError, match="missing"):
            service.submit("t", [claim(subject_id="missing")])

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
