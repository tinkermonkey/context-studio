"""
RAG Pipeline Service

This service orchestrates all four layers of the RAG pipeline with error handling,
timeout enforcement, deduplication, and observability tracking.
"""
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
import asyncio
import time
from uuid import uuid4
from difflib import SequenceMatcher

from rag.models import RAGExtractionRequest, RAGExtractionResponse, ExtractedEntity, LayerMetrics, ProcessingMetrics
from rag.processors.models import ProcessorInput
from rag.processors.kg_context import KGContextProcessor
from rag.processors.llm_extraction import LLMExtractionProcessor
from rag.processors.spacy_gap import SpaCyGapProcessor
from rag.processors.concept_resolution import ConceptResolutionProcessor
from rag.observability_store import RAGObservabilityStore
from utils.logger import get_logger

logger = get_logger(__name__)


class RAGPipelineService:
    """
    RAG Pipeline Service - Orchestrates all four layers of the RAG extraction pipeline.

    Layers:
    - Layer 0: Knowledge Graph Context Preparation (sentence-level)
    - Layer 1: LLM-based Entity Extraction with KG context
    - Layer 2: spaCy Syntactic Gap Analysis
    - Layer 3: Concept Resolution via KG and Web Search

    Features:
    - Sentence-level processing with paragraph-level aggregation
    - Timeout enforcement per layer
    - Graceful degradation on layer failures
    - Entity deduplication with 90% similarity threshold
    - Observability tracking (metrics and optional traces)
    """

    # Timeout budgets per layer (in seconds)
    TIMEOUT_LAYER_0 = 0.5  # 500ms for KG context preparation
    TIMEOUT_LAYER_1 = 30.0  # 30s for LLM extraction
    TIMEOUT_LAYER_2 = 0.5  # 500ms for spaCy gap detection
    TIMEOUT_LAYER_3 = 30.0  # 30s for concept resolution
    TIMEOUT_TOTAL = 120.0  # 120s total pipeline timeout

    # Deduplication similarity threshold
    DEDUP_SIMILARITY_THRESHOLD = 0.9  # 90% similarity

    def __init__(
        self,
        kg_db_session: Session,
        ops_db_session: Session,
        llm_flavor_id: str = "default",
        kg_top_k: int = 50
    ):
        """
        Initialize RAG Pipeline Service.

        Args:
            kg_db_session: Database session for knowledge graph (local.db)
            ops_db_session: Database session for operations/observability (operations.db)
            llm_flavor_id: LLM pipeline flavor ID to use for extraction
            kg_top_k: Number of top KG nodes to retrieve (default: 50)
        """
        self.kg_db_session = kg_db_session
        self.ops_db_session = ops_db_session

        # Initialize processors
        self.kg_processor = KGContextProcessor(kg_db_session, top_k=kg_top_k)
        self.llm_processor = LLMExtractionProcessor(flavor_id=llm_flavor_id)
        self.spacy_processor = SpaCyGapProcessor(tf_idf_threshold=0.1)
        self.concept_processor = ConceptResolutionProcessor(kg_db_session, similarity_threshold=0.6)

        # Initialize observability store
        self.observability_store = RAGObservabilityStore(ops_db_session)

        logger.info(
            f"RAGPipelineService initialized with llm_flavor={llm_flavor_id}, kg_top_k={kg_top_k}"
        )

    async def extract_entities(
        self,
        text: str,
        enable_trace: bool = False
    ) -> RAGExtractionResponse:
        """
        Extract entities from text using the full RAG pipeline.

        Args:
            text: Input text to analyze and extract entities from
            enable_trace: Enable detailed tracing for observability (default: False)

        Returns:
            RAGExtractionResponse with extracted entities, metrics, and trace info
        """
        request_id = str(uuid4())
        logger.info(f"Starting RAG extraction request {request_id}, trace_enabled={enable_trace}")

        start_time = time.time()

        # Initialize layer results
        kg_context_output = None
        llm_extraction_output = None
        spacy_gap_output = None
        concept_resolution_output = None

        # Initialize metrics
        layer_0_time = 0.0
        layer_1_time = 0.0
        layer_2_time = 0.0
        layer_3_time = 0.0

        # Layer error tracking
        layer_errors = []

        # Create processor input
        processor_input = ProcessorInput(text=text, enable_trace=enable_trace)

        try:
            # LAYER 0: Knowledge Graph Context Preparation
            logger.info("Executing Layer 0: KG Context Preparation")
            layer_0_start = time.time()

            try:
                kg_context_output = await asyncio.wait_for(
                    asyncio.to_thread(self.kg_processor.process, processor_input),
                    timeout=self.TIMEOUT_LAYER_0
                )
                layer_0_time = (time.time() - layer_0_start) * 1000  # Convert to ms
                logger.info(f"Layer 0 completed in {layer_0_time:.2f}ms, found {len(kg_context_output.kg_nodes)} KG nodes")

                if enable_trace:
                    await asyncio.to_thread(
                        self.observability_store.save_trace,
                        request_id,
                        -1,  # Paragraph-level
                        "kg_context",
                        "output",
                        kg_context_output.trace_data
                    )

            except asyncio.TimeoutError:
                layer_0_time = (time.time() - layer_0_start) * 1000
                error_msg = f"Layer 0 timeout after {layer_0_time:.2f}ms (limit: {self.TIMEOUT_LAYER_0 * 1000}ms)"
                logger.warning(error_msg)
                layer_errors.append({"layer": "Layer 0", "error": error_msg})
                # Create empty KG context to allow pipeline to continue
                from rag.processors.models import KGContextOutput
                kg_context_output = KGContextOutput(
                    extracted_phrases=[],
                    kg_nodes=[],
                    total_sentences=0,
                    trace_data={}
                )

            except Exception as e:
                layer_0_time = (time.time() - layer_0_start) * 1000
                error_msg = f"Layer 0 error: {str(e)}"
                logger.error(error_msg, exc_info=True)
                layer_errors.append({"layer": "Layer 0", "error": error_msg})
                # Create empty KG context to allow pipeline to continue
                from rag.processors.models import KGContextOutput
                kg_context_output = KGContextOutput(
                    extracted_phrases=[],
                    kg_nodes=[],
                    total_sentences=0,
                    trace_data={}
                )

            # LAYER 1: LLM Entity Extraction
            logger.info("Executing Layer 1: LLM Extraction")
            layer_1_start = time.time()

            try:
                llm_extraction_output = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.llm_processor.process,
                        processor_input,
                        kg_context_output
                    ),
                    timeout=self.TIMEOUT_LAYER_1
                )
                layer_1_time = (time.time() - layer_1_start) * 1000
                logger.info(f"Layer 1 completed in {layer_1_time:.2f}ms, found {len(llm_extraction_output.entities)} entities")

                if enable_trace:
                    await asyncio.to_thread(
                        self.observability_store.save_trace,
                        request_id,
                        -1,
                        "llm_extraction",
                        "output",
                        llm_extraction_output.trace_data
                    )

            except asyncio.TimeoutError:
                layer_1_time = (time.time() - layer_1_start) * 1000
                error_msg = f"Layer 1 timeout after {layer_1_time:.2f}ms (limit: {self.TIMEOUT_LAYER_1 * 1000}ms)"
                logger.warning(error_msg)
                layer_errors.append({"layer": "Layer 1", "error": error_msg})
                # Create empty LLM output
                from rag.processors.models import LLMExtractionOutput
                llm_extraction_output = LLMExtractionOutput(
                    entities=[],
                    kg_context_size=len(kg_context_output.kg_nodes),
                    token_usage=None,
                    trace_data={}
                )

            except Exception as e:
                layer_1_time = (time.time() - layer_1_start) * 1000
                error_msg = f"Layer 1 error: {str(e)}"
                logger.error(error_msg, exc_info=True)
                layer_errors.append({"layer": "Layer 1", "error": error_msg})
                from rag.processors.models import LLMExtractionOutput
                llm_extraction_output = LLMExtractionOutput(
                    entities=[],
                    kg_context_size=len(kg_context_output.kg_nodes),
                    token_usage=None,
                    trace_data={}
                )

            # LAYER 2: spaCy Gap Detection
            logger.info("Executing Layer 2: spaCy Gap Detection")
            layer_2_start = time.time()

            try:
                spacy_gap_output = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.spacy_processor.process,
                        processor_input,
                        llm_extraction_output
                    ),
                    timeout=self.TIMEOUT_LAYER_2
                )
                layer_2_time = (time.time() - layer_2_start) * 1000
                logger.info(f"Layer 2 completed in {layer_2_time:.2f}ms, found {len(spacy_gap_output.gaps)} gaps")

                if enable_trace:
                    await asyncio.to_thread(
                        self.observability_store.save_trace,
                        request_id,
                        -1,
                        "spacy_gap",
                        "output",
                        spacy_gap_output.trace_data
                    )

            except asyncio.TimeoutError:
                layer_2_time = (time.time() - layer_2_start) * 1000
                error_msg = f"Layer 2 timeout after {layer_2_time:.2f}ms (limit: {self.TIMEOUT_LAYER_2 * 1000}ms)"
                logger.warning(error_msg)
                layer_errors.append({"layer": "Layer 2", "error": error_msg})
                # Create empty gap output
                from rag.processors.models import SpaCyGapOutput
                spacy_gap_output = SpaCyGapOutput(
                    gaps=[],
                    total_noun_phrases=0,
                    filtered_count=0,
                    trace_data={}
                )

            except Exception as e:
                layer_2_time = (time.time() - layer_2_start) * 1000
                error_msg = f"Layer 2 error: {str(e)}"
                logger.error(error_msg, exc_info=True)
                layer_errors.append({"layer": "Layer 2", "error": error_msg})
                from rag.processors.models import SpaCyGapOutput
                spacy_gap_output = SpaCyGapOutput(
                    gaps=[],
                    total_noun_phrases=0,
                    filtered_count=0,
                    trace_data={}
                )

            # LAYER 3: Concept Resolution
            logger.info("Executing Layer 3: Concept Resolution")
            layer_3_start = time.time()

            try:
                concept_resolution_output = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.concept_processor.process,
                        processor_input,
                        kg_context_output,
                        llm_extraction_output,
                        spacy_gap_output
                    ),
                    timeout=self.TIMEOUT_LAYER_3
                )
                layer_3_time = (time.time() - layer_3_start) * 1000
                logger.info(
                    f"Layer 3 completed in {layer_3_time:.2f}ms, "
                    f"resolved {len(concept_resolution_output.resolved_concepts)} concepts"
                )

                if enable_trace:
                    await asyncio.to_thread(
                        self.observability_store.save_trace,
                        request_id,
                        -1,
                        "concept_resolution",
                        "output",
                        concept_resolution_output.trace_data
                    )

            except asyncio.TimeoutError:
                layer_3_time = (time.time() - layer_3_start) * 1000
                error_msg = f"Layer 3 timeout after {layer_3_time:.2f}ms (limit: {self.TIMEOUT_LAYER_3 * 1000}ms)"
                logger.warning(error_msg)
                layer_errors.append({"layer": "Layer 3", "error": error_msg})
                # Create empty resolution output
                from rag.processors.models import ConceptResolutionOutput
                concept_resolution_output = ConceptResolutionOutput(
                    resolved_concepts=[],
                    unresolved_gaps=spacy_gap_output.gaps,
                    web_searches_performed=0,
                    cached_kg_hits=0,
                    full_kg_hits=0,
                    trace_data={}
                )

            except Exception as e:
                layer_3_time = (time.time() - layer_3_start) * 1000
                error_msg = f"Layer 3 error: {str(e)}"
                logger.error(error_msg, exc_info=True)
                layer_errors.append({"layer": "Layer 3", "error": error_msg})
                from rag.processors.models import ConceptResolutionOutput
                concept_resolution_output = ConceptResolutionOutput(
                    resolved_concepts=[],
                    unresolved_gaps=spacy_gap_output.gaps,
                    web_searches_performed=0,
                    cached_kg_hits=0,
                    full_kg_hits=0,
                    trace_data={}
                )

            # DEDUPLICATION: Merge entities from all layers
            logger.info("Performing entity deduplication")
            all_entities = self._collect_and_deduplicate_entities(
                llm_extraction_output,
                concept_resolution_output
            )

            total_time = (time.time() - start_time) * 1000
            logger.info(
                f"RAG pipeline completed in {total_time:.2f}ms, "
                f"extracted {len(all_entities)} unique entities"
            )

            # Log any errors that occurred
            if layer_errors:
                logger.warning(f"Pipeline completed with {len(layer_errors)} layer errors: {layer_errors}")

            # Build metrics
            metrics = ProcessingMetrics(
                kg_layer=LayerMetrics(
                    execution_time_ms=layer_0_time,
                    entities_found=len(kg_context_output.kg_nodes) if kg_context_output else 0,
                    entities_deduplicated=0
                ),
                nlp_layer=LayerMetrics(
                    execution_time_ms=layer_2_time,
                    entities_found=len(spacy_gap_output.gaps) if spacy_gap_output else 0,
                    entities_deduplicated=0
                ),
                llm_layer=LayerMetrics(
                    execution_time_ms=layer_1_time,
                    entities_found=len(llm_extraction_output.entities) if llm_extraction_output else 0,
                    entities_deduplicated=0
                ),
                web_layer=LayerMetrics(
                    execution_time_ms=layer_3_time,
                    entities_found=len(concept_resolution_output.resolved_concepts) if concept_resolution_output else 0,
                    entities_deduplicated=0
                ),
                total_execution_time_ms=total_time,
                total_entities=len(all_entities),
                total_sentences=kg_context_output.total_sentences if kg_context_output else 0
            )

            # Save metrics to database
            try:
                await asyncio.to_thread(
                    self.observability_store.save_metrics,
                    request_id,
                    total_time,
                    layer_0_time,
                    len(kg_context_output.kg_nodes) if kg_context_output else 0,
                    layer_1_time,
                    len(llm_extraction_output.entities) if llm_extraction_output else 0,
                    layer_2_time,
                    len(spacy_gap_output.gaps) if spacy_gap_output else 0,
                    layer_3_time,
                    len(concept_resolution_output.resolved_concepts) if concept_resolution_output else 0,
                    kg_context_output.total_sentences if kg_context_output else 0
                )
            except Exception as e:
                logger.error(f"Failed to save observability metrics: {e}", exc_info=True)

            # Build response
            return RAGExtractionResponse(
                request_id=request_id,
                entities=all_entities,
                metrics=metrics,
                trace_available=enable_trace
            )

        except Exception as e:
            total_time = (time.time() - start_time) * 1000
            logger.error(f"RAG pipeline failed after {total_time:.2f}ms: {e}", exc_info=True)

            # Return empty response with error indication
            return RAGExtractionResponse(
                request_id=request_id,
                entities=[],
                metrics=ProcessingMetrics(
                    kg_layer=LayerMetrics(execution_time_ms=layer_0_time, entities_found=0, entities_deduplicated=0),
                    nlp_layer=LayerMetrics(execution_time_ms=layer_2_time, entities_found=0, entities_deduplicated=0),
                    llm_layer=LayerMetrics(execution_time_ms=layer_1_time, entities_found=0, entities_deduplicated=0),
                    web_layer=LayerMetrics(execution_time_ms=layer_3_time, entities_found=0, entities_deduplicated=0),
                    total_execution_time_ms=total_time,
                    total_entities=0,
                    total_sentences=0
                ),
                trace_available=False
            )

    def _collect_and_deduplicate_entities(
        self,
        llm_output,
        concept_output
    ) -> List[ExtractedEntity]:
        """
        Collect entities from all layers and deduplicate using 90% similarity threshold.

        Priority order: LLM extraction > spaCy pattern match > web search

        Args:
            llm_output: LLM extraction output
            concept_output: Concept resolution output

        Returns:
            List of deduplicated ExtractedEntity objects
        """
        entities_map: Dict[str, ExtractedEntity] = {}

        # Priority 1: LLM extracted entities
        for llm_entity in llm_output.entities:
            entity_key = llm_entity.text.lower().strip()
            entities_map[entity_key] = ExtractedEntity(
                text=llm_entity.text,
                type=llm_entity.entity_type,
                confidence=llm_entity.confidence,
                source_layer="llm",
                sentence_index=llm_entity.sentence_indices[0] if llm_entity.sentence_indices else 0,
                metadata={
                    "matched_kg_node": llm_entity.matched_kg_node,
                    "sentence_indices": llm_entity.sentence_indices,
                    "char_range": [llm_entity.start_char, llm_entity.end_char]
                }
            )

        # Priority 2 & 3: Resolved concepts (from spaCy + web search)
        for resolved in concept_output.resolved_concepts:
            entity_key = resolved.original_gap.text.lower().strip()

            # Check for duplicates using 90% similarity
            is_duplicate = False
            for existing_key in entities_map.keys():
                similarity = self._text_similarity(entity_key, existing_key)
                if similarity >= self.DEDUP_SIMILARITY_THRESHOLD:
                    is_duplicate = True
                    # Merge metadata if duplicate found
                    existing_entity = entities_map[existing_key]
                    existing_entity.metadata["also_found_by"] = existing_entity.metadata.get("also_found_by", [])
                    existing_entity.metadata["also_found_by"].append(
                        resolved.resolution_method.value
                    )
                    break

            if not is_duplicate:
                # Determine source layer based on resolution method
                source_layer = "nlp"  # spaCy gap detected
                if resolved.resolution_method.value == "web_search":
                    source_layer = "web"

                entity_type = "CONCEPT"  # Default type for resolved concepts

                entities_map[entity_key] = ExtractedEntity(
                    text=resolved.original_gap.text,
                    type=entity_type,
                    confidence=resolved.confidence,
                    source_layer=source_layer,
                    sentence_index=resolved.original_gap.sentence_index,
                    metadata={
                        "resolution_method": resolved.resolution_method.value,
                        "matched_kg_node": resolved.matched_kg_node.node_id if resolved.matched_kg_node else None,
                        "web_definition": resolved.web_definition,
                        "dep_role": resolved.original_gap.dep_role,
                        "priority": resolved.original_gap.priority.value,
                        "tf_idf_score": resolved.original_gap.tf_idf_score,
                        "char_range": [resolved.original_gap.start_char, resolved.original_gap.end_char]
                    }
                )

        logger.info(f"Deduplication complete: {len(entities_map)} unique entities")
        return list(entities_map.values())

    @staticmethod
    def _text_similarity(text1: str, text2: str) -> float:
        """
        Calculate text similarity ratio between two strings.

        Args:
            text1: First text string
            text2: Second text string

        Returns:
            Similarity ratio (0.0 to 1.0)
        """
        return SequenceMatcher(None, text1, text2).ratio()
