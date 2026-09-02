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
from typing import Any
from uuid import uuid4

from domain.interchange.services import set_batch_run_context
from domain.ontology.ports import (
    EmbeddingService,
    IndividualVectorIndex,
    OntologyRepository,
    SchemaVectorIndex,
)
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

# Upper bound on the number of ontology classes injected into a triple-extraction
# prompt. Keeps the RAG grounding block a bounded fraction of the prompt for
# large taxonomies; the imported DR spec has ~186 classes, comfortably under it.
_MAX_CATALOG_CLASSES = 300

# Upper bound on the number of ontology-permitted predicates injected into the
# relationship pass's prompt. The finite predicate vocabulary the second pass
# clamps to stays a bounded fraction of the prompt for large taxonomies; the
# imported DR spec defines ~66 distinct canonical predicates, comfortably under it.
_MAX_VOCABULARY_PREDICATES = 200

# NLP-grounded typing (issue #1141): how many candidate classes the vector index
# retrieves per extracted noun chunk for the LLM to confirm, and the minimum
# similarity a candidate must clear to be offered at all. Top-K is deliberately
# generous (the LLM does the final disambiguation); the threshold only prunes
# obvious non-matches so a bare/generic noun chunk with no real class fit yields
# no candidates and is dropped rather than sent to the LLM.
_NLP_TYPING_TOP_K = 8
_NLP_TYPING_THRESHOLD = 0.2

# Predicate labels (post-normalization) that mark a triple as an rdf:type/is_a
# typing assertion whose object must be an ontology class reference.
_TYPE_PREDICATE_LABELS = frozenset(
    {"is a", "is_a", "isa", "type", "rdf type", "instance of", "subclass of"}
)

# Retrieval-based class catalog bounds for pass-1 individual extraction
# Maximum number of retrieved classes to inject into pass-1 prompt; distinct from
# the full-catalog cap (_MAX_CATALOG_CLASSES = 300, used as fallback). When
# retrieval yields more than this count, the top-K are used; retrieval's top-k
# is independently configurable.
_CATALOG_RETRIEVAL_TOP_K = 50

# Search score threshold: minimum similarity score for a class to be included in
# retrieval results. Set to 0.10 to filter classes with near-zero semantic
# similarity while allowing weak matches through (top-K is the primary limiter).
_CATALOG_RETRIEVAL_THRESHOLD = 0.10

# Minimum number of results the retrieval must produce to be accepted; below this,
# fallback to the full catalog. Retrieval on tiny ontologies or poor query/embedding
# matches may yield empty or near-empty result sets; a minimum threshold guards
# against prompting with a near-empty catalog when the full catalog is available.
_CATALOG_RETRIEVAL_MIN_RESULTS = 5

# Small-ontology skip threshold: if a taxonomy's total class count is at or below
# this, retrieval is skipped entirely (no embed/search call is made) and the full
# catalog is returned directly. Retrieval introduces latency; on small ontologies,
# the full catalog is already bounded and there is no efficiency gain.
_CATALOG_RETRIEVAL_SKIP_THRESHOLD = 50


def _canonical_class_ref(cls) -> str:
    """
    The class's canonical external reference, or its machine identifier.

    DR-imported classes carry their spec node id (e.g. "technology.node") as the
    first ``external_references`` entry; that dotted id is the vocabulary the
    source ontology — and the graded ground truth — use for a class. Falls back
    to the class ``identifier`` when no external reference is present.
    """
    for reference in getattr(cls, "external_references", None) or []:
        identifier = getattr(reference, "identifier", None)
        if identifier:
            return identifier
    return getattr(cls, "identifier", "") or ""


def _class_reference_aliases(cls) -> list[str]:
    """
    Every identifying string by which a typing triple may legitimately name a class.

    A class can be referenced by any of its external reference identifiers (a DR
    spec node id like "technology.node", a wikidata/dbpedia id, ...), by its own
    machine identifier ("crdt"), or by its human title ("Conflict-free Replicated
    Data Type"). Different source ontologies — and their graded ground truth —
    use different ones of these forms (the DR spec types by dotted node id; the
    canon slice's models emit the class title), so verification must recognize a
    class by any of them rather than a single canonical pick.
    """
    aliases: list[str] = []
    for reference in getattr(cls, "external_references", None) or []:
        identifier = getattr(reference, "identifier", None)
        if identifier:
            aliases.append(identifier)
    identifier = getattr(cls, "identifier", "") or ""
    if identifier:
        aliases.append(identifier)
    title = getattr(cls, "title", "") or ""
    if title:
        aliases.append(title)
    return aliases


def _normalize_predicate_label(label: str) -> str:
    """Lowercase a predicate label and fold underscores/hyphens to spaces for matching."""
    return label.strip().lower().replace("_", " ").replace("-", " ")


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
        schema_index: SchemaVectorIndex | None = None,
        extraction_mode: str = "llm_two_pass",
        individual_index: IndividualVectorIndex | None = None,
        recog_threshold: float = 0.90,
        recog_margin: float = 0.05,
        recog_min_len: int = 4,
        recog_acronym_threshold: float = 0.95,
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
            schema_index: Optional vector index over ontology class/predicate
                titles + definitions. Used by the ``llm_two_pass`` extraction
                mode (to retrieve semantically relevant classes for pass-1 grounding
                via ``_relevant_class_catalog``) and required by the ``nlp_grounded``
                mode (to retrieve candidate classes for extracted noun chunks).
            extraction_mode: Which triple-extraction pipeline ``extract_triples``
                runs — ``"llm_two_pass"`` (the LLM identifies+types then relates)
                or ``"nlp_grounded"`` (spaCy extracts noun chunks, the vector
                index retrieves candidate classes, and the LLM only confirms the
                best fit — see issue #1141). Defaults to ``"llm_two_pass"``.
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
        self._schema_index = schema_index
        self._extraction_mode = extraction_mode
        # Recognition (issue #1142). When individual_index is None, recognition is
        # a no-op and behavior is unchanged. The thresholds are precision-first —
        # a false merge corrupts the graph, a missed merge is a recoverable
        # duplicate — so acceptance is conservative and biased toward "new node".
        self._individual_index = individual_index
        self._recog_threshold = recog_threshold
        self._recog_margin = recog_margin
        self._recog_min_len = recog_min_len
        self._recog_acronym_threshold = recog_acronym_threshold

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

                # Two-pass extraction (karpathy_loop_design.md §7): pass 1 grounds
                # individuals to ontology classes, pass 2 derives relationships from
                # the closed set of predicates the ontology permits between those
                # classes. The nlp_grounded mode (issue #1141) replaces pass 1's
                # LLM typing with spaCy noun-chunk extraction + vector retrieval +
                # LLM confirmation, then reuses the same relationship derivation.
                if self._extraction_mode == "nlp_grounded":
                    extracted_triples, tokens_used = self._extract_triples_nlp_grounded(
                        text, ontology, ontology_id, model, temperature
                    )
                else:
                    extracted_triples, tokens_used = self._extract_triples_two_pass(
                        text, ontology, ontology_id, model, temperature
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

    def _ontology_class_catalog(self, ontology) -> list[tuple[str, str]]:
        """
        Return the ontology's classes as (class_ref, title) pairs for RAG grounding.

        ``class_ref`` is the class's canonical external identifier (the first
        ``external_references`` entry, e.g. "technology.node") when present,
        falling back to its machine identifier. This is the exact reference the
        LLM must emit as the object of an ``is_a`` typing triple, so grounding a
        prompt in these pairs lets the model type individuals with vocabulary the
        source ontology actually defines instead of inventing class names.

        The catalog is pooled across every concept scheme of the taxonomy and
        capped so the injected block stays a bounded fraction of the prompt.
        Returns an empty list when the ontology exposes no classes (e.g. a bare
        taxonomy or an unresolved id), so the caller degrades to an ungrounded
        prompt rather than failing.
        """
        taxonomy_id = getattr(ontology, "id", None)
        if not taxonomy_id:
            return []

        catalog: list[tuple[str, str]] = []
        seen_refs: set[str] = set()
        schemes = self._ontology_repo.list_concept_schemes(
            taxonomy_id=str(taxonomy_id), limit=None
        )
        for scheme in schemes:
            for cls in self._ontology_repo.list_classes(
                concept_scheme_id=scheme.id, limit=None
            ):
                class_ref = _canonical_class_ref(cls)
                if not class_ref or class_ref in seen_refs:
                    continue
                seen_refs.add(class_ref)
                catalog.append((class_ref, cls.title or class_ref))
                if len(catalog) >= _MAX_CATALOG_CLASSES:
                    return catalog
        return catalog

    def _relevant_class_catalog(self, text: str, ontology) -> list[tuple[str, str]]:
        """
        Retrieve semantically relevant classes from the ontology's catalog, with fallback.

        Uses the vector index to embed the source text and retrieve ontology classes
        whose title/definition embeddings match that text's semantic content, scoped
        strictly to the taxonomy associated with the extraction request. Implements
        graceful degradation across multiple fallback scenarios:

        1. Index not configured (`schema_index is None`): returns full catalog
        2. Taxonomy at/below skip threshold: returns full catalog (no embed/search call)
        3. Embedding the source text raises an exception: returns full catalog
        4. Search raises an exception: returns full catalog
        5. Returned results below minimum threshold (after deduplication): returns full catalog

        Retrieved results are then deduplicated by class reference and capped at
        _CATALOG_RETRIEVAL_TOP_K. Preserves the `_ontology_class_catalog` behavior:
        canonicalized class refs matched with titles, pooled across concept schemes,
        but now subset by semantic relevance. The full catalog remains unchanged and
        is used as both fallback and for downstream canonicalization
        (`_canonicalize_triples_against_ontology`).

        Args:
            text: Source text to embed and query against
            ontology: The target ontology for scoping

        Returns:
            List of (class_ref, title) tuples, same shape as _ontology_class_catalog
        """
        taxonomy_id = getattr(ontology, "id", None)
        if not taxonomy_id:
            return self._ontology_class_catalog(ontology)

        # Vector index is not available: fall back to full catalog
        if self._schema_index is None:
            return self._ontology_class_catalog(ontology)

        # Count the total classes in the taxonomy for skip-threshold check
        total_class_count = 0
        schemes = self._ontology_repo.list_concept_schemes(
            taxonomy_id=str(taxonomy_id), limit=None
        )
        for scheme in schemes:
            total_class_count += self._ontology_repo.count_classes(
                concept_scheme_id=scheme.id
            )

        # Skip retrieval on small ontologies: return full catalog directly
        if total_class_count <= _CATALOG_RETRIEVAL_SKIP_THRESHOLD:
            return self._ontology_class_catalog(ontology)

        # Embed the source text
        try:
            embedding = self._embedding_service.embed(text)
        except Exception as exc:
            _logger.warning(
                f"Failed to embed text for class retrieval: {exc}; falling back to full catalog",
                exc_info=exc,
            )
            return self._ontology_class_catalog(ontology)

        # Query the schema vector index for relevant classes
        try:
            matches = self._schema_index.search(
                embedding,
                kinds=["class"],
                top_k=_CATALOG_RETRIEVAL_TOP_K,
                threshold=_CATALOG_RETRIEVAL_THRESHOLD,
                taxonomy_id=str(taxonomy_id),
            )
        except Exception as exc:
            _logger.warning(
                f"Schema index search failed: {exc}; falling back to full catalog",
                exc_info=exc,
            )
            return self._ontology_class_catalog(ontology)

        # Convert SchemaMatch objects to (class_ref, title) tuples, deduplicating refs.
        # Use external_id (e.g., DR spec node id) if available, else identifier (e.g.,
        # "web_server"), else empty string. This matches _canonical_class_ref behavior.
        catalog: list[tuple[str, str]] = []
        seen_refs: set[str] = set()
        for match in matches:
            class_ref = match.external_id or match.identifier or ""
            if not class_ref or class_ref in seen_refs:
                continue
            seen_refs.add(class_ref)
            catalog.append((class_ref, match.label or class_ref))

        # Enforce minimum results threshold after deduplication; below it, fallback
        if len(catalog) < _CATALOG_RETRIEVAL_MIN_RESULTS:
            _logger.warning(
                f"Retrieved only {len(catalog)} unique classes after deduplication "
                f"(below minimum {_CATALOG_RETRIEVAL_MIN_RESULTS}); falling back to full catalog"
            )
            return self._ontology_class_catalog(ontology)

        return catalog

    def _extract_triples_two_pass(
        self, text: str, ontology, ontology_id: str, model: str, temperature: float
    ) -> tuple[list[dict], int]:
        """
        Run the two-pass individual-then-relationship extraction (design doc §7).

        Pass 1 identifies and grounds individuals: the LLM lists every distinct
        individual the text mentions and types each one with an ``is_a`` triple
        against the ontology's class catalog, and the returned class references
        are canonicalized against the ontology (`_canonicalize_triples_against_ontology`).

        Pass 2 derives relationships between the now-known, grounded individuals.
        The prompt offers the LLM only the finite set of predicates the ontology
        actually defines (`_ontology_predicate_vocabulary`) and asks it to choose
        from that closed set — attacking the predicate-drift that free-form verb
        extraction produces. When the ontology defines no predicate vocabulary
        (e.g. a bare taxonomy), the pass falls back to free-form verb phrases so
        relationships are still derived. Pass 2 is skipped entirely when fewer
        than two individuals were identified (no pair to relate).

        Before returning, extracted individuals are resolved against existing
        graph nodes (`_recognize_individuals`) so a mention that already exists
        adopts that node's canonical title instead of being re-created.

        Returns:
            Tuple of (combined typing + relationship triples, total tokens used).
        """
        individual_system, individual_user = self._build_individual_extraction_prompt(
            text, ontology
        )
        individual_response = self._llm.complete(
            system_prompt=individual_system,
            user_prompt=individual_user,
            model=model,
            temperature=temperature,
            max_tokens=8000,
            response_format="json",
        )
        tokens_used = individual_response.tokens_in + individual_response.tokens_out

        individual_triples = self._parse_triple_extraction_response(
            individual_response.content, text, ontology_id
        )
        individual_triples = self._canonicalize_triples_against_ontology(
            individual_triples, ontology
        )

        individuals = self._identified_individuals(individual_triples)
        relationship_triples, rel_tokens = self._derive_relationships(
            text, ontology, individuals, ontology_id, model, temperature
        )
        tokens_used += rel_tokens
        all_relationship_triples = self._type_concept_objects(
            relationship_triples, individual_triples, ontology
        )
        combined = self._post_process_triples(
            individual_triples + all_relationship_triples, ontology
        )
        return combined, tokens_used

    def _derive_relationships(
        self, text, ontology, individuals, ontology_id, model, temperature
    ) -> tuple[list[dict], int]:
        """
        Derive relationships over already-identified individuals (shared pass 2).

        Used by both extraction modes: the LLM is offered the identified
        individuals and, per subject class, only the predicates the ontology
        permits from that class (`_build_relationship_extraction_prompt`, which
        clamps to domain/range). Any typing triple the model re-emits is dropped
        so the identification pass stays the single source of typing. Skipped when
        fewer than two individuals were identified. Returns (relationship triples,
        tokens used).
        """
        if len(individuals) < 2:
            return [], 0
        relationship_system, relationship_user = self._build_relationship_extraction_prompt(
            text, ontology, individuals
        )
        relationship_response = self._llm.complete(
            system_prompt=relationship_system,
            user_prompt=relationship_user,
            model=model,
            temperature=temperature,
            max_tokens=8000,
            response_format="json",
        )
        tokens = relationship_response.tokens_in + relationship_response.tokens_out
        relationship_triples = self._parse_triple_extraction_response(
            relationship_response.content, text, ontology_id
        )
        relationship_triples = [
            triple for triple in relationship_triples if not self._is_typing_triple(triple)
        ]
        return relationship_triples, tokens

    def _post_process_triples(self, triples: list[dict], ontology) -> list[dict]:
        """Recognition step, shared by both modes."""
        return self._recognize_individuals(triples, ontology)

    def _type_concept_objects(
        self,
        relationship_triples: list[dict],
        individual_triples: list[dict],
        ontology,
    ) -> list[dict]:
        """
        Type pass-2 concept-objects via PropertyDefinition range inference.

        Pass-2 relationship extraction may emit concept-objects: relationship
        triple objects with kind=="individual", no id, and labels not seen in
        pass-1 individuals (e.g., "readability", "loose coupling"). These are
        untyped and invisible to recognition.

        This step emits synthetic is_a triples that ground each concept-object
        in the ontology via the relationship's PropertyDefinition.range_class_id,
        making them visible to downstream recognition and materialization.

        Additionally, this step stamps property_definition_id on all relationship
        triples (not just those introducing concept-objects) by resolving their
        predicates to PropertyDefinition entities. This is a prerequisite for
        the apply service guard at line 232 (which requires property_definition_id
        to be truthy).

        Args:
            relationship_triples: Pass-2 output (relationship triples only)
            individual_triples: Pass-1 output (typing triples)
            ontology: Target ontology

        Returns:
            relationship_triples with property_definition_id stamped + synthetic
            is_a triples for concept-objects
        """
        if not relationship_triples:
            return relationship_triples

        taxonomy_id = getattr(ontology, "id", None)
        if not taxonomy_id:
            return relationship_triples

        pass_1_individual_labels = self._pass_1_individual_labels(individual_triples)

        prop_index = self._property_definition_index()
        by_alias, by_id = self._class_index(ontology)

        synthetic_triples: list[dict] = []
        concept_object_labels_typed: set[str] = set()

        for triple in relationship_triples:
            predicate_label = str(triple.get("predicate", {}).get("label", "")).strip()
            normalized_label = _normalize_predicate_label(predicate_label)

            prop_def = prop_index.get(normalized_label)
            if prop_def:
                triple["predicate"]["property_definition_id"] = str(prop_def.id)

            obj = triple.get("object", {})
            obj_kind = obj.get("kind", "")
            obj_label = str(obj.get("label", "")).strip()
            obj_id = obj.get("id")

            if self._is_concept_object(obj_kind, obj_id, obj_label, pass_1_individual_labels):
                if prop_def and prop_def.range_class_id:
                    range_class = by_id.get(str(prop_def.range_class_id))
                    if range_class:
                        obj_label_lower = obj_label.lower()
                        if obj_label_lower not in concept_object_labels_typed:
                            concept_object_labels_typed.add(obj_label_lower)
                            synthetic_triple = self._make_concept_object_typing_triple(
                                obj_label, range_class, triple
                            )
                            synthetic_triples.append(synthetic_triple)
                    else:
                        _logger.info(
                            f"Concept-object '{obj_label}': PropertyDefinition "
                            f"'{predicate_label}' has range_class_id="
                            f"{prop_def.range_class_id}, but class not found in ontology"
                        )
                elif prop_def:
                    _logger.info(
                        f"Concept-object '{obj_label}': PropertyDefinition "
                        f"'{predicate_label}' declares no range_class_id"
                    )
                else:
                    _logger.info(
                        f"Concept-object '{obj_label}': PropertyDefinition not found "
                        f"for predicate '{predicate_label}'"
                    )

        return relationship_triples + synthetic_triples

    def _pass_1_individual_labels(self, individual_triples: list[dict]) -> set[str]:
        """
        Extract pass-1 individual labels (lowercased) from typing triples.

        Reads individual labels from the subjects of is_a typing triples.
        """
        labels: set[str] = set()
        for triple in individual_triples:
            if self._is_typing_triple(triple):
                label = str(triple.get("subject", {}).get("label", "")).strip()
                if label:
                    labels.add(label.lower())
        return labels

    def _property_definition_index(self) -> dict[str, Any]:
        """
        Build a normalized_predicate_label -> PropertyDefinition index.

        Follows the local-index pattern: built within the method from
        list_property_definitions, not cached.
        """
        index: dict[str, Any] = {}
        for prop_def in self._ontology_repo.list_property_definitions(limit=None):
            predicate = (prop_def.canonical_predicate or prop_def.title or "").strip()
            if not predicate:
                continue
            normalized = _normalize_predicate_label(predicate)
            index[normalized] = prop_def
        return index

    def _is_concept_object(
        self,
        obj_kind: str,
        obj_id: Any,
        obj_label: str,
        pass_1_individual_labels: set[str],
    ) -> bool:
        """
        Check if an object is a pass-2 concept-object.

        A concept-object has:
        - kind == "individual"
        - no id
        - label (lowercased) not in pass-1 individual labels
        """
        return (
            obj_kind == "individual"
            and not obj_id
            and obj_label.lower() not in pass_1_individual_labels
        )

    def _make_concept_object_typing_triple(
        self, obj_label: str, range_class, originating_triple: dict
    ) -> dict:
        """
        Create a synthetic is_a triple for a concept-object.

        The subject is the concept-object itself, the object is the range class,
        and the confidence/provenance are inherited from the originating
        relationship triple.
        """
        range_class_id = str(range_class.id)
        range_class_ref = _canonical_class_ref(range_class) or range_class_id
        return {
            "subject": {
                "kind": "individual",
                "id": None,
                "label": obj_label,
                "class_id": range_class_id,
            },
            "predicate": {"property_definition_id": None, "label": "is_a"},
            "object": {
                "kind": "class",
                "id": range_class_id,
                "label": range_class_ref,
            },
            "confidence": originating_triple.get("confidence"),
            "provenance": originating_triple.get("provenance"),
        }

    def _extract_triples_nlp_grounded(
        self, text: str, ontology, ontology_id: str, model: str, temperature: float
    ) -> tuple[list[dict], int]:
        """
        NLP-grounded extraction: spaCy leading edge + retrieval + LLM confirmation (#1141).

        Phase 1 (typing) replaces the LLM identification pass: spaCy extracts
        noun chunks, the vector index retrieves candidate classes for each, and
        the LLM only *confirms* the best-fitting class (or none) in the chunk's
        sentence context (`_type_individuals_nlp_grounded`). The label comes from
        the text and the type from the matched ontology node, so nothing is
        LLM-generated. The relationship pass (`_derive_relationships`) is reused
        unchanged for now.

        NOT the baseline (`extract_triples` defaults to ``llm_two_pass``).
        Retained as a pipeline component. A de-risking smoke (issue #1141) found
        retrieval-for-typing regresses on this ontology: the DR classes' generic
        ArchiMate definitions do not embed near specific instance names (e.g.
        "Nextflow" -> application.applicationcomponent ranks ~32/186), so the
        right class is routinely outside any usable top-K and the LLM-confirm step
        cannot recover it — whereas the LLM's world knowledge types it correctly.
        Vector retrieval is the right tool for RECOGNITION (matching an extracted
        individual to an EXISTING specific individual — a specific-to-specific
        match) rather than typing (specific instance -> generic class). See
        `_recognize_individuals` (#1137).
        """
        individual_triples, tokens_used = self._type_individuals_nlp_grounded(
            text, ontology, ontology_id, model, temperature
        )
        individual_triples = self._canonicalize_triples_against_ontology(
            individual_triples, ontology
        )
        individuals = self._identified_individuals(individual_triples)
        relationship_triples, rel_tokens = self._derive_relationships(
            text, ontology, individuals, ontology_id, model, temperature
        )
        tokens_used += rel_tokens
        all_relationship_triples = self._type_concept_objects(
            relationship_triples, individual_triples, ontology
        )
        combined = self._post_process_triples(
            individual_triples + all_relationship_triples, ontology
        )
        return combined, tokens_used

    def _type_individuals_nlp_grounded(
        self, text: str, ontology, ontology_id: str, model: str, temperature: float
    ) -> tuple[list[dict], int]:
        """
        Phase-1 typing via spaCy noun chunks + vector retrieval + LLM confirmation (#1141).

        For each noun chunk spaCy finds (headed by a NOUN/PROPN, non-stopword),
        the chunk plus its sentence is embedded and the vector index retrieves the
        top-K candidate ontology classes; the LLM then confirms which candidate
        the chunk instantiates in that sentence, or none. A confirmed chunk
        becomes an ``is_a`` typing triple whose subject label is the chunk text
        and whose object is the matched class's external id — the label comes from
        the text and the type from the ontology, so nothing is LLM-generated.
        Requires a schema index; without one this mode can't retrieve and yields
        no typing.
        """
        if self._schema_index is None:
            return [], 0

        result = self._nlp.process_open(text)
        tokens = list(result.tokens)
        sentences = self._sentence_texts(text, tokens)
        taxonomy_id = str(getattr(ontology, "id", "") or "") or None

        triples: list[dict] = []
        tokens_used = 0
        seen: set[str] = set()
        for chunk in result.noun_chunks:
            root = tokens[chunk.root_index] if 0 <= chunk.root_index < len(tokens) else None
            if root is None or root.pos not in ("NOUN", "PROPN") or root.is_stop:
                continue
            label = chunk.text.strip()
            if not label or label.lower() in seen:
                continue

            sentence = sentences.get(chunk.sentence_index, "")
            query = f"{label}. {sentence}".strip() if sentence else label
            embedding = self._embedding_service.embed(query)
            matches = self._schema_index.search(
                embedding,
                kinds=["class"],
                top_k=_NLP_TYPING_TOP_K,
                threshold=_NLP_TYPING_THRESHOLD,
                taxonomy_id=taxonomy_id,
            )
            if not matches:
                continue

            chosen, call_tokens = self._confirm_class_for_chunk(
                label, sentence, matches, model, temperature
            )
            tokens_used += call_tokens
            if chosen is None:
                continue
            seen.add(label.lower())
            triples.append(self._make_typing_triple(label, chosen, chunk))
        return triples, tokens_used

    @staticmethod
    def _sentence_texts(text: str, tokens: list) -> dict[int, str]:
        """Reconstruct each sentence's text (by ``sentence_index``) from token char spans."""
        bounds: dict[int, tuple[int, int]] = {}
        for tok in tokens:
            start, end = bounds.get(tok.sentence_index, (tok.start, tok.end))
            bounds[tok.sentence_index] = (min(start, tok.start), max(end, tok.end))
        return {idx: text[start:end] for idx, (start, end) in bounds.items()}

    def _confirm_class_for_chunk(
        self, label: str, sentence: str, matches, model: str, temperature: float
    ):
        """
        Ask the LLM which retrieved candidate class the noun chunk instantiates.

        The LLM's only job is disambiguation-in-context: it picks the best-fitting
        candidate (by its exact ontology reference) or "none" — it never invents a
        class. Returns ``(chosen SchemaMatch | None, tokens_used)``.
        """
        candidates: list[tuple[str, Any]] = []
        lines: list[str] = []
        for match in matches:
            ref = match.external_id or match.identifier or match.label
            if not ref:
                continue
            cls = self._ontology_repo.get_class(match.entity_id)
            definition = (getattr(cls, "description", None) or "").strip() if cls else ""
            title = match.label or ref
            candidates.append((ref, match))
            lines.append(f"- {ref} ({title})" + (f": {definition}" if definition else ""))
        if not candidates:
            return None, 0

        system_prompt = (
            "You are a knowledge-graph typing assistant. Given a phrase from a "
            "text, its sentence, and a list of candidate ontology classes, decide "
            "which single class the phrase is an INSTANCE of in that sentence. "
            'Choose the exact reference of the best-fitting candidate, or "none" '
            "if the phrase is not an instance of any of them. Do not invent "
            'classes. Respond with only JSON: {"class": "<exact reference or none>"}.'
        )
        user_prompt = (
            f'Phrase: "{label}"\n'
            f'Sentence: "{sentence}"\n\n'
            "Candidate classes (reference (title): definition):\n"
            + "\n".join(lines)
        )
        response = self._llm.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
            max_tokens=200,
            response_format="json",
        )
        tokens = response.tokens_in + response.tokens_out

        choice = ""
        payload = re.search(r"\{.*\}", response.content or "", re.S)
        if payload:
            try:
                choice = str(json.loads(payload.group(0)).get("class", "")).strip()
            except (ValueError, TypeError):
                choice = ""
        if not choice or choice.lower() == "none":
            return None, tokens
        choice_lower = choice.lower()
        for ref, match in candidates:
            if ref.lower() == choice_lower or (match.label or "").lower() == choice_lower:
                return match, tokens
        return None, tokens

    @staticmethod
    def _make_typing_triple(label: str, match, chunk) -> dict:
        """Build an ``is_a`` typing triple from a confirmed class match and its noun chunk."""
        class_ref = match.external_id or match.identifier or match.label
        return {
            "subject": {
                "kind": "individual",
                "id": None,
                "label": label,
                "class_id": match.entity_id,
            },
            "predicate": {"property_definition_id": None, "label": "is_a"},
            "object": {"kind": "class", "id": match.entity_id, "label": class_ref},
            "confidence": round(float(getattr(match, "score", 0.0) or 0.0), 2),
            "provenance": {
                "text_offset_start": chunk.start,
                "text_offset_end": chunk.end,
                "raw": chunk.text,
            },
        }

    def _recognize_individuals(self, triples: list[dict], ontology) -> list[dict]:
        """
        Recognition step — resolve extracted individuals to existing graph nodes (#1142).

        Individuals are instances of ontology terms. Extraction identifies them
        from text; *recognition* answers "does this individual already exist?" and
        resolves each typed mention to an existing graph individual when one is
        found — so the same real-world entity is not re-created as duplicate nodes
        across documents, and its canonical label comes from the resolved node.

        For each distinct typed mention (subject of an ``is_a`` triple; its
        grounded class taken from the triple's object), resolve against the
        existing individuals of that class via `_resolve_mention` (exact-label,
        then a conservative vector match). A resolution rewrites every triple that
        references the mention as a subject/object individual — never a class — to
        the resolved node's canonical title, and stamps ``id`` so apply reuses the
        node instead of creating a duplicate. Resolution is precision-first: it
        maps a mention to at most one existing node, never fuses two existing
        nodes, and biases toward "new node" on any doubt.

        No-op when no individual index is wired (the caller passes
        ``individual_index=None`` for the plain single-document path). Unresolved
        mentions (no existing node found) keep the surface label extraction
        produced — recognition is the only source of label normalization for
        individuals.
        """
        if self._individual_index is None:
            return triples

        by_alias, _ = self._class_index(ontology)

        # Distinct typed mentions in first-appearance order -> grounded class id.
        mention_class: dict[str, tuple[str, str | None]] = {}
        for triple in triples:
            if not self._is_typing_triple(triple):
                continue
            mention = str(triple.get("subject", {}).get("label", "")).strip()
            if not mention or mention.lower() in mention_class:
                continue
            cls = by_alias.get(str(triple.get("object", {}).get("label", "")).strip().lower())
            mention_class[mention.lower()] = (mention, str(cls.id) if cls is not None else None)

        resolution: dict[str, tuple[str, str]] = {}
        for key, (mention, class_id) in mention_class.items():
            resolved = self._resolve_mention(mention, class_id)
            if resolved is not None:
                resolution[key] = resolved
        if not resolution:
            return triples

        for triple in triples:
            for role in ("subject", "object"):
                node = triple.get(role, {})
                if node.get("kind") == "class":
                    continue
                resolved = resolution.get(str(node.get("label", "")).strip().lower())
                if resolved is not None:
                    node["id"], node["label"] = resolved[0], resolved[1]
        return triples

    def _resolve_mention(self, mention: str, class_id: str | None) -> tuple[str, str] | None:
        """
        Resolve one extracted mention to an existing individual, or None (new node).

        Exact-label match (case-insensitive title within the grounded class) always
        wins. Otherwise a vector match is accepted only when it clears the
        recognition threshold, beats the runner-up by the ambiguity margin, and —
        for short/acronym mentions — clears a stricter bar. Returns
        ``(individual_id, canonical_title)`` on resolution.
        """
        if self._individual_index is None:
            return None
        class_ids = [class_id] if class_id else []
        embedding = self._embedding_service.embed(mention)
        candidates = self._individual_index.search(
            embedding, class_ids=class_ids, top_k=5, threshold=0.0
        )
        if not candidates:
            return None

        mention_lower = mention.strip().lower()
        for candidate in candidates:
            if candidate.title.strip().lower() == mention_lower:
                return candidate.individual_id, candidate.title

        top = candidates[0]
        min_score = (
            self._recog_acronym_threshold
            if len(mention.strip()) < self._recog_min_len
            else self._recog_threshold
        )
        if top.score < min_score:
            return None
        if len(candidates) > 1 and (top.score - candidates[1].score) < self._recog_margin:
            return None
        return top.individual_id, top.title

    def _is_typing_triple(self, triple: dict) -> bool:
        """Return True when a triple is an ``is_a``/rdf:type assertion (object is a class)."""
        predicate_label = _normalize_predicate_label(triple.get("predicate", {}).get("label", ""))
        object_kind = triple.get("object", {}).get("kind", "")
        return predicate_label in _TYPE_PREDICATE_LABELS or object_kind == "class"

    def _identified_individuals(self, triples: list[dict]) -> list[tuple[str, str]]:
        """
        Collect the distinct individuals identified in pass 1 with their grounded class.

        Reads the pass-1 typing triples: each individual is the subject of an
        ``is_a`` triple, grounded to the class named in the triple's object. The
        result is the (individual_label, class_label) input the relationship pass
        needs to enumerate which ontology predicates may hold between the pair.
        A blank class label is kept when the individual was extracted without a
        resolved type so it can still participate in a relationship.
        """
        individuals: dict[str, str] = {}
        for triple in triples:
            label = str(triple.get("subject", {}).get("label", "")).strip()
            if not label:
                continue
            class_label = ""
            if self._is_typing_triple(triple):
                class_label = str(triple.get("object", {}).get("label", "")).strip()
            # Prefer a grounded class label if one is available across duplicates.
            if label not in individuals or (not individuals[label] and class_label):
                individuals[label] = class_label
        return list(individuals.items())

    def _ontology_predicate_vocabulary(self, ontology) -> list[str]:
        """
        Return the finite set of predicates the ontology defines, for pass-2 clamping.

        Pools the canonical predicate of every property definition the ontology
        declares (falling back to the property's title when no canonical form is
        set), de-duplicated case-insensitively and capped at
        `_MAX_VOCABULARY_PREDICATES`. This is the closed vocabulary the
        relationship pass offers the LLM so it chooses an existing predicate
        instead of inventing a free-form verb. Returns an empty list when the
        ontology declares no properties (e.g. a bare taxonomy), so the caller
        degrades to free-form relationship extraction rather than emitting nothing.
        """
        if not getattr(ontology, "id", None):
            return []

        vocabulary: list[str] = []
        seen: set[str] = set()
        for prop in self._ontology_repo.list_property_definitions(limit=None):
            predicate = (prop.canonical_predicate or prop.title or "").strip()
            if not predicate:
                continue
            key = predicate.lower()
            if key in seen:
                continue
            seen.add(key)
            vocabulary.append(predicate)
            if len(vocabulary) >= _MAX_VOCABULARY_PREDICATES:
                break
        return vocabulary

    def _class_index(self, ontology) -> tuple[dict, dict]:
        """
        Index the ontology's classes by identifying alias and by id.

        Returns ``(by_alias, by_id)``: ``by_alias`` maps every identifying form of
        a class (external refs, machine identifier, title — lowercased) to the
        class, so a pass-1 individual's grounded class label resolves to the class
        entity; ``by_id`` maps class id to class, for walking the hierarchy.
        """
        by_alias: dict[str, Any] = {}
        by_id: dict[str, Any] = {}
        taxonomy_id = getattr(ontology, "id", None)
        if not taxonomy_id:
            return by_alias, by_id
        for scheme in self._ontology_repo.list_concept_schemes(
            taxonomy_id=str(taxonomy_id), limit=None
        ):
            for cls in self._ontology_repo.list_classes(
                concept_scheme_id=scheme.id, limit=None
            ):
                by_id[str(cls.id)] = cls
                for alias in _class_reference_aliases(cls):
                    by_alias.setdefault(alias.strip().lower(), cls)
        return by_alias, by_id

    def _class_ancestor_ids(self, cls, by_id: dict) -> set[str]:
        """The class's own id plus every ancestor id (walking ``parent_class_id``)."""
        ids: set[str] = set()
        current = cls
        while current is not None and str(current.id) not in ids:
            ids.add(str(current.id))
            parent_id = getattr(current, "parent_class_id", None)
            current = by_id.get(str(parent_id)) if parent_id else None
        return ids

    def _predicate_options_by_class(
        self, ontology, individuals: list[tuple[str, str]]
    ) -> dict[str, list[tuple[str, str | None]]]:
        """
        Per-subject-class predicate options for the identified individuals (design doc §7).

        The ontology is strongly typed: each property definition declares an
        rdfs:domain (`domain_class_id`) and rdfs:range (`range_class_id`), so a
        predicate is only valid FROM one class TO another. Rather than offer pass 2
        the whole flat predicate vocabulary for every pair, this returns, for each
        class present among the identified individuals, the predicates the ontology
        permits from that class — honoring class hierarchy (a predicate whose
        domain is an ancestor of the individual's class applies) — paired with each
        predicate's target-class title as a range hint.

        Returns an ordered ``{subject_class_title: [(predicate, range_title|None)]}``
        mapping, or an empty dict when the ontology defines no domain-scoped
        predicates for the present classes (the caller then falls back to the flat
        vocabulary or free-form extraction).
        """
        by_alias, by_id = self._class_index(ontology)
        if not by_id:
            return {}

        # Resolve each identified individual's grounded class label to a class,
        # and precompute that class's ancestor-inclusive id set.
        present: dict[str, Any] = {}
        ancestors_of: dict[str, set[str]] = {}
        for _label, class_label in individuals:
            cls = by_alias.get(str(class_label).strip().lower()) if class_label else None
            if cls is None:
                continue
            cid = str(cls.id)
            present[cid] = cls
            ancestors_of[cid] = self._class_ancestor_ids(cls, by_id)
        if not present:
            return {}

        options: dict[str, list[tuple[str, str | None]]] = {}
        for prop in self._ontology_repo.list_property_definitions(limit=None):
            domain_id = getattr(prop, "domain_class_id", None)
            if not domain_id:
                continue
            predicate = (prop.canonical_predicate or prop.title or "").strip()
            if not predicate:
                continue
            range_id = getattr(prop, "range_class_id", None)
            range_title = None
            if range_id and str(range_id) in by_id:
                range_title = by_id[str(range_id)].title
            for cid, ancestor_ids in ancestors_of.items():
                if str(domain_id) not in ancestor_ids:
                    continue
                title = present[cid].title or cid
                bucket = options.setdefault(title, [])
                if (predicate, range_title) not in bucket:
                    bucket.append((predicate, range_title))
        return options

    def _build_individual_extraction_prompt(self, text: str, ontology) -> tuple[str, str]:
        """
        Build the pass-1 prompt: identify and ground individuals only (design doc §7).

        The user prompt is grounded, RAG-style, in a retrieval-based class catalog
        (`_relevant_class_catalog`): semantically relevant classes are retrieved and listed
        so the model types each extracted individual with an ``is_a`` triple
        whose object is a real class reference, instead of trusting the model to
        guess the ontology's vocabulary. Retrieval falls back to the full catalog
        gracefully (vector index unavailable, embedding failed, too few results, etc.).
        When the ontology exposes no classes the catalog block is omitted and the prompt
        degrades to a plain extraction instruction. Relationships between individuals
        are deliberately NOT requested here — they are the job of the second pass.

        Args:
            text: Source text to extract from
            ontology: The target ontology

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        system_prompt = """You are an expert knowledge graph extraction assistant.
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

        catalog = self._relevant_class_catalog(text, ontology)
        ontology_title = ontology.title if hasattr(ontology, "title") else str(ontology)

        if catalog:
            catalog_block = "\n".join(f"- {ref} ({title})" for ref, title in catalog)
            grounding = (
                f"Ontology: {ontology_title}\n\n"
                "Ontology classes (use the exact reference before the parenthesis "
                'as the object.label of an "is_a" triple):\n'
                f"{catalog_block}"
            )
        else:
            grounding = f"Ontology: {ontology_title}"

        user_prompt = f"""Identify the individuals in the following text, scoped to the ontology
        context provided.

Text:
{text}

{grounding}"""

        return system_prompt, user_prompt

    def _build_relationship_extraction_prompt(
        self, text: str, ontology, individuals: list[tuple[str, str]]
    ) -> tuple[str, str]:
        """
        Build the pass-2 prompt: derive relationships over the identified individuals.

        Given the individuals pass 1 grounded (label + class), the prompt asks the
        LLM to state the relationships the text asserts between them, with the
        predicate clamped to what the ontology permits. Preferred clamp: the
        per-subject-class options scoped by the ontology's rdfs:domain/rdfs:range
        (`_predicate_options_by_class`) — for each individual's class the model is
        offered only the predicates the ontology defines FROM that class, each with
        its target class as a range hint. This uses the ontology's strongly-typed
        structure instead of a flat list, tightening the closed set per pair and
        enforcing direction. Fallbacks preserve prior behavior: when no domain/range
        is defined, the flat `_ontology_predicate_vocabulary` closed set; when the
        ontology declares no predicates at all, a free-form short-verb-phrase
        instruction so relationships are still derived.

        The object of a relationship may be a listed individual OR a new concept,
        quality, or outcome the text names as the relationship's target. Pass 1's
        class-catalog grounding biases it toward concrete typeable entities and
        drops the abstract qualities/outcomes many relationships point at
        (readability, loose coupling, duplication), so restricting the object to
        the pass-1 list left those relationships unformed. Only the OBJECT side is
        opened this way — the subject stays a pass-1 individual and the predicate
        still clamps to the closed vocabulary — so this captures the missing
        relationship objects without loosening subject grounding or predicate drift.

        Args:
            text: Source text to extract from
            ontology: The target ontology
            individuals: (label, class_label) pairs identified in pass 1

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        # Prefer per-class predicate options scoped by the ontology's domain/range
        # (the strongly-typed closed set the design intends); fall back to the flat
        # global vocabulary, then to free-form, when the ontology lacks domain/range.
        options = self._predicate_options_by_class(ontology, individuals)
        vocabulary = [] if options else self._ontology_predicate_vocabulary(ontology)

        if options:
            predicate_instruction = (
                "predicate.label MUST be one of the predicates listed below for the "
                "SUBJECT individual's class — the ontology only permits those relations "
                "from that class. If none of the subject class's predicates fits, omit "
                "the relationship rather than inventing a predicate."
            )
        elif vocabulary:
            predicate_instruction = (
                "predicate.label MUST be copied EXACTLY from the allowed predicates "
                "listed in the prompt. If no allowed predicate fits a pair, omit "
                "that relationship rather than inventing a predicate."
            )
        else:
            predicate_instruction = (
                "predicate.label should be a short verb phrase describing the relationship."
            )

        system_prompt = f"""You are an expert knowledge graph extraction assistant.
Your task is to state the relationships a text asserts between a fixed set of
already-identified individuals.

Extract relationship triples in the following JSON format:
{{
  "triples": [
    {{
      "subject": {{"kind": "individual", "id": "...", "label": "..."}},
      "predicate": {{"property_definition_id": "...", "label": "..."}},
      "object": {{"kind": "individual", "id": "...", "label": "..."}},
      "confidence": 0.95,
      "provenance": {{"text_offset_start": 0, "text_offset_end": 10, "raw": "..."}}
    }}
  ]
}}

Use one of the individuals listed in the prompt as the SUBJECT of each relationship,
copying its label EXACTLY. The OBJECT may be one of the listed individuals OR a new
concept, quality, or outcome the text names as what the subject relates to (for example
an abstract quality such as "readability", "loose coupling", or "duplication") — many
relationships point at such concepts even though they are not concrete typeable
entities. When the object is a new concept, set object.kind to "individual" and give it
a concise label taken from the text; never introduce a new SUBJECT this way. Emit a
relationship only when the text states one. Do NOT emit typing ("is_a") triples in this
step. {predicate_instruction}

Return only valid JSON. If no relationships can be extracted, return {{"triples": []}}."""

        ontology_title = ontology.title if hasattr(ontology, "title") else str(ontology)
        individuals_block = "\n".join(
            f"- {label}" + (f" (a {class_label})" if class_label else "")
            for label, class_label in individuals
        )

        if options:
            lines: list[str] = []
            budget = _MAX_VOCABULARY_PREDICATES
            for class_title, preds in options.items():
                rendered: list[str] = []
                for predicate, range_title in preds:
                    if budget <= 0:
                        break
                    rendered.append(
                        f"{predicate} (-> {range_title})" if range_title else predicate
                    )
                    budget -= 1
                if rendered:
                    lines.append(f"- From a {class_title}: " + ", ".join(rendered))
                if budget <= 0:
                    break
            allowed = (
                "\n\nAllowed relations by the SUBJECT individual's class (choose "
                "predicate.label from the list matching the subject's class; the arrow "
                "shows the predicate's expected target class as a hint):\n"
                + "\n".join(lines)
            )
        elif vocabulary:
            predicate_block = "\n".join(f"- {predicate}" for predicate in vocabulary)
            allowed = (
                "\n\nAllowed predicates (use the exact form as predicate.label):\n"
                f"{predicate_block}"
            )
        else:
            allowed = ""

        user_prompt = f"""State the relationships the following text asserts, scoped to the
        ontology context provided. Each relationship's subject is one of the identified
        individuals; its object is either another identified individual or a new concept
        the text names as the relationship's target.

Text:
{text}

Ontology: {ontology_title}

Identified individuals:
{individuals_block}{allowed}"""

        return system_prompt, user_prompt

    def _canonicalize_triples_against_ontology(
        self, triples: list[dict], ontology
    ) -> list[dict]:
        """
        Canonicalize typing triples whose object resolves to an ontology class.

        The "verify LLM-returned ids against the ontology instead of trusting
        them" half of RAG-proper prompting (design doc §7 item 1). For every
        ``is_a`` typing triple (predicate normalizes to "is a"/"type"/"subclass
        of", or object.kind is "class") whose object.label resolves —
        case-insensitively — to one of a class's identifying forms
        (`_class_reference_aliases`: any external reference id, the class's own
        identifier, or its title), the label is rewritten to that alias's
        canonical casing and its kind set to "class". Matching every identifying
        form — not just the first external reference — is what lets the same step
        work across ontologies that name classes differently (the DR spec types
        by dotted node id; the canon slice's models emit the class title while
        its external refs are wikidata ids).

        Typing triples whose object matches no class, and all relationship
        triples, pass through untouched. We deliberately do NOT drop unmatched
        typing triples: the repository ontology is not guaranteed to be complete
        (a run may target a partially-populated taxonomy), so dropping would
        silently discard valid model output — a silent-failure hazard — for no
        measurable precision gain. Empirically, a grounded model emits only
        catalog-listed refs on a fully-loaded ontology, so dropping and
        canonicalize-only score identically there; keeping is strictly safer.

        The alias map spans every class the taxonomy defines (uncapped, unlike
        the prompt catalog) so a valid type is never missed merely because its
        class fell outside the prompt's bounded catalog window. When the ontology
        exposes no classes the triples are returned unchanged.
        """
        taxonomy_id = getattr(ontology, "id", None)
        if not taxonomy_id:
            return triples

        alias_to_canonical: dict[str, str] = {}
        schemes = self._ontology_repo.list_concept_schemes(
            taxonomy_id=str(taxonomy_id), limit=None
        )
        for scheme in schemes:
            for cls in self._ontology_repo.list_classes(
                concept_scheme_id=scheme.id, limit=None
            ):
                for alias in _class_reference_aliases(cls):
                    alias_to_canonical.setdefault(alias.strip().lower(), alias)

        if not alias_to_canonical:
            return triples

        for triple in triples:
            predicate = triple.get("predicate", {})
            obj = triple.get("object", {})
            predicate_label = _normalize_predicate_label(predicate.get("label", ""))
            is_typing = predicate_label in _TYPE_PREDICATE_LABELS or obj.get("kind") == "class"
            if not is_typing:
                continue

            canonical = alias_to_canonical.get(str(obj.get("label", "")).strip().lower())
            if canonical is None:
                continue
            obj["label"] = canonical
            obj["kind"] = "class"
        return triples

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
        subject_kind = subject_data.get("kind", "class")
        subject: dict = {
            "kind": subject_kind,
            "id": subject_data.get("id", ""),
            "label": subject_data.get("label", ""),
        }
        if subject_kind == "individual":
            class_id = subject_data.get("class_id", "")
            subject["class_ids"] = [class_id] if class_id else []

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
