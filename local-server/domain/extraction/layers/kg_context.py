"""
Knowledge Graph context extraction layer (Layer 0).

Extracts entities and relationships from the existing knowledge graph
to provide context for subsequent extraction layers.
"""
from domain.extraction.entities import ExtractedEntity
from domain.extraction.value_objects import LayerOutput


def execute(text: str, ontology_repo, embedding_service) -> LayerOutput:
    """
    Extract entity mentions from existing knowledge graph.

    This layer searches the ontology repository for classes and individuals
    that are relevant to the input text, using semantic similarity to find
    matches.

    Args:
        text: The source text to extract from
        ontology_repo: OntologyRepository port for querying existing entities
        embedding_service: EmbeddingService port for semantic similarity

    Returns:
        LayerOutput containing entities found in the knowledge graph
    """
    entities: list[ExtractedEntity] = []

    if not text or not text.strip():
        return LayerOutput(entities=entities, metadata={"reason": "empty_text"})

    try:
        # Get embedding for the input text
        text_embedding = embedding_service.embed(text.strip())

        # Retrieve all classes from the ontology
        all_entities = ontology_repo.get_all_entities_and_relationships()

        if not all_entities:
            return LayerOutput(entities=entities, metadata={"reason": "no_entities_in_repo"})

        entities_dict, _ = all_entities

        # Search for semantically similar entities
        matches_found = 0
        for entity_id, entity_data in entities_dict.items():
            entity_embedding = entity_data.get("embedding")
            if not entity_embedding:
                continue

            # Compute similarity
            similarity = embedding_service.similarity(text_embedding, entity_embedding)

            # Use similarity threshold of 0.7 for KG context
            if similarity >= 0.7:
                entity_label = entity_data.get("title", "")
                entity_type = entity_data.get("node_type", "unknown")
                entity_uri = entity_data.get("external_references", [{}])[0].get("uri")

                extracted = ExtractedEntity(
                    label=entity_label,
                    entity_type=entity_type,
                    source_layer=0,
                    confidence=float(similarity),
                    uri=entity_uri,
                    description=entity_data.get("description"),
                    properties={"kg_entity_id": entity_id},
                )
                entities.append(extracted)
                matches_found += 1

        return LayerOutput(
            entities=entities,
            metadata={
                "matches_found": matches_found,
                "threshold": 0.7,
                "entities_checked": len(entities_dict),
            },
        )

    except Exception as exc:
        # Layer error does not prevent subsequent layers from executing
        # Return empty output but with metadata about the error
        return LayerOutput(
            entities=[],
            metadata={"error": str(exc), "error_type": type(exc).__name__},
        )
