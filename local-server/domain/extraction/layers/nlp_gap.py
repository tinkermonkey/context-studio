"""
NLP gap-filling layer (Layer 2).

Fills gaps in entity extraction using NLP processors to catch entities
missed by prior layers.
"""
from domain.extraction.entities import ExtractedEntity
from domain.extraction.exceptions import NLPProcessorNotReadyError
from domain.extraction.ports import NLPProcessor
from domain.extraction.value_objects import LayerInput, LayerOutput


def execute(input: LayerInput, nlp: NLPProcessor) -> LayerOutput:
    """
    Extract entities using NLP processing (Layer 2).

    Uses a trained NLP model to identify named entities, filtering out
    those already found in previous layers. Raises an exception if the
    NLP processor is not available, ensuring the error is logged and
    reported distinctly from "no entities found".

    Args:
        input: LayerInput containing text and prior extraction context
        nlp: NLPProcessor port for NLP analysis

    Returns:
        LayerOutput containing entities found by NLP but not in prior layers

    Raises:
        NLPProcessorNotReadyError: If the NLP processor model is not installed
            or initialization failed. This is raised (not returned as empty
            success) to distinguish from "text contains no named entities".
    """
    entities: list[ExtractedEntity] = []

    if not input.text or not input.text.strip():
        return LayerOutput(entities=entities, metadata={"reason": "empty_text"})

    # Check if NLP processor is ready before attempting extraction
    # If not ready, raise an exception (not return empty result) so the caller
    # can distinguish this error from "no entities found in text"
    if not nlp.is_ready():
        raise NLPProcessorNotReadyError(
            "NLP processor is not ready. Model may not be installed or initialization failed."
        )

    # Extract entities using NLP
    # Uses the adapter-provided confidence scores (typically from spaCy or similar)
    nlp_entities = nlp.extract_entities(input.text)

    # Get set of already extracted entity texts (normalized for comparison)
    existing_labels = {e.label.lower().strip() for e in input.existing_entities}

    # Convert NLP entities to our domain model, filtering out duplicates from prior layers
    for nlp_entity in nlp_entities:
        # Skip if already extracted in prior layers
        if nlp_entity.text.lower().strip() in existing_labels:
            continue

        extracted = ExtractedEntity(
            label=nlp_entity.text.strip(),
            entity_type=nlp_entity.label,  # Entity type from NLP processor (e.g., 'PERSON', 'ORG')
            source_layer=2,  # Layer 2 = NLP gap-filling
            confidence=nlp_entity.confidence,  # Use adapter-provided confidence score
            uri=nlp_entity.linked_uri,
            properties={
                "char_offset_start": nlp_entity.start,
                "char_offset_end": nlp_entity.end,
            },
        )
        entities.append(extracted)

    return LayerOutput(
        entities=entities,
        metadata={
            "nlp_entities_found": len(nlp_entities),
            "duplicates_skipped": len(nlp_entities) - len(entities),
            "processor_ready": True,
        },
    )
