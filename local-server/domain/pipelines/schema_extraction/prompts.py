"""
Default stage prompts for the LLM schema extraction pipeline ("default" implementation).

A configuration can override any of them through ``stage_prompts``; see
domain/pipelines/stage_prompts.py. The defaults render byte-identical to the
prompts recorded in the quality-test cassettes, so changing a default
invalidates those recordings.
"""

from domain.pipelines.stage_prompts import StageDefinition, StagePrompt

_CONTEXT = "The first 3000 characters of the normalized source text"

SCHEMA_EXTRACTION_STAGES: tuple[StageDefinition, ...] = (
    StageDefinition(
        key="candidate_identification",
        label="Candidate identification",
        description="Lists candidate class labels in each chunk of the text (one call per chunk).",
        placeholders={"chunk": "One chunk of the source text"},
        default=StagePrompt(
            system=(
                "You are an expert in ontology design and schema extraction. "
                "Extract candidate classes and key terms from the text. "
                "Return a JSON array of candidate labels. "
                "Be precise and extract technical/domain terms, not generic words."
            ),
            user=(
                "Extract candidate classes and technical terms from this text:\n\n{chunk}\n\n"
                "Return a JSON array of strings (labels only). "
                'Example: ["Microservice", "Message Queue", "API Gateway"]'
            ),
        ),
    ),
    StageDefinition(
        key="definition_synthesis",
        label="Definition synthesis",
        description="Writes a definition for every candidate class in one call.",
        placeholders={
            "labels": 'The candidate labels, quoted and comma-separated ("A", "B")',
            "context": _CONTEXT,
            "example": 'The first two labels as JSON entries ("A": "definition...")',
        },
        default=StagePrompt(
            system=(
                "You are an expert in ontology definition writing. "
                "Return a JSON object mapping each label to its definition (1-2 sentences). "
                "Only output the JSON object, nothing else."
            ),
            user=(
                "Define these classes for a technical ontology.\n\n"
                "Labels: {labels}\n\n"
                "Context: {context}\n\n"
                "Return JSON: {{example}, ...}"
            ),
        ),
    ),
    StageDefinition(
        key="connection_proposal",
        label="Connection proposal",
        description="Proposes relationships and properties between the candidate classes.",
        placeholders={
            "classes": "The candidate labels, comma-separated",
            "context": _CONTEXT,
        },
        default=StagePrompt(
            system=(
                "You are an expert in ontology design. "
                "Identify relationships and properties between the given classes. "
                'Return a JSON object with "relationships" and "properties" arrays.'
            ),
            user=(
                "For these candidate classes, identify relationships and properties:\n\n"
                "Classes: {classes}\n\n"
                "Context: {context}\n\n"
                "Return JSON:\n"
                "{\n"
                '  "relationships": [\n'
                '    {"subject": "Class1", "predicate": "subclass_of", '
                '"object": "Class2", "confidence": 0.8},\n'
                "    ...\n"
                "  ],\n"
                '  "properties": [\n'
                '    {"name": "Property1", "domain": "Class1", '
                '"range": "Class2", "confidence": 0.7},\n'
                "    ...\n"
                "  ]\n"
                "}"
            ),
        ),
    ),
    StageDefinition(
        key="disambiguation",
        label="Disambiguation",
        description=(
            "Splits a term into senses only when the text uses it in more than one, "
            "with a quote for each."
        ),
        placeholders={
            "terms": "The candidate labels, comma-separated",
            "context": _CONTEXT,
        },
        default=StagePrompt(
            system=(
                "You are an expert in word sense disambiguation for ontology design. "
                "Report only terms that the given text itself uses in MORE THAN ONE distinct "
                "sense. Ignore senses that do not occur in the text, such as everyday or "
                "dictionary meanings unrelated to its subject, and categories or roles the "
                "term could belong to. "
                "Every sense needs a quote: a short passage copied word for word from the "
                "text that contains the term used in that sense. Each sense's quote must be "
                "a different passage. A sense you cannot quote is not used in the text. "
                "Return a JSON object with ambiguous terms and their senses."
            ),
            user=(
                "Check these terms for multiple senses used in the text:\n\n"
                "Terms: {terms}\n\n"
                "Context: {context}\n\n"
                "Most terms have a single sense in the text; return an empty list then.\n"
                "Return JSON:\n"
                "{\n"
                '  "ambiguous_terms": [\n'
                '    {"term": "Term1", "rationale": "Why the text uses it in several senses",\n'
                '     "senses": [\n'
                '       {"qualifier": "1-3 word sense name", "definition": "One-sentence '
                'definition of this sense", "quote": "Verbatim words from the text using '
                'the term in this sense"}\n'
                "     ]}\n"
                "  ]\n"
                "}"
            ),
        ),
    ),
)
