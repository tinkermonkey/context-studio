"""
Default stage prompts for LLM individual extraction (ExtractionService.extract_triples).

Pass 1 identifies and types the individuals a text mentions; pass 2 derives
the relationships between them. A pipeline configuration can override either
through ``stage_prompts``; see domain/pipelines/stage_prompts.py.

The defaults render byte-identical to the prompts recorded in the quality-test
cassettes, so changing a default invalidates those recordings. That includes
the indentation inside the user templates.
"""

from domain.pipelines.stage_prompts import StageDefinition, StagePrompt

IDENTIFY_INDIVIDUALS = "identify_individuals"
DERIVE_RELATIONSHIPS = "derive_relationships"

_IDENTIFY_SYSTEM = """You are an expert knowledge graph extraction assistant.
Your task is to identify the individuals a text mentions, scoped to an ontology context.

Extract triples in the following JSON format:
{
  "triples": [
    {
      "subject": {"kind": "individual", "id": "...", "label": "...", "class_id": "..."},
      "predicate": {"property_definition_id": "...", "label": "is_a"},
      "object": {"kind": "class", "id": "...", "label": "..."},
      "confidence": 0.95,
      "provenance": {"text_offset_start": 0, "text_offset_end": 10, "raw": "..."}
    }
  ]
}

For each extracted triple, set provenance.raw to an exact, verbatim substring from
the source text (not a paraphrase), and set text_offset_start/text_offset_end to the
best-effort character positions of that substring.

Extract every distinct individual (a concrete named thing, concept, or component)
the text mentions. For each individual, emit exactly one typing triple: subject =
the individual, predicate.label = "is_a", object = the ontology class it belongs to.
For an "is_a" triple, object.kind must be "class" and object.label MUST be one of
the class references listed in the prompt, copied EXACTLY (do not invent, rename,
pluralize, or reformat class references). Every distinct individual the text
mentions MUST appear: when no listed class fits well, still emit the individual,
choosing the CLOSEST listed class rather than omitting it — never drop an
individual for lack of a perfect type. Do NOT emit relationship triples between
individuals in this step.

Return only valid JSON. If no individuals can be extracted, return {"triples": []}."""

_IDENTIFY_USER = """Identify the individuals in the following text, scoped to the ontology
        context provided.

Text:
{text}

{grounding}"""

_DERIVE_SYSTEM = """You are an expert knowledge graph extraction assistant.
Your task is to state the relationships a text asserts between a fixed set of
already-identified individuals.

Extract relationship triples in the following JSON format:
{
  "triples": [
    {
      "subject": {"kind": "individual", "id": "...", "label": "..."},
      "predicate": {"property_definition_id": "...", "label": "..."},
      "object": {"kind": "individual", "id": "...", "label": "..."},
      "confidence": 0.95,
      "provenance": {"text_offset_start": 0, "text_offset_end": 10, "raw": "..."}
    }
  ]
}

For each relationship triple, set provenance.raw to an exact, verbatim substring that
evidences the relationship (typically spanning both entities and the connecting clause,
not just a single entity mention), and set text_offset_start/text_offset_end to the
best-effort character positions of that substring.

Use one of the individuals listed in the prompt as the SUBJECT of each relationship,
copying its label EXACTLY. The OBJECT may be one of the listed individuals OR a new
concept, quality, or outcome the text names as what the subject relates to (for example
an abstract quality such as "readability", "loose coupling", or "duplication") — many
relationships point at such concepts even though they are not concrete typeable
entities. When the object is a new concept, set object.kind to "individual" and give it
a concise label taken from the text; never introduce a new SUBJECT this way. Emit a
relationship only when the text states one. Do NOT emit typing ("is_a") triples in this
step. {predicate_instruction}

Return only valid JSON. If no relationships can be extracted, return {"triples": []}."""

_DERIVE_USER = """State the relationships the following text asserts, scoped to the
        ontology context provided. Each relationship's subject is one of the identified
        individuals; its object is either another identified individual or a new concept
        the text names as the relationship's target.

Text:
{text}

Ontology: {ontology}

Identified individuals:
{individuals}{allowed}"""

INDIVIDUAL_EXTRACTION_STAGES: tuple[StageDefinition, ...] = (
    StageDefinition(
        key=IDENTIFY_INDIVIDUALS,
        label="Identify individuals",
        description=(
            "Pass 1: lists every individual the text mentions and types each one "
            "against the ontology's classes."
        ),
        placeholders={
            "text": "The source text",
            "grounding": (
                "The ontology title and, when it has classes, the class catalog "
                "relevant to the text"
            ),
        },
        default=StagePrompt(system=_IDENTIFY_SYSTEM, user=_IDENTIFY_USER),
    ),
    StageDefinition(
        key=DERIVE_RELATIONSHIPS,
        label="Derive relationships",
        description=(
            "Pass 2: states the relationships the text asserts between the "
            "identified individuals, using the predicates the ontology allows."
        ),
        placeholders={
            "predicate_instruction": (
                "(system prompt) How to choose predicate.label: from the subject "
                "class's predicates, from the ontology's predicates, or free-form "
                "when the ontology defines none"
            ),
            "text": "The source text",
            "ontology": "The ontology title",
            "individuals": "The identified individuals, one per line with their class",
            "allowed": "The allowed predicates block (empty when the ontology defines none)",
        },
        default=StagePrompt(system=_DERIVE_SYSTEM, user=_DERIVE_USER),
    ),
)
