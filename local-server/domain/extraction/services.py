"""
Business logic service for the Knowledge Extraction bounded context.

ExtractionService orchestrates four extraction layers sequentially, deduplicates
results, and emits domain events. It depends on port interfaces for repositories,
embedding services, LLM providers, NLP processors, and reference sources.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from uuid import uuid4

from domain.ports import EventPublisher
from . import layers
from .entities import ExtractedEntity, ExtractionResult
from .events import ExtractionCompleted
from .exceptions import ExtractionError
from .ports import LLMProvider, NLPProcessor, ReferenceSource
from .value_objects import ExtractionLayerResult, LayerInput, LayerOutput


class ExtractionService:
    """
    Service implementing knowledge extraction orchestration.

    This service:
    1. Coordinates four extraction layers (KG context, LLM, NLP, reference)
    2. Passes forward-output between layers for context
    3. Recovers from individual layer failures
    4. Deduplicates entities across layers
    5. Emits domain events on completion
    """

    # Deduplication priority: higher source_layer values deprioritized
    # Priority order: 1 > 0 > 2 > 3
    DEDUP_PRIORITY = {1: 0, 0: 1, 2: 2, 3: 3}
    SIMILARITY_THRESHOLD = 0.85

    def __init__(
        self,
        ontology_repo,
        embedding_service,
        llm: LLMProvider,
        nlp: NLPProcessor,
        reference_sources: list[ReferenceSource],
        event_publisher: EventPublisher,
    ) -> None:
        """
        Initialize the service with port dependencies.

        Args:
            ontology_repo: Port for querying the knowledge graph
            embedding_service: Port for semantic embeddings
            llm: Port for LLM completions
            nlp: Port for NLP processing
            reference_sources: List of reference source ports
            event_publisher: Port for publishing domain events
        """
        self._ontology_repo = ontology_repo
        self._embedding_service = embedding_service
        self._llm = llm
        self._nlp = nlp
        self._reference_sources = reference_sources
        self._event_publisher = event_publisher

    def extract(self, text: str) -> ExtractionResult:
        """
        Extract entities from text through four coordinated layers.

        Layers execute sequentially:
        - Layer 0: Knowledge graph context (uses embedding similarity)
        - Layer 1: LLM extraction (structured JSON output)
        - Layer 2: NLP gap-filling (catches missed entities)
        - Layer 3: Reference source enrichment (adds URIs and metadata)

        If a single layer fails, its error is recorded but subsequent layers
        continue executing.

        Args:
            text: Source text to extract entities from

        Returns:
            ExtractionResult containing deduplicated entities and layer metadata

        Raises:
            ExtractionError: If all layers fail or text validation fails
        """
        if not text or not text.strip():
            raise ExtractionError("Text cannot be empty")

        result_id = str(uuid4())
        start_time = time.time()
        layers_executed: list[ExtractionLayerResult] = []
        all_entities: list[ExtractedEntity] = []

        # Layer 0: Knowledge graph context
        layer_0_output = self._execute_layer(
            layer_num=0,
            layer_name="Knowledge Graph Context",
            layer_fn=lambda: layers.kg_context.execute(
                text=text,
                ontology_repo=self._ontology_repo,
                embedding_service=self._embedding_service,
            ),
            layers_executed=layers_executed,
        )
        all_entities.extend(layer_0_output.entities)

        # Layer 1: LLM extraction
        layer_1_input = LayerInput(
            text=text,
            existing_entities=all_entities.copy(),
            kg_context=layer_0_output.entities,
        )
        layer_1_output = self._execute_layer(
            layer_num=1,
            layer_name="LLM Extraction",
            layer_fn=lambda: layers.llm_extract.execute(
                input=layer_1_input,
                llm=self._llm,
            ),
            layers_executed=layers_executed,
        )
        all_entities.extend(layer_1_output.entities)

        # Layer 2: NLP gap-filling
        layer_2_input = LayerInput(
            text=text,
            existing_entities=all_entities.copy(),
            kg_context=layer_0_output.entities,
        )
        layer_2_output = self._execute_layer(
            layer_num=2,
            layer_name="NLP Gap-Filling",
            layer_fn=lambda: layers.nlp_gap.execute(
                input=layer_2_input,
                nlp=self._nlp,
            ),
            layers_executed=layers_executed,
        )
        all_entities.extend(layer_2_output.entities)

        # Layer 3: Reference source enrichment
        layer_3_input = LayerInput(
            text=text,
            existing_entities=all_entities.copy(),
            kg_context=layer_0_output.entities,
        )
        layer_3_output = self._execute_layer(
            layer_num=3,
            layer_name="Reference Source Enrichment",
            layer_fn=lambda: layers.reference.execute(
                input=layer_3_input,
                sources=self._reference_sources,
            ),
            layers_executed=layers_executed,
        )
        all_entities.extend(layer_3_output.entities)

        # Deduplicate entities across layers
        deduplicated = self._deduplicate(all_entities)

        # Check if no entities were extracted across all layers
        if not deduplicated:
            raise ExtractionError("All extraction layers failed to extract entities")

        # Calculate execution time
        duration_ms = int((time.time() - start_time) * 1000)

        # Create result
        result = ExtractionResult(
            id=result_id,
            text=text,
            extracted_entities=deduplicated,
            layers_executed=layers_executed,
            total_duration_ms=duration_ms,
            created_at=datetime.now(timezone.utc),
        )

        # Publish completion event
        self._event_publisher.publish(ExtractionCompleted(
            result_id=result_id,
            entity_count=len(deduplicated),
            duration_ms=duration_ms,
        ))

        return result

    def _execute_layer(
        self,
        layer_num: int,
        layer_name: str,
        layer_fn,
        layers_executed: list[ExtractionLayerResult],
    ) -> LayerOutput:
        """
        Execute a single extraction layer with error isolation.

        If the layer raises an exception, it is caught, logged in metadata,
        and an empty LayerOutput is returned. The layer is still recorded
        in layers_executed with success=False.

        Args:
            layer_num: Layer index (0–3)
            layer_name: Human-readable layer name
            layer_fn: Callable returning LayerOutput
            layers_executed: List to append execution metadata to

        Returns:
            LayerOutput from the layer, or empty output if layer failed
        """
        layer_start = time.time()

        try:
            output = layer_fn()
            duration_ms = int((time.time() - layer_start) * 1000)

            layers_executed.append(ExtractionLayerResult(
                layer_number=layer_num,
                layer_name=layer_name,
                entities_found=len(output.entities),
                duration_ms=duration_ms,
                success=True,
            ))

            return output

        except Exception as exc:
            duration_ms = int((time.time() - layer_start) * 1000)

            layers_executed.append(ExtractionLayerResult(
                layer_number=layer_num,
                layer_name=layer_name,
                entities_found=0,
                duration_ms=duration_ms,
                success=False,
                error_message=str(exc),
            ))

            # Return empty output so subsequent layers can continue
            return LayerOutput(entities=[], metadata={"error": str(exc)})

    def _deduplicate(self, entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
        """
        Deduplicate entities across layers using ID and string similarity.

        Deduplication rules:
        1. Sort by priority: source_layer 1 > 0 > 2 > 3
        2. Group entities by ID first (exact match) - entities with same ID are same entity
        3. Then group entities with normalized labels matching >= 0.85 similarity
        4. Keep the highest-priority entity in each group
        5. Return deduplicated entities sorted by priority

        Args:
            entities: Unfiltered list of entities from all layers

        Returns:
            Deduplicated list of entities
        """
        if not entities:
            return []

        if len(entities) == 1:
            return entities

        # Sort by priority (lower value = higher priority)
        sorted_entities = sorted(
            entities,
            key=lambda e: self.DEDUP_PRIORITY.get(e.source_layer, 999),
        )

        deduplicated: list[ExtractedEntity] = []
        used_indices: set[int] = set()

        for i, entity in enumerate(sorted_entities):
            if i in used_indices:
                continue

            # Find all entities duplicated with this one
            used_indices.add(i)

            for j in range(i + 1, len(sorted_entities)):
                if j in used_indices:
                    continue

                other = sorted_entities[j]

                # First check: same ID means same entity
                if entity.id == other.id:
                    used_indices.add(j)
                    continue

                # Second check: label similarity for cross-layer matches
                label_similarity = self._normalized_similarity(entity.label, other.label)

                if label_similarity >= self.SIMILARITY_THRESHOLD:
                    # Mark as duplicate of current entity (higher priority)
                    used_indices.add(j)

            # Keep the highest-priority entity from the group
            deduplicated.append(entity)

        return deduplicated

    def _normalized_similarity(self, label_a: str, label_b: str) -> float:
        """
        Compute normalized string similarity between two labels.

        Uses case-insensitive comparison with Levenshtein distance normalization.

        Args:
            label_a: First label
            label_b: Second label

        Returns:
            Similarity score from 0.0 to 1.0
        """
        # Normalize: lowercase and strip whitespace
        a = label_a.lower().strip()
        b = label_b.lower().strip()

        # Exact match
        if a == b:
            return 1.0

        # Empty strings
        if not a or not b:
            return 0.0

        # Levenshtein distance normalization
        max_len = max(len(a), len(b))
        distance = self._levenshtein_distance(a, b)
        similarity = 1.0 - (distance / max_len)

        return max(0.0, similarity)

    @staticmethod
    def _levenshtein_distance(s1: str, s2: str) -> int:
        """
        Calculate Levenshtein distance between two strings.

        Args:
            s1: First string
            s2: Second string

        Returns:
            Minimum edit distance
        """
        if len(s1) < len(s2):
            return ExtractionService._levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row: list[int] = list(range(len(s2) + 1))

        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                # j+1 instead of j since previous_row and current_row are one character longer
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]
