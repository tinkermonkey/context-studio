"""
Default stage prompts for LLM individual extraction (ExtractionService.extract_triples).

Pass 1 identifies and types the individuals a text mentions; pass 2 derives
the relationships between them. A pipeline configuration can override either
through ``stage_prompts``; see domain/pipelines/stage_prompts.py.

The find-then-type shape (domain/extraction/find_then_type.py) has stages of
its own for pass 1: one finds what a text mentions without typing it, one
types each mention against the ontology's whole class catalog. Its
relationships are pass 2, unchanged.

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

FIND_MENTIONS = "find_mentions"
TYPE_MENTION = "type_mention"

_FIND_SYSTEM = """You are an expert knowledge graph extraction assistant.
Your task is to list what a text mentions that a model of its subject would record.
You do not classify anything: a later step does that.

List two kinds of element:
- "thing": something the text names. Use the name the text uses.
- "statement": something the text asserts about its subject or the people behind it:
  a goal, a requirement, a principle, a constraint, a reason, a finding or an outcome.
  Name it with a paraphrase of at most ten words.

Be exhaustive: include what is named only once, in a table, a list or a diagram.
Leave out what the text only refers to and does not describe as part of its subject:
other works it cites or compares itself with, press coverage, link lists and navigation.

For each element give a quote: the exact words of the text, at most 300 characters,
that say what the element is or that state it. Copy the quote verbatim from the text;
never paraphrase it.

Return only valid JSON in this format:
{"mentions": [{"name": "...", "kind": "thing", "quote": "..."}]}
If the text mentions nothing to record, return {"mentions": []}."""

_FIND_USER = """List the elements the following text mentions, for a model in the
ontology described below.

{grounding}

Text:
{text}"""

_TYPE_SYSTEM = """You are an expert knowledge graph extraction assistant.
Your task is to type one candidate element against the classes of an ontology: to say
which one class it is an instance of, as the text describes it.

{catalog}

You are given a passage of a text and one candidate found in it. Choose the one class
listed above that best fits what the candidate is, as the text describes it. Judge by
the class definitions, not by the class names. Answer "none" when the candidate is not
something a model in this ontology would record: something the text only cites or
compares itself with, a passing example, a generic term, or a repeat of a heading.

Return only valid JSON in one of these two formats:
{"class": "<a class reference from the list, copied exactly>", "confidence": 0.9}
{"class": "none", "confidence": 0.9}
confidence is how sure you are of the answer, from 0 to 1."""

_TYPE_USER = """Text:
{context}

Candidate: {name}
The text says of it: {quote}"""

FIND_THEN_TYPE_STAGES: tuple[StageDefinition, ...] = (
    StageDefinition(
        key=FIND_MENTIONS,
        label="Find mentions",
        description=(
            "Lists what the text mentions (named things, and statements such as goals "
            "and requirements) with the passage for each, without typing anything."
        ),
        placeholders={
            "text": "The source text",
            "grounding": "The ontology title and the kinds of element it records",
        },
        default=StagePrompt(system=_FIND_SYSTEM, user=_FIND_USER),
    ),
    StageDefinition(
        key=TYPE_MENTION,
        label="Type a mention",
        description=(
            "Types one mention against the ontology's whole class catalog, with "
            "definitions: one class, or none when it is not something to record. Asked "
            "once per distinct mention, with the same system prompt each time."
        ),
        placeholders={
            "catalog": (
                "(system prompt) The ontology title and every class: reference, title, "
                "kind and definition"
            ),
            "context": "The text around the mention's first passage",
            "name": "The mention's name",
            "quote": "The passage the mention was found in",
        },
        default=StagePrompt(system=_TYPE_SYSTEM, user=_TYPE_USER),
    ),
    next(stage for stage in INDIVIDUAL_EXTRACTION_STAGES if stage.key == DERIVE_RELATIONSHIPS),
)
