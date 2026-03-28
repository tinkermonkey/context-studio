"""
NLP gap-filling layer (Layer 2).

Fills gaps in entity extraction using NLP processors to catch entities
missed by prior layers.
"""
from domain.extraction.entities import ExtractedEntity
from domain.extraction.ports import NLPProcessor
from domain.extraction.value_objects import LayerInput, LayerOutput


def execute(input: LayerInput, nlp: NLPProcessor) -> LayerOutput:
    """
    Extract entities using NLP processing.

    Uses a trained NLP model to identify named entities, filtering out
    those already found in previous layers.

    Args:
        input: LayerInput containing text and prior extraction context
        nlp: NLPProcessor port for NLP analysis

    Returns:
        LayerOutput containing entities found by NLP but not in prior layers
    """
    entities: list[ExtractedEntity] = []

    if not input.text or not input.text.strip():
        return LayerOutput(entities=entities, metadata={"reason": "empty_text"})

    # Check if NLP processor is ready
    if not nlp.is_ready():
        return LayerOutput(
            entities=[],
            metadata={"reason": "nlp_processor_not_ready"},
        )

    # Extract entities using NLP
    nlp_entities = nlp.extract_entities(input.text)

    # Get set of already extracted entity texts (normalized)
    existing_labels = {e.label.lower().strip() for e in input.existing_entities}

    # Convert NLP entities to our domain model
    for nlp_entity in nlp_entities:
        # Skip if already extracted in prior layers
        if nlp_entity.text.lower().strip() in existing_labels:
            continue

        extracted = ExtractedEntity(
            label=nlp_entity.text.strip(),
            entity_type=nlp_entity.label,  # spaCy label
            source_layer=2,
            # Use 0.75 default for NLP extraction - represents typical reliability
            # of en_core_web_sm model for general entity recognition
            confidence=getattr(nlp_entity, "confidence", 0.75),
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
