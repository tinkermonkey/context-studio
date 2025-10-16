"""
Layer 3: Concept Resolution Processor

This processor resolves unrecognized concepts through knowledge graph matching
and strategic web search with rate limiting.
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import numpy as np

from rag.processors.models import (
    ProcessorInput,
    ConceptResolutionOutput,
    ResolvedConcept,
    GapConcept,
    KGNode,
    KGContextOutput,
    SpaCyGapOutput,
    ResolutionMethod,
    LLMExtractionOutput
)
from rag.processors.web_search import RateLimitedWebSearchClient
from database.models import StructureNode
from embeddings.generate_embeddings import get_model
from utils.logger import get_logger

logger = get_logger(__name__)


class ConceptResolutionProcessor:
    """
    Layer 3: Concept Resolution via Knowledge Graph and Web Search

    Resolves unrecognized concepts through:
    - Searching cached relevant KG subset (from FR-1)
    - Expanding to full KG vector search if no match in cached subset
    - Strategic web search for high-value unrecognized concepts with rate limiting
    - Assigns confidence scores based on resolution method
    """

    # Confidence score ranges by resolution method
    CONFIDENCE_CACHED_KG = (0.7, 0.8)
    CONFIDENCE_FULL_KG = (0.6, 0.75)
    CONFIDENCE_WEB_SEARCH = (0.5, 0.6)

    def __init__(
        self,
        db_session: Session,
        web_search_client: Optional[RateLimitedWebSearchClient] = None,
        similarity_threshold: float = 0.6
    ):
        """
        Initialize Concept Resolution Processor.

        Args:
            db_session: Database session for KG queries
            web_search_client: Optional web search client (creates default if None)
            similarity_threshold: Minimum similarity for KG matches (default: 0.6)
        """
        self.db_session = db_session
        self.web_search_client = web_search_client or RateLimitedWebSearchClient()
        self.similarity_threshold = similarity_threshold
        self.embedding_model = get_model()
        logger.info(
            f"ConceptResolutionProcessor initialized with "
            f"similarity_threshold={similarity_threshold}"
        )

    def process(
        self,
        input_data: ProcessorInput,
        kg_context: KGContextOutput,
        llm_output: LLMExtractionOutput,
        gap_output: SpaCyGapOutput
    ) -> ConceptResolutionOutput:
        """
        Process gaps to resolve concepts.

        Args:
            input_data: Input containing text and trace settings
            kg_context: KG context from Layer 0 (cached subset)
            llm_output: LLM extraction output from Layer 1 (for domain context)
            gap_output: Gap detection output from Layer 2

        Returns:
            ConceptResolutionOutput with resolved concepts
        """
        logger.info(f"Starting concept resolution for {len(gap_output.gaps)} gaps")
        trace_data = {} if input_data.enable_trace else {}

        # Reset web search session counter
        self.web_search_client.reset_session()

        resolved_concepts = []
        unresolved_gaps = []
        cached_kg_hits = 0
        full_kg_hits = 0
        web_searches_performed = 0

        # Build domain context from LLM entities
        domain_context = self._build_domain_context(llm_output)

        if input_data.enable_trace:
            trace_data['domain_context'] = domain_context
            trace_data['resolutions'] = []

        for gap in gap_output.gaps:
            logger.debug(f"Resolving gap: '{gap.text}' (priority: {gap.priority.value})")

            resolution_trace = {
                'gap_text': gap.text,
                'priority': gap.priority.value,
                'attempts': []
            } if input_data.enable_trace else None

            # Try 1: Search cached KG subset
            resolved = self._try_cached_kg(gap, kg_context, resolution_trace)
            if resolved:
                resolved_concepts.append(resolved)
                cached_kg_hits += 1
                if resolution_trace:
                    trace_data['resolutions'].append(resolution_trace)
                continue

            # Try 2: Expand to full KG vector search
            resolved = self._try_full_kg(gap, resolution_trace)
            if resolved:
                resolved_concepts.append(resolved)
                full_kg_hits += 1
                if resolution_trace:
                    trace_data['resolutions'].append(resolution_trace)
                continue

            # Try 3: Strategic web search (only for high-priority gaps)
            if self._should_perform_web_search(gap):
                resolved = self._try_web_search(gap, domain_context, resolution_trace)
                if resolved:
                    resolved_concepts.append(resolved)
                    web_searches_performed += 1
                    if resolution_trace:
                        trace_data['resolutions'].append(resolution_trace)
                    continue

            # Could not resolve
            unresolved_gaps.append(gap)
            if resolution_trace:
                resolution_trace['result'] = 'unresolved'
                trace_data['resolutions'].append(resolution_trace)

        logger.info(
            f"Resolution complete: {len(resolved_concepts)} resolved, "
            f"{len(unresolved_gaps)} unresolved "
            f"(cached_kg: {cached_kg_hits}, full_kg: {full_kg_hits}, web: {web_searches_performed})"
        )

        return ConceptResolutionOutput(
            resolved_concepts=resolved_concepts,
            unresolved_gaps=unresolved_gaps,
            web_searches_performed=web_searches_performed,
            cached_kg_hits=cached_kg_hits,
            full_kg_hits=full_kg_hits,
            trace_data=trace_data
        )

    def _build_domain_context(self, llm_output: LLMExtractionOutput) -> str:
        """
        Build domain context from recognized entities for web search.

        Args:
            llm_output: LLM extraction output

        Returns:
            Domain context string
        """
        if not llm_output.entities:
            return ""

        # Extract top entity texts as context
        entity_texts = [e.text for e in llm_output.entities[:5]]
        return ", ".join(entity_texts)

    def _try_cached_kg(
        self,
        gap: GapConcept,
        kg_context: KGContextOutput,
        resolution_trace: Optional[Dict]
    ) -> Optional[ResolvedConcept]:
        """
        Try to resolve gap using cached KG subset.

        Args:
            gap: Gap to resolve
            kg_context: Cached KG context
            resolution_trace: Trace dictionary to update

        Returns:
            ResolvedConcept if matched, None otherwise
        """
        if resolution_trace:
            resolution_trace['attempts'].append({'method': 'cached_kg', 'result': None})

        # Simple text matching first
        gap_text_lower = gap.text.lower()
        for node in kg_context.kg_nodes:
            if gap_text_lower == node.title.lower() or \
               gap_text_lower in node.title.lower() or \
               node.title.lower() in gap_text_lower:

                confidence = self._calculate_confidence(
                    ResolutionMethod.CACHED_KG,
                    similarity=0.9  # High confidence for text match
                )

                if resolution_trace:
                    resolution_trace['attempts'][-1]['result'] = 'matched'
                    resolution_trace['attempts'][-1]['node_id'] = node.node_id
                    resolution_trace['attempts'][-1]['confidence'] = confidence

                logger.debug(f"Cached KG match: '{gap.text}' -> '{node.title}' (confidence: {confidence:.2f})")

                return ResolvedConcept(
                    original_gap=gap,
                    resolution_method=ResolutionMethod.CACHED_KG,
                    matched_kg_node=node,
                    web_definition=None,
                    confidence=confidence
                )

        if resolution_trace:
            resolution_trace['attempts'][-1]['result'] = 'no_match'

        return None

    def _try_full_kg(
        self,
        gap: GapConcept,
        resolution_trace: Optional[Dict]
    ) -> Optional[ResolvedConcept]:
        """
        Try to resolve gap using full KG vector search.

        Args:
            gap: Gap to resolve
            resolution_trace: Trace dictionary to update

        Returns:
            ResolvedConcept if matched, None otherwise
        """
        if resolution_trace:
            resolution_trace['attempts'].append({'method': 'full_kg', 'result': None})

        try:
            # Generate embedding for gap text
            gap_embedding = self.embedding_model.encode([gap.text])[0]
            gap_emb_array = np.array(gap_embedding, dtype=np.float32)

            # Query all KG nodes with embeddings
            kg_nodes = self.db_session.query(StructureNode).filter(
                StructureNode.title_embedding.isnot(None)
            ).all()

            best_match = None
            best_similarity = 0.0

            for node in kg_nodes:
                try:
                    node_emb = np.frombuffer(node.title_embedding, dtype=np.float32)
                    similarity = self._cosine_similarity(gap_emb_array, node_emb)

                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_match = node

                except Exception as e:
                    logger.debug(f"Error calculating similarity for node {node.id}: {e}")

            if best_match and best_similarity >= self.similarity_threshold:
                confidence = self._calculate_confidence(
                    ResolutionMethod.FULL_KG,
                    similarity=best_similarity
                )

                matched_kg_node = KGNode(
                    node_id=best_match.id,
                    title=best_match.title,
                    node_type=best_match.node_type.value,
                    similarity_score=best_similarity,
                    definition=best_match.definition
                )

                if resolution_trace:
                    resolution_trace['attempts'][-1]['result'] = 'matched'
                    resolution_trace['attempts'][-1]['node_id'] = best_match.id
                    resolution_trace['attempts'][-1]['similarity'] = float(best_similarity)
                    resolution_trace['attempts'][-1]['confidence'] = confidence

                logger.debug(
                    f"Full KG match: '{gap.text}' -> '{best_match.title}' "
                    f"(similarity: {best_similarity:.2f}, confidence: {confidence:.2f})"
                )

                return ResolvedConcept(
                    original_gap=gap,
                    resolution_method=ResolutionMethod.FULL_KG,
                    matched_kg_node=matched_kg_node,
                    web_definition=None,
                    confidence=confidence
                )

            if resolution_trace:
                resolution_trace['attempts'][-1]['result'] = 'no_match'
                if best_match:
                    resolution_trace['attempts'][-1]['best_similarity'] = float(best_similarity)

        except Exception as e:
            logger.warning(f"Full KG search failed for gap '{gap.text}': {e}")
            if resolution_trace:
                resolution_trace['attempts'][-1]['result'] = 'error'
                resolution_trace['attempts'][-1]['error'] = str(e)

        return None

    def _should_perform_web_search(self, gap: GapConcept) -> bool:
        """
        Evaluate if gap meets criteria for web search.

        Args:
            gap: Gap to evaluate

        Returns:
            True if web search should be attempted
        """
        # Check if web search client can still search
        if not self.web_search_client.can_search():
            return False

        # Only search for critical and important priority gaps
        from rag.processors.models import GapPriority
        if gap.priority not in [GapPriority.CRITICAL, GapPriority.IMPORTANT]:
            return False

        # Check TF-IDF significance
        if gap.tf_idf_score is not None and gap.tf_idf_score < 0.15:
            return False

        return True

    def _try_web_search(
        self,
        gap: GapConcept,
        domain_context: str,
        resolution_trace: Optional[Dict]
    ) -> Optional[ResolvedConcept]:
        """
        Try to resolve gap using web search.

        Args:
            gap: Gap to resolve
            domain_context: Domain context for query enrichment
            resolution_trace: Trace dictionary to update

        Returns:
            ResolvedConcept if found, None otherwise
        """
        if resolution_trace:
            resolution_trace['attempts'].append({'method': 'web_search', 'result': None})

        # Perform web search
        search_result = self.web_search_client.search(
            query=gap.text,
            domain_context=domain_context,
            grammatical_context=gap.connected_verb
        )

        if search_result and search_result.snippet:
            confidence = self._calculate_confidence(
                ResolutionMethod.WEB_SEARCH,
                snippet_length=len(search_result.snippet)
            )

            if resolution_trace:
                resolution_trace['attempts'][-1]['result'] = 'found'
                resolution_trace['attempts'][-1]['query'] = search_result.query
                resolution_trace['attempts'][-1]['snippet'] = search_result.snippet[:200]
                resolution_trace['attempts'][-1]['confidence'] = confidence

            logger.debug(
                f"Web search match: '{gap.text}' -> definition found "
                f"(confidence: {confidence:.2f})"
            )

            return ResolvedConcept(
                original_gap=gap,
                resolution_method=ResolutionMethod.WEB_SEARCH,
                matched_kg_node=None,
                web_definition=search_result.snippet,
                confidence=confidence
            )

        if resolution_trace:
            resolution_trace['attempts'][-1]['result'] = 'no_results'

        return None

    def _calculate_confidence(
        self,
        method: ResolutionMethod,
        similarity: Optional[float] = None,
        snippet_length: Optional[int] = None
    ) -> float:
        """
        Calculate confidence score based on resolution method and quality indicators.

        Args:
            method: Resolution method used
            similarity: Similarity score for KG matches
            snippet_length: Length of web search snippet

        Returns:
            Confidence score (0.0 to 1.0)
        """
        if method == ResolutionMethod.CACHED_KG:
            # Cached KG: 0.7-0.8
            base = 0.75
            if similarity:
                # Adjust based on similarity
                base = 0.7 + (similarity * 0.1)
            return min(0.8, max(0.7, base))

        elif method == ResolutionMethod.FULL_KG:
            # Full KG: 0.6-0.75
            base = 0.675
            if similarity:
                # Adjust based on similarity
                base = 0.6 + (similarity * 0.15)
            return min(0.75, max(0.6, base))

        elif method == ResolutionMethod.WEB_SEARCH:
            # Web search: 0.5-0.6
            base = 0.55
            if snippet_length:
                # Higher confidence for longer, more detailed snippets
                if snippet_length > 200:
                    base = 0.58
                elif snippet_length > 100:
                    base = 0.56
            return min(0.6, max(0.5, base))

        return 0.5

    @staticmethod
    def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity score (0 to 1)
        """
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))
