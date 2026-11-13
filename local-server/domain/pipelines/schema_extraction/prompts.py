"""
Default stage prompts for the LLM schema extraction pipeline ("default" implementation),
in the order the stages run.

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
        key="placement",
        label="Placement",
        description=(
            "Places each candidate under an existing class or another candidate, and marks"
            " measurements and other values as attributes of a class instead of classes."
        ),
        placeholders={
            "existing_classes": (
                "The taxonomy's classes, one per line: title and a one-line description"
                ' (titles only past the first ones); "(none)" without a taxonomy'
            ),
            "candidates": "The candidates, one per line: label and definition",
            "value_types": "The attribute value types, comma-separated",
        },
        default=StagePrompt(
            system=(
                "You are an expert in ontology design. You place new candidate terms into an "
                "existing class hierarchy. A class is a kind of thing, person, place, process "
                "or event whose instances can be told apart. An attribute is a measurement, "
                "quantity, rating, setting, date, identifier or other value that describes "
                "the instances of a class. Return only a JSON object."
            ),
            user=(
                "Existing classes:\n{existing_classes}\n\n"
                "Candidates:\n{candidates}\n\n"
                "For each candidate decide its role.\n"
                '- role "class": give its parent, the most specific existing class or other '
                "candidate that it is a kind of, by its exact title; null when none fits. "
                "A parent is never the candidate itself, nor something it is only a part of, "
                "located in or used with.\n"
                '- role "attribute" (such as voltage, current, humidity, temperature, '
                "capacity, a rating, a date or a model number): give the class whose "
                "instances it describes, an existing class or a candidate, by its exact "
                "title; its value_type, one of {value_types}; and its unit, such as "
                '"V" or "%", or null.\n\n'
                "Return JSON:\n"
                "{\n"
                '  "placements": [\n'
                '    {"label": "Candidate1", "role": "class", "parent": "Existing Class"},\n'
                '    {"label": "Candidate2", "role": "attribute", "of": "Candidate1", '
                '"value_type": "number", "unit": "V"}\n'
                "  ]\n"
                "}"
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
                "Senses are different KINDS of thing, each its own class under a different "
                "parent, as 'bank' names both a financial institution and the side of a river. "
                "These are one sense, not several: the same thing in different roles, uses, "
                "states or conditions (existing or replacement, working or faulty, standalone "
                "or paired with something), a general concept and a particular instance of it, "
                "and an activity and its result when the text treats them as one idea. "
                "If two senses would sit under the same parent class, or one is a state, role "
                "or use of the other, the term has one sense. "
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
