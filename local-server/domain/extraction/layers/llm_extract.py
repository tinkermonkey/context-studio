"""
LLM extraction layer (Layer 1).

Extracts entities using prompts sent to language models.
"""
import json

from domain.extraction.entities import ExtractedEntity
from domain.extraction.ports import LLMProvider
from domain.extraction.value_objects import LayerInput, LayerOutput


def execute(input: LayerInput, llm: LLMProvider) -> LayerOutput:
    """
    Extract entities using an LLM.

    Prompts the LLM to identify entities in the input text and return
    them as structured JSON.

    Args:
        input: LayerInput containing text and prior extraction context
        llm: LLMProvider port for text generation

    Returns:
        LayerOutput containing entities identified by the LLM
    """
    entities: list[ExtractedEntity] = []

    if not input.text or not input.text.strip():
        return LayerOutput(entities=entities, metadata={"reason": "empty_text"})

    # Check if LLM is available
    available_models = llm.list_available_models()
    if not available_models:
        return LayerOutput(
            entities=[],
            metadata={"reason": "no_models_available"},
        )

    model = available_models[0]  # Use first available model

    # Build prompt with context from previous layers
    existing_entity_labels = [e.label for e in input.existing_entities]
    context_str = (
        f"\nAlready extracted: {', '.join(existing_entity_labels)}"
        if existing_entity_labels
        else ""
    )

    system_prompt = """You are an expert knowledge extraction assistant.
Extract named entities from the provided text and return them as a JSON array.
Each entity should have: label, type, confidence (0.0-1.0), optional uri, optional description."""

    user_prompt = f"""Extract entities from this text:{context_str}

Text:
{input.text}

Return a JSON array with entity objects. Example:
[
  {{"label": "John", "type": "PERSON", "confidence": 0.95, "uri": null, "description": null}},
  {{"label": "Google", "type": "ORGANIZATION", "confidence": 0.90, "uri": "https://example.com", "description": "Tech company"}}
]

JSON Array:"""

    response = llm.complete(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
        temperature=0.3,
        max_tokens=2000,
        response_format=None,
    )

    # Parse LLM response
    response_text = response.content.strip()

    # Try to extract JSON array from response using proper bracket matching
    json_match = None
    if "[" in response_text:
        start_idx = response_text.index("[")
        # Find matching closing bracket by counting bracket depth
        bracket_count = 0
        end_idx = None
        for i in range(start_idx, len(response_text)):
            if response_text[i] == "[":
                bracket_count += 1
            elif response_text[i] == "]":
                bracket_count -= 1
                if bracket_count == 0:
                    end_idx = i + 1
                    break

        if end_idx is not None:
            json_match = response_text[start_idx:end_idx]

    if json_match:
        try:
            entity_list = json.loads(json_match)
            for item in entity_list:
                if isinstance(item, dict) and "label" in item:
                    extracted = ExtractedEntity(
                        label=item.get("label", "").strip(),
                        entity_type=item.get("type", "UNKNOWN"),
                        source_layer=1,
                        confidence=float(item.get("confidence", 0.5)),
                        uri=item.get("uri"),
                        description=item.get("description"),
                    )
                    if extracted.label:  # Only add if label is non-empty
                        entities.append(extracted)
        except (json.JSONDecodeError, ValueError):
            # Invalid JSON found - return empty entities
            pass

    return LayerOutput(
        entities=entities,
        metadata={
            "model": model,
            "tokens_in": response.tokens_in,
            "tokens_out": response.tokens_out,
            "finish_reason": response.finish_reason,
        },
    )
