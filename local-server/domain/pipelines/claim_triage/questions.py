"""
The triage questions, ported from DR's cli/scripts/spec-enrich/triage.ts QUESTIONS
(classifier_relevant is left out: #1418 doesn't ask it).
"""

from collections.abc import Mapping

from domain.decision.value_objects import ChoiceQuestion, Question, ScoreQuestion, YesNoQuestion
from domain.versioning.claims import Validity

VALIDITY_CRITERIA = {
    Validity.REAL_DEFECT.value: (
        "The claim identifies a genuine problem in the taxonomy as written; it should be fixed"
    ),
    Validity.WORKS_AS_DESIGNED.value: (
        "The taxonomy intends this; the claim misreads the design or the scheme's intent, and"
        " at most the definition should say so more clearly"
    ),
    Validity.JUDGMENT_CALL.value: (
        "A reasonable modelling choice either way; needs a product decision, not a correction"
    ),
    Validity.OUT_OF_SCOPE.value: (
        "The claim is about something the taxonomy deliberately does not model, or about"
        " tooling rather than the taxonomy"
    ),
}

SEVERITY_LEVELS = (
    "0 cosmetic: wording or documentation only; nothing a modeller does changes",
    "1 minor: a modeller can work around it; occasional confusion",
    "2 significant: models built today will be inconsistent or lose information because of it",
    "3 blocking: it prevents modelling a common case correctly or makes valid models fail",
)

FIX_SCOPE_LEVELS = (
    "0 wording: change only descriptions or documentation",
    "1 additive: add an attribute, enum value or relationship; existing models stay valid",
    "2 breaking: rename, retype, remove or change required-ness; existing models need migration",
    "3 roadmap: a design change that needs its own proposal",
)

ADDRESSED_BY_PROPOSAL = "addressed_by_proposal"


def triage_questions(
    categories: Mapping[str, str], with_pending_definition: bool
) -> dict[str, Question]:
    """
    The questions to ask about one claim.

    Args:
        categories: The category vocabulary (option -> when it applies)
        with_pending_definition: Whether the state shows a pending definition;
            addressed_by_proposal is asked only then
    """
    questions: dict[str, Question] = {
        "validity": ChoiceQuestion(
            instructions=(
                "Is this claim a genuine problem with the taxonomy, the taxonomy working as"
                " designed, a judgment call, or out of scope? Judge against the design intent"
                " and the current schema shown."
            ),
            criteria=VALIDITY_CRITERIA,
            offer_none=False,
        ),
        "category": ChoiceQuestion(
            instructions="Which category best describes the claim?",
            criteria=dict(categories),
            offer_none=False,
        ),
        "severity": ScoreQuestion(
            instructions=(
                "If the claim is valid, how severe is the problem for people building models"
                " with this taxonomy?"
            ),
            levels=SEVERITY_LEVELS,
        ),
        "fix_scope": ScoreQuestion(
            instructions="What scope of change would resolve the claim?",
            levels=FIX_SCOPE_LEVELS,
        ),
    }
    if with_pending_definition:
        questions[ADDRESSED_BY_PROPOSAL] = YesNoQuestion(
            instructions=(
                "The proposed definition shown in the context already resolves this claim"
                " (e.g. the claim is a misreading that the new wording prevents)."
            )
        )
    return questions
