"""
Business logic service for the Knowledge Extraction bounded context.

ExtractionService orchestrates four extraction layers sequentially, deduplicates
results, and emits domain events. It depends on port interfaces for repositories,
embedding services, LLM providers, NLP processors, and reference sources.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from datetime import datetime, timezone
from types import MappingProxyType
from uuid import uuid4

from domain.interchange.services import set_batch_run_context
from domain.ontology.ports import EmbeddingService, OntologyRepository
from domain.pipelines.ports import LLMProvider
from domain.ports import EventPublisher

from . import layers
from .entities import (
    ExtractedEntity,
    ExtractionResult,
    ExtractionRun,
    ExtractionRunStatus,
    TripleExtractionResult,
)
from .events import ExtractionCompleted
from .exceptions import ExtractionError
from .ports import (
    ExtractionRepository,
    ExtractionRunRepository,
    NLPProcessor,
    ReferenceSource,
)
from .value_objects import ExtractionLayerResult, LayerInput, LayerOutput

_logger = logging.getLogger(__name__)


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

    def __init__(
        self,
        ontology_repo: OntologyRepository,
        embedding_service: EmbeddingService,
        llm: LLMProvider,
        nlp: NLPProcessor,
        reference_sources: list[ReferenceSource],
        event_publisher: EventPublisher,
        extraction_repo: ExtractionRepository,
        extraction_run_repo: ExtractionRunRepository,
        similarity_threshold: float = 0.85,
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
            extraction_repo: Port for persisting extraction results
            extraction_run_repo: Port for persisting extraction runs
            similarity_threshold: Threshold for entity label similarity matching (0.0–1.0).
                Defaults to 0.85. Entities with normalized label similarity >= this value
                are considered duplicates.
        """
        if not 0.0 <= similarity_threshold <= 1.0:
            raise ValueError(
                "similarity_threshold must be between 0.0 and 1.0, got" f" {similarity_threshold}"
            )
        self._ontology_repo = ontology_repo
        self._embedding_service = embedding_service
        self._llm = llm
        self._nlp = nlp
        self._reference_sources = reference_sources
        self._event_publisher = event_publisher
        self._extraction_repo = extraction_repo
        self._extraction_run_repo = extraction_run_repo
        self._similarity_threshold = similarity_threshold

    def extract(self, text: str) -> ExtractionResult:
        """
        Extract entities from text through four coordinated layers.

        This is the main use case that orchestrates the full extraction pipeline.
        Layers execute sequentially:
        - Layer 0: Knowledge graph context (uses embedding similarity)
        - Layer 1: LLM extraction (structured JSON output)
        - Layer 2: NLP gap-filling (catches missed entities)
        - Layer 3: Reference source enrichment (adds URIs and metadata)

        If a single layer fails, its error is recorded but subsequent layers
        continue executing. Empty results are valid and do not raise an error;
        they indicate the text contains no entities.

        Args:
            text: Source text to extract entities from

        Returns:
            ExtractionResult containing deduplicated entities and layer metadata
            (may be empty if text contains no entities)

        Raises:
            ExtractionError: If text validation fails
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
            existing_entities=tuple(all_entities.copy()),
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
            existing_entities=tuple(all_entities.copy()),
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
            existing_entities=tuple(all_entities.copy()),
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

        # Empty results are valid—text may legitimately contain no entities
        # Build and return result (with or without entities)
        return self._build_result(
            result_id=result_id,
            text=text,
            deduplicated=deduplicated,
            layers_executed=layers_executed,
            start_time=start_time,
        )

    def analyze_text(self, text: str) -> ExtractionResult:
        """
        Analyze text for linguistic features and named entities.

        This use case focuses on NLP-based analysis including tokenization,
        entity recognition, language detection, and linguistic features.
        It may also provide context from the knowledge graph.

        Args:
            text: Source text to analyze

        Returns:
            ExtractionResult containing analyzed entities and linguistic metadata

        Raises:
            ExtractionError: If text validation fails
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

        # Layer 2: NLP gap-filling (primary for text analysis)
        layer_2_input = LayerInput(
            text=text,
            existing_entities=tuple(all_entities.copy()),
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

        # Deduplicate entities
        deduplicated = self._deduplicate(all_entities)

        # Build and return result
        return self._build_result(
            result_id=result_id,
            text=text,
            deduplicated=deduplicated,
            layers_executed=layers_executed,
            start_time=start_time,
        )

    def enrich_from_references(
        self, text: str, extracted_entities: list[ExtractedEntity]
    ) -> ExtractionResult:
        """
        Enrich extracted entities with external reference knowledge.

        This use case takes already-extracted entities and enriches them with
        URIs, metadata, and relationships from external knowledge sources like
        ConceptNet, DBpedia, Wikidata, and schema.org.

        Args:
            text: Original source text
            extracted_entities: Entities to enrich

        Returns:
            ExtractionResult with enriched entities and reference metadata

        Raises:
            ExtractionError: If text validation fails
        """
        if not text or not text.strip():
            raise ExtractionError("Text cannot be empty")

        result_id = str(uuid4())
        start_time = time.time()
        layers_executed: list[ExtractionLayerResult] = []
        all_entities = extracted_entities.copy()

        # Layer 3: Reference source enrichment
        layer_3_input = LayerInput(
            text=text,
            existing_entities=tuple(all_entities.copy()),
            kg_context=None,
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

        # Deduplicate entities
        deduplicated = self._deduplicate(all_entities)

        # Build and return result
        return self._build_result(
            result_id=result_id,
            text=text,
            deduplicated=deduplicated,
            layers_executed=layers_executed,
            start_time=start_time,
        )

    def extract_triples(
        self,
        text: str,
        ontology_id: str,
        model: str,
        temperature: float,
    ) -> TripleExtractionResult:
        """
        Extract RDF triples from text, scoped to a specific ontology.

        This method uses an LLM to extract subject-predicate-object triples
        from the input text, linking them to classes and individuals from a
        specific ontology. Each triple is returned with confidence and provenance.

        Args:
            text: Source text to extract triples from
            ontology_id: ID of the target ontology
            model: LLM model name (e.g., 'gpt-4', 'claude-opus')
            temperature: Sampling temperature (0.0–2.0)

        Returns:
            Dictionary with keys:
                - triples: list of extracted triples
                - warnings: list of warnings or validation issues
                - metadata: extraction metadata (model, tokens_used, duration_ms)

        Raises:
            ExtractionError: If text validation fails
            ValueError: If ontology_id not found
        """
        if not text or not text.strip():
            raise ExtractionError("Text cannot be empty")
        if not 0.0 <= temperature <= 2.0:
            raise ValueError(f"temperature must be 0.0–2.0, got {temperature}")

        # Create extraction run record
        run_id = str(uuid4())
        text_hash = hashlib.sha256(text.encode()).hexdigest()

        run = ExtractionRun.create(
            id=run_id,
            source_document_uri=None,
            source_text_hash=text_hash,
            pipeline_config_ref="extraction-default",
            model=model,
            temperature=temperature,
        )

        # Save initial run record
        self._extraction_run_repo.save_extraction_run(run)

        # Set correlation context so change events are linked to this extraction run
        set_batch_run_context(run_id)

        start_time = time.time()
        triples_extracted = 0
        triples_committed = 0
        warnings = []
        tokens_used = 0
        run_status = ExtractionRunStatus.COMPLETED

        try:
            try:
                # Get ontology to validate it exists
                ontology = self._ontology_repo.get_taxonomy(ontology_id)
                if not ontology:
                    raise ValueError(f"Ontology {ontology_id} not found")

                # Call LLM to extract triples
                system_prompt, user_prompt = self._build_triple_extraction_prompt(text, ontology)
                llm_response = self._llm.complete(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=model,
                    temperature=temperature,
                    max_tokens=8000,
                    response_format="json",
                )
                tokens_used = llm_response.tokens_in + llm_response.tokens_out

                # Parse LLM response
                extracted_triples = self._parse_triple_extraction_response(
                    llm_response.content, text, ontology_id
                )
                triples_extracted = len(extracted_triples)
                triples_committed = triples_extracted

            except Exception as exc:
                _logger.error(f"Triple extraction failed: {exc}", exc_info=exc)
                tokens_used = 0
                extracted_triples = []
                run_status = ExtractionRunStatus.FAILED
                warnings.append(f"Extraction failed: {str(exc)}")

            # Update run record
            duration_ms = int((time.time() - start_time) * 1000)
            run = ExtractionRun(
                id=run.id,
                source_document_uri=run.source_document_uri,
                source_text_hash=run.source_text_hash,
                pipeline_config_ref=run.pipeline_config_ref,
                model=run.model,
                temperature=run.temperature,
                tokens_used=tokens_used,
                duration_ms=duration_ms,
                triples_extracted=triples_extracted,
                triples_committed=triples_committed,
                status=run_status,
            )

            self._extraction_run_repo.update_extraction_run(run)

            # Publish completion event only on successful extraction
            # (with batch_run_id still in context for change event recording)
            if run_status == ExtractionRunStatus.COMPLETED:
                failures = self._event_publisher.publish(
                    ExtractionCompleted(
                        result_id=run_id,
                        entity_count=triples_extracted,
                        duration_ms=duration_ms,
                    )
                )
                if failures:
                    handler_names = ", ".join(name for name, _ in failures)
                    _logger.warning(
                        "Event handlers failed for ExtractionCompleted (result_id=%s): %s. "
                        "Extraction result is returned but audit trail may have gaps.",
                        run_id,
                        handler_names,
                    )

        finally:
            # Always clear the correlation context after extraction
            set_batch_run_context(None)

        return TripleExtractionResult(
            triples=extracted_triples,
            warnings=warnings,
            metadata={
                "model": model,
                "tokens_used": tokens_used,
                "duration_ms": duration_ms,
            },
        )

    def _build_triple_extraction_prompt(self, text: str, ontology) -> tuple[str, str]:
        """
        Build system and user prompts for LLM triple extraction.

        Args:
            text: Source text to extract from
            ontology: The target ontology

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        system_prompt = """You are an expert knowledge graph extraction assistant.
Your task is to extract RDF triples from text, scoped to an ontology context.

Extract triples in the following JSON format:
{
  "triples": [
    {
      "subject": {"kind": "individual|class", "id": "...", "label": "..."},
      "predicate": {"property_definition_id": "...", "label": "..."},
      "object": {"kind": "individual|class|literal", "id": "...", "label": "...", "value": "..."},
      "confidence": 0.95,
      "provenance": {"text_offset_start": 0, "text_offset_end": 10, "raw": "..."}
    }
  ]
}

Return only valid JSON. If no triples can be extracted, return {"triples": []}."""

        user_prompt = f"""Extract RDF triples from the following text, scoped to the ontology
        context provided.

Text:
{text}

Ontology: {ontology.title if hasattr(ontology, 'title') else str(ontology)}"""

        return system_prompt, user_prompt

    def _parse_triple_extraction_response(
        self, response: str, text: str, ontology_id: str
    ) -> list[dict]:
        """
        Parse LLM response to extract structured triples.

        Args:
            response: LLM response text
            text: Original source text
            ontology_id: Target ontology ID

        Returns:
            List of extracted triple dictionaries
        """
        try:
            # Extract JSON from response
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if not json_match:
                return []

            response_json = json.loads(json_match.group())
            triples_data = response_json.get("triples", [])

            triples = []
            for triple_data in triples_data:
                try:
                    triple = self._build_triple_from_llm_output(triple_data, text, ontology_id)
                    triples.append(triple)
                except Exception as e:
                    _logger.warning(f"Failed to parse triple: {e}")
                    continue

            return triples

        except json.JSONDecodeError as e:
            _logger.error(f"Failed to parse LLM JSON response: {e}")
            return []

    def _build_triple_from_llm_output(self, triple_data: dict, text: str, ontology_id: str) -> dict:
        """
        Build a triple dict from LLM-extracted data.

        Args:
            triple_data: Triple data from LLM
            text: Original source text
            ontology_id: Target ontology ID

        Returns:
            Triple dictionary matching ExtractedTriple schema
        """
        subject_data = triple_data.get("subject", {})
        predicate_data = triple_data.get("predicate", {})
        object_data = triple_data.get("object", {})
        confidence = float(triple_data.get("confidence", 0.5))
        provenance_data = triple_data.get("provenance", {})

        # Build provenance
        start = provenance_data.get("text_offset_start", 0)
        end = provenance_data.get("text_offset_end", min(start + 10, len(text)))
        raw = text[start:end] if start < len(text) else ""

        provenance = {
            "text_offset_start": max(0, start),
            "text_offset_end": min(end, len(text)),
            "raw": raw,
        }

        # Build subject
        subject = {
            "kind": subject_data.get("kind", "class"),
            "id": subject_data.get("id", ""),
            "label": subject_data.get("label", ""),
        }

        # Build predicate
        predicate = {
            "property_definition_id": predicate_data.get("property_definition_id", ""),
            "label": predicate_data.get("label", ""),
        }

        # Build object (discriminated by kind)
        object_kind = object_data.get("kind", "literal")
        if object_kind == "literal":
            obj = {
                "kind": "literal",
                "value": object_data.get("value"),
                "datatype": object_data.get("datatype"),
            }
        else:
            obj = {
                "kind": object_kind,
                "id": object_data.get("id", ""),
                "label": object_data.get("label", ""),
            }

        return {
            "subject": subject,
            "predicate": predicate,
            "object": obj,
            "confidence": max(0.0, min(1.0, confidence)),
            "provenance": provenance,
        }

    def _build_result(
        self,
        result_id: str,
        text: str,
        deduplicated: list[ExtractedEntity],
        layers_executed: list[ExtractionLayerResult],
        start_time: float,
    ) -> ExtractionResult:
        """
        Construct ExtractionResult from deduplicated entities and layer metadata.

        This helper consolidates common result assembly and event publishing logic
        used by extract(), analyze_text(), and enrich_from_references().

        Args:
            result_id: Unique identifier for this extraction result
            text: Original source text
            deduplicated: Deduplicated list of extracted entities
            layers_executed: Execution details for each layer that ran
            start_time: Start time (from time.time()) for calculating duration

        Returns:
            Fully constructed ExtractionResult with completion event published
        """
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

        # Persist the result, but don't fail the entire extraction if persistence fails.
        # This is critical: extraction results from expensive LLM calls must never be
        # lost due to a persistence layer failure. The result is still returned to the
        # caller and the domain event is still published even if the database save fails.
        try:
            self._extraction_repo.save_extraction_result(result)
        except Exception as exc:
            _logger.error(
                "Failed to persist extraction result %s: %s: %s. Result will still be"
                " returned to caller.",
                result_id,
                type(exc).__name__,
                str(exc),
                exc_info=exc,
            )
            # IMPORTANT: Continue execution. The result is still returned to the caller
            # and the completion event is still published. Persistence is fire-and-forget.

        # Publish completion event
        failures = self._event_publisher.publish(
            ExtractionCompleted(
                result_id=result_id,
                entity_count=len(deduplicated),
                duration_ms=duration_ms,
            )
        )
        if failures:
            handler_names = ", ".join(name for name, _ in failures)
            _logger.warning(
                "Event handlers failed for ExtractionCompleted (result_id=%s): %s. "
                "Extraction result is returned but audit trail may have gaps.",
                result_id,
                handler_names,
            )

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

            layers_executed.append(
                ExtractionLayerResult(
                    layer_number=layer_num,
                    layer_name=layer_name,
                    entities_found=len(output.entities),
                    duration_ms=duration_ms,
                    success=True,
                )
            )

            return output

        except Exception as exc:
            duration_ms = int((time.time() - layer_start) * 1000)
            error_msg = str(exc)

            _logger.error(
                "Layer %d (%s) failed: %s: %s",
                layer_num,
                layer_name,
                type(exc).__name__,
                error_msg,
                exc_info=exc,
            )

            layers_executed.append(
                ExtractionLayerResult(
                    layer_number=layer_num,
                    layer_name=layer_name,
                    entities_found=0,
                    duration_ms=duration_ms,
                    success=False,
                    error_message=error_msg,
                )
            )

            # Return empty output so subsequent layers can continue
            return LayerOutput(entities=tuple(), metadata=MappingProxyType({"error": error_msg}))

    def _deduplicate(self, entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
        """
        Deduplicate entities across layers using ID and string similarity.

        Deduplication rules:
        1. Sort by priority: source_layer 1 > 0 > 2 > 3
        2. Group entities by ID first (exact match) - entities with same ID are the same entity
           Special handling: if multiple entities share an ID, prefer enriched copies from layer 3
           (reference layer) as they contain additional URIs, descriptions, and metadata from
           external sources. Never discard enrichment data when deduplicating.
        3. Then group entities with normalized labels matching >= threshold similarity
        4. Keep the highest-priority entity in each group, or the enriched version if available
        5. Return deduplicated entities

        Args:
            entities: Unfiltered list of entities from all layers

        Returns:
            Deduplicated list of entities with enrichment data preserved
        """
        if not entities:
            return []

        if len(entities) == 1:
            return entities

        # Sort by priority (lower value = higher priority)
        # Layer 1 (LLM) has highest priority, then Layer 0 (KG), then
        # Layer 2 (NLP), then Layer 3 (Reference)
        sorted_entities = sorted(
            entities,
            key=lambda e: self.DEDUP_PRIORITY.get(e.source_layer, 999),
        )

        deduplicated: list[ExtractedEntity] = []
        used_indices: set[int] = set()

        for i, entity in enumerate(sorted_entities):
            if i in used_indices:
                continue

            # Find all entities that represent the same concept
            used_indices.add(i)
            entity_to_keep = entity
            enriched_from_layer_3 = False

            for j in range(i + 1, len(sorted_entities)):
                if j in used_indices:
                    continue

                other = sorted_entities[j]

                if entity.id == other.id:
                    # When reference enrichment (layer 3) provides additional metadata,
                    # merge it with the higher-priority entity for maximum data retention
                    if other.source_layer == 3 and not enriched_from_layer_3:
                        entity_to_keep = ExtractedEntity(
                            id=entity.id,
                            label=entity.label,
                            entity_type=entity.entity_type,
                            source_layer=entity.source_layer,
                            confidence=max(entity.confidence, other.confidence),
                            uri=other.uri or entity.uri,
                            description=other.description or entity.description,
                            matched_class_id=entity.matched_class_id,
                            properties={
                                **(entity.properties or {}),
                                **(other.properties or {}),
                            },
                        )
                        enriched_from_layer_3 = True
                    used_indices.add(j)
                    continue

                label_similarity = self._normalized_similarity(entity.label, other.label)

                if label_similarity >= self._similarity_threshold:
                    # Mark as used; higher-priority entity is kept
                    used_indices.add(j)

            deduplicated.append(entity_to_keep)

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
