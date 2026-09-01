# mypy: ignore-errors
"""
Layer 3: Concept Resolution Processor

This processor resolves unrecognized concepts through knowledge graph matching
and strategic web search with rate limiting.
"""


import numpy as np
from database.sql_builders import build_max_similarity_case_when
from embeddings.generate_embeddings import get_model
from sqlalchemy import text
from sqlalchemy.orm import Session
from utils.logger import get_logger

from rag.processors.models import (
    ConceptResolutionOutput,
    GapConcept,
    KGContextOutput,
    KGNode,
    LLMExtractionOutput,
    ProcessorInput,
    ResolutionMethod,
    ResolvedConcept,
    SpaCyGapOutput,
)
from rag.processors.web_search import RateLimitedWebSearchClient

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
        web_search_client: RateLimitedWebSearchClient | None = None,
        similarity_threshold: float = 0.4,
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
        gap_output: SpaCyGapOutput,
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

        # Build phrase-to-KG mapping from Layer 0 for reuse
        phrase_kg_map = self._build_phrase_kg_map(kg_context, input_data.enable_trace)

        if input_data.enable_trace:
            trace_data["domain_context"] = domain_context
            trace_data["phrase_kg_map_size"] = len(phrase_kg_map)  # type: ignore
            trace_data["phrase_kg_map_keys"] = list(phrase_kg_map.keys())  # type: ignore
            trace_data["gaps_to_resolve"] = [g.text for g in gap_output.gaps]  # type: ignore
            trace_data["resolutions"] = []  # type: ignore

        logger.info(
            f"Starting gap resolution with {len(phrase_kg_map)} cached phrase mappings "
            f"and {len(gap_output.gaps)} gaps to resolve"
        )

        for gap in gap_output.gaps:
            logger.debug(
                f"Resolving gap: '{gap.text}' (priority: {gap.priority.value})"
            )

            resolution_trace = (
                {"gap_text": gap.text, "priority": gap.priority.value, "attempts": []}
                if input_data.enable_trace
                else None
            )

            # Try 1: Check if gap matches a phrase from Layer 0 using vector similarity
            resolved = self._try_phrase_match(
                gap, phrase_kg_map, kg_context, resolution_trace
            )
            if resolved:
                resolved_concepts.append(resolved)
                cached_kg_hits += 1
                if resolution_trace:
                    trace_data["resolutions"].append(resolution_trace)
                continue

            # Try 2: Expand to full KG vector search
            resolved = self._try_full_kg(gap, resolution_trace)
            if resolved:
                resolved_concepts.append(resolved)
                full_kg_hits += 1
                if resolution_trace:
                    trace_data["resolutions"].append(resolution_trace)
                continue

            # Try 3: Strategic web search (only for high-priority gaps)
            if self._should_perform_web_search(gap):
                resolved = self._try_web_search(gap, domain_context, resolution_trace)
                if resolved:
                    resolved_concepts.append(resolved)
                    web_searches_performed += 1
                    if resolution_trace:
                        trace_data["resolutions"].append(resolution_trace)
                    continue

            # Could not resolve
            unresolved_gaps.append(gap)
            if resolution_trace:
                resolution_trace["result"] = "unresolved"
                trace_data["resolutions"].append(resolution_trace)

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
            trace_data=trace_data,
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

    def _build_phrase_kg_map(
        self, kg_context: KGContextOutput, enable_trace: bool
    ) -> dict[str, tuple]:
        """
        Build a mapping of phrase embeddings to their best-matching KG nodes from Layer 0.

        This allows us to reuse Layer 0's vector search results instead of re-searching.

        Args:
            kg_context: KG context output from Layer 0
            enable_trace: Whether tracing is enabled

        Returns:
            Dict mapping phrase_text -> (phrase_embedding, best_kg_node, kg_similarity)
        """
        phrase_map = {}

        # Create a lookup map for KG nodes by ID for fast access
        kg_node_map = {node.node_id: node for node in kg_context.kg_nodes}

        # Use the phrase_to_kg_map from Layer 0 if available
        if kg_context.phrase_to_kg_map:
            for phrase_text, matches in kg_context.phrase_to_kg_map.items():
                if not matches:
                    continue  # No KG matches for this phrase

                try:
                    # Generate embedding for this phrase
                    phrase_embedding = self.embedding_model.encode([phrase_text])[0]
                    phrase_emb_array = np.array(phrase_embedding, dtype=np.float32)

                    # Get the best match from Layer 0's results (already sorted by similarity)
                    best_match = matches[0]
                    best_kg_node = kg_node_map.get(best_match["node_id"])

                    if best_kg_node:
                        phrase_map[phrase_text] = (
                            phrase_emb_array,
                            best_kg_node,
                            best_match["similarity"],
                        )
                        logger.debug(
                            f"Mapped phrase '{phrase_text}' -> KG '{best_kg_node.title}' "
                            f"(similarity: {best_match['similarity']:.2f})"
                        )

                except Exception as e:
                    logger.warning(
                        f"Failed to process phrase '{phrase_text}' from Layer 0 mapping: {e}"
                    )
                    continue

        else:
            # Fallback: Generate embeddings for phrases without KG matches
            # This happens when Layer 0 didn't provide the phrase_to_kg_map
            logger.debug(
                "phrase_to_kg_map not available from Layer 0, building phrase embeddings only"
            )

            for phrase in kg_context.extracted_phrases:
                try:
                    # Generate embedding for this phrase
                    phrase_embedding = self.embedding_model.encode([phrase.text])[0]
                    phrase_emb_array = np.array(phrase_embedding, dtype=np.float32)

                    # Store phrase embedding without KG node (will try full KG search later)
                    phrase_map[phrase.text] = (phrase_emb_array, None, 0.0)

                except Exception as e:
                    logger.warning(f"Failed to process phrase '{phrase.text}': {e}")
                    continue

        logger.debug(f"Built phrase-KG map with {len(phrase_map)} phrases")
        return phrase_map

    def _try_phrase_match(
        self,
        gap: GapConcept,
        phrase_kg_map: dict[str, tuple],
        kg_context: KGContextOutput,
        resolution_trace: dict | None,
    ) -> ResolvedConcept | None:
        """
        Try to resolve gap by matching it to Layer 0 phrases using vector similarity.

        This reuses Layer 0's vector search results to avoid redundant searches.

        Args:
            gap: Gap to resolve
            phrase_kg_map: Mapping of phrases to their embeddings and KG nodes
            kg_context: Cached KG context
            resolution_trace: Trace dictionary to update

        Returns:
            ResolvedConcept if matched, None otherwise
        """
        if resolution_trace:
            resolution_trace["attempts"].append(
                {"method": "phrase_match", "result": None}
            )

        try:
            # Generate embedding for gap text
            gap_embedding = self.embedding_model.encode([gap.text])[0]
            gap_emb_array = np.array(gap_embedding, dtype=np.float32)

            # Find best matching phrase from Layer 0 using cosine similarity
            best_phrase = None
            best_phrase_similarity = 0.0
            best_kg_node = None

            logger.debug(
                f"Checking gap '{gap.text}' against {len(phrase_kg_map)} cached phrases"
            )

            for phrase_text, (
                phrase_emb,
                kg_node,
                kg_similarity,
            ) in phrase_kg_map.items():
                # Calculate cosine similarity between gap and phrase
                phrase_similarity = self._cosine_similarity(gap_emb_array, phrase_emb)

                logger.debug(
                    f"  Gap '{gap.text}' vs phrase '{phrase_text}': "
                    f"similarity={phrase_similarity:.3f}, kg_node={kg_node.title if kg_node else 'None'}"
                )

                # If gap is very similar to a Layer 0 phrase, reuse that phrase's KG results
                if (
                    phrase_similarity >= 0.85
                ):  # High similarity threshold for phrase reuse
                    if phrase_similarity > best_phrase_similarity:
                        best_phrase_similarity = phrase_similarity
                        best_phrase = phrase_text
                        best_kg_node = kg_node

            # If we found a matching phrase with a KG node, use it
            if best_kg_node and best_phrase_similarity >= 0.85:
                confidence = self._calculate_confidence(
                    ResolutionMethod.CACHED_KG,
                    similarity=best_kg_node.similarity_score,  # Use the KG similarity from Layer 0
                )

                if resolution_trace:
                    resolution_trace["attempts"][-1]["result"] = "matched"
                    resolution_trace["attempts"][-1]["matched_phrase"] = best_phrase
                    resolution_trace["attempts"][-1][
                        "phrase_similarity"
                    ] = best_phrase_similarity
                    resolution_trace["attempts"][-1]["node_id"] = best_kg_node.node_id
                    resolution_trace["attempts"][-1]["node_title"] = best_kg_node.title
                    resolution_trace["attempts"][-1][
                        "kg_similarity"
                    ] = best_kg_node.similarity_score
                    resolution_trace["attempts"][-1]["confidence"] = confidence

                logger.debug(
                    f"Phrase match: '{gap.text}' -> phrase '{best_phrase}' ({best_phrase_similarity:.2f}) "
                    f"-> KG '{best_kg_node.title}' (confidence: {confidence:.2f})"
                )

                return ResolvedConcept(
                    original_gap=gap,
                    resolution_method=ResolutionMethod.CACHED_KG,
                    matched_kg_node=best_kg_node,
                    web_definition=None,
                    confidence=confidence,
                )

            if resolution_trace:
                resolution_trace["attempts"][-1]["result"] = "no_match"
                if best_phrase:
                    resolution_trace["attempts"][-1]["best_phrase"] = best_phrase
                    resolution_trace["attempts"][-1][
                        "best_phrase_similarity"
                    ] = best_phrase_similarity

        except Exception as e:
            logger.warning(f"Phrase matching failed for gap '{gap.text}': {e}")
            if resolution_trace:
                resolution_trace["attempts"][-1]["result"] = "error"
                resolution_trace["attempts"][-1]["error"] = str(e)

        return None

    def _try_full_kg(
        self, gap: GapConcept, resolution_trace: dict | None
    ) -> ResolvedConcept | None:
        """
        Try to resolve gap using full KG vector search with SQLite-vec.

        Args:
            gap: Gap to resolve
            resolution_trace: Trace dictionary to update

        Returns:
            ResolvedConcept if matched, None otherwise
        """
        if resolution_trace:
            resolution_trace["attempts"].append({"method": "full_kg", "result": None})

        try:
            # Generate embedding for gap text
            gap_embedding = self.embedding_model.encode([gap.text])[0]
            gap_emb_array = np.array(gap_embedding, dtype=np.float32)
            query_vec_bytes = gap_emb_array.tobytes()

            # Use SQLite-vec for native vector search
            # Search against both title and definition embeddings, taking the max similarity
            # Use a CTE to compute similarity, then filter in outer query
            similarity_case = build_max_similarity_case_when()
            query = text(f"""
                WITH similarities AS (
                    SELECT
                        id,
                        title,
                        node_type,
                        definition,
                        {similarity_case} as similarity
                    FROM ontology_entities
                    WHERE (title_embedding IS NOT NULL OR definition_embedding IS NOT NULL)
                )
                SELECT id, title, node_type, definition, similarity
                FROM similarities
                WHERE similarity >= :threshold
                ORDER BY similarity DESC
                LIMIT 1
            """)

            result = self.db_session.execute(
                query,
                {"query_vec": query_vec_bytes, "threshold": self.similarity_threshold},
            ).fetchone()

            if result:
                best_similarity = float(result.similarity)
                confidence = self._calculate_confidence(
                    ResolutionMethod.FULL_KG, similarity=best_similarity
                )

                matched_kg_node = KGNode(
                    node_id=result.id,
                    title=result.title,
                    node_type=result.node_type,
                    similarity_score=best_similarity,
                    definition=result.definition,
                )

                if resolution_trace:
                    resolution_trace["attempts"][-1]["result"] = "matched"
                    resolution_trace["attempts"][-1]["node_id"] = result.id
                    resolution_trace["attempts"][-1]["similarity"] = best_similarity
                    resolution_trace["attempts"][-1]["confidence"] = confidence

                logger.debug(
                    f"Full KG match: '{gap.text}' -> '{result.title}' "
                    f"(similarity: {best_similarity:.2f}, confidence: {confidence:.2f})"
                )

                return ResolvedConcept(
                    original_gap=gap,
                    resolution_method=ResolutionMethod.FULL_KG,
                    matched_kg_node=matched_kg_node,
                    web_definition=None,
                    confidence=confidence,
                )

            if resolution_trace:
                resolution_trace["attempts"][-1]["result"] = "no_match"

        except Exception as e:
            logger.warning(f"Full KG search failed for gap '{gap.text}': {e}")
            if resolution_trace:
                resolution_trace["attempts"][-1]["result"] = "error"
                resolution_trace["attempts"][-1]["error"] = str(e)

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
        return not (gap.tf_idf_score is not None and gap.tf_idf_score < 0.15)

    def _try_web_search(
        self, gap: GapConcept, domain_context: str, resolution_trace: dict | None
    ) -> ResolvedConcept | None:
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
            resolution_trace["attempts"].append(
                {
                    "method": "web_search",
                    "result": None,
                    "input_query": gap.text,
                    "domain_context": domain_context,
                    "grammatical_context": gap.connected_verb,
                }
            )

        # Perform web search
        search_result = self.web_search_client.search(
            query=gap.text,
            domain_context=domain_context,
            grammatical_context=gap.connected_verb,
        )

        if search_result and search_result.snippet:
            confidence = self._calculate_confidence(
                ResolutionMethod.WEB_SEARCH, snippet_length=len(search_result.snippet)
            )

            if resolution_trace:
                resolution_trace["attempts"][-1]["result"] = "found"
                resolution_trace["attempts"][-1]["enriched_query"] = search_result.query
                resolution_trace["attempts"][-1]["title"] = search_result.title
                resolution_trace["attempts"][-1]["snippet"] = search_result.snippet
                resolution_trace["attempts"][-1]["url"] = search_result.url
                resolution_trace["attempts"][-1]["snippet_length"] = len(
                    search_result.snippet
                )
                resolution_trace["attempts"][-1]["confidence"] = confidence
                resolution_trace["attempts"][-1][
                    "timestamp"
                ] = search_result.timestamp.isoformat()

            logger.debug(
                f"Web search match: '{gap.text}' -> definition found "
                f"(confidence: {confidence:.2f})"
            )

            return ResolvedConcept(
                original_gap=gap,
                resolution_method=ResolutionMethod.WEB_SEARCH,
                matched_kg_node=None,
                web_definition=search_result.snippet,
                confidence=confidence,
            )

        if resolution_trace:
            resolution_trace["attempts"][-1]["result"] = "no_results"
            # Still capture the enriched query even if no results
            if search_result:
                resolution_trace["attempts"][-1]["enriched_query"] = search_result.query

        return None

    def _calculate_confidence(
        self,
        method: ResolutionMethod,
        similarity: float | None = None,
        snippet_length: int | None = None,
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
            Cosine similarity score (0 to 1), clamped to non-negative values
        """
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = float(dot_product / (norm1 * norm2))
        # Clamp to [0, 1] range - cosine similarity can be negative but we want only positive matches
        return max(0.0, min(1.0, similarity))
