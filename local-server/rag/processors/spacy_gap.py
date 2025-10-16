"""
Layer 2: spaCy Syntactic Gap Analysis Processor

This processor identifies unrecognized concepts using spaCy grammatical analysis
and TF-IDF filtering to reduce noise.
"""
from typing import List, Dict, Any, Set
from collections import Counter
import math

from rag.processors.models import (
    ProcessorInput,
    SpaCyGapOutput,
    GapConcept,
    GapPriority,
    LLMExtractionOutput
)
from nlp.pipeline import get_pipeline
from utils.logger import get_logger

logger = get_logger(__name__)


class SpaCyGapProcessor:
    """
    Layer 2: spaCy Syntactic Gap Analysis

    Identifies unrecognized concepts using spaCy grammatical analysis:
    - Extracts noun phrases not recognized in LLM extraction
    - Prioritizes grammatically significant positions (subject, direct object, prepositional object)
    - Analyzes verb-object patterns for implicit concepts
    - Categorizes gaps as critical, important, or contextual based on grammatical role
    - Records syntactic context for each gap
    - Applies TF-IDF filtering to reduce noise
    """

    # Dependency roles that indicate critical concepts
    CRITICAL_DEP_ROLES = {'nsubj', 'nsubjpass'}  # Subject positions
    IMPORTANT_DEP_ROLES = {'dobj', 'pobj', 'attr', 'dative'}  # Object positions
    CONTEXTUAL_DEP_ROLES = {'conj', 'appos', 'compound', 'amod'}  # Contextual modifiers

    def __init__(self, tf_idf_threshold: float = 0.1):
        """
        Initialize spaCy Gap Processor.

        Args:
            tf_idf_threshold: Minimum TF-IDF score for gap significance (default: 0.1)
        """
        self.tf_idf_threshold = tf_idf_threshold
        self.nlp_pipeline = get_pipeline()
        logger.info(f"SpaCyGapProcessor initialized with tf_idf_threshold={tf_idf_threshold}")

    def process(
        self,
        input_data: ProcessorInput,
        llm_output: LLMExtractionOutput
    ) -> SpaCyGapOutput:
        """
        Process input text to identify syntactic gaps.

        Args:
            input_data: Input containing text and trace settings
            llm_output: LLM extraction output from Layer 1

        Returns:
            SpaCyGapOutput with detected gaps
        """
        logger.info("Starting spaCy gap analysis")
        trace_data = {} if input_data.enable_trace else {}

        # Parse text with spaCy
        doc = self.nlp_pipeline.process(input_data.text)

        # Get recognized entity texts from LLM output
        recognized_texts = {entity.text.lower() for entity in llm_output.entities}

        # Extract all noun phrases
        all_noun_phrases = []
        for sent_idx, sent in enumerate(doc.sents):
            for chunk in sent.noun_chunks:
                all_noun_phrases.append((chunk, sent_idx, sent))

        logger.debug(f"Found {len(all_noun_phrases)} total noun phrases")

        # Filter noun phrases to find gaps (unrecognized concepts)
        potential_gaps = []
        for chunk, sent_idx, sent in all_noun_phrases:
            chunk_text = chunk.text.strip().lower()

            # Skip if already recognized by LLM
            if chunk_text in recognized_texts:
                continue

            # Skip very short or stopword-only chunks
            if len(chunk_text) < 3 or all(token.is_stop for token in chunk):
                continue

            # Get dependency information for the chunk root
            root = chunk.root
            dep_role = root.dep_
            head_word = root.head.text if root.head != root else ""
            connected_verb = self._find_connected_verb(root)

            # Determine priority based on grammatical role
            priority = self._determine_priority(dep_role)

            gap = GapConcept(
                text=chunk.text.strip(),
                sentence_index=sent_idx,
                priority=priority,
                dep_role=dep_role,
                head_word=head_word,
                connected_verb=connected_verb,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
                tf_idf_score=None  # Will be calculated later
            )
            potential_gaps.append(gap)

        logger.debug(f"Found {len(potential_gaps)} potential gaps (unrecognized noun phrases)")

        # Apply TF-IDF filtering
        gaps, filtered_count = self._apply_tfidf_filtering(potential_gaps, doc)

        logger.info(f"Identified {len(gaps)} significant gaps after TF-IDF filtering ({filtered_count} filtered out)")

        if input_data.enable_trace:
            trace_data['total_noun_phrases_analyzed'] = len(all_noun_phrases)
            trace_data['potential_gaps_found'] = len(potential_gaps)
            trace_data['gaps_after_filtering'] = len(gaps)
            trace_data['gaps_by_priority'] = {
                'critical': len([g for g in gaps if g.priority == GapPriority.CRITICAL]),
                'important': len([g for g in gaps if g.priority == GapPriority.IMPORTANT]),
                'contextual': len([g for g in gaps if g.priority == GapPriority.CONTEXTUAL])
            }

        return SpaCyGapOutput(
            gaps=gaps,
            total_noun_phrases=len(all_noun_phrases),
            filtered_count=filtered_count,
            trace_data=trace_data
        )

    def _find_connected_verb(self, token) -> str:
        """
        Find the verb connected to this token.

        Args:
            token: spaCy Token

        Returns:
            Connected verb text or empty string
        """
        # Look up the dependency tree for a verb
        current = token
        max_depth = 5
        depth = 0

        while current and depth < max_depth:
            if current.pos_ == 'VERB':
                return current.text
            current = current.head if current.head != current else None
            depth += 1

        # Look in children
        for child in token.children:
            if child.pos_ == 'VERB':
                return child.text

        return ""

    def _determine_priority(self, dep_role: str) -> GapPriority:
        """
        Determine gap priority based on dependency role.

        Args:
            dep_role: Dependency role string

        Returns:
            GapPriority enum value
        """
        if dep_role in self.CRITICAL_DEP_ROLES:
            return GapPriority.CRITICAL
        elif dep_role in self.IMPORTANT_DEP_ROLES:
            return GapPriority.IMPORTANT
        else:
            return GapPriority.CONTEXTUAL

    def _apply_tfidf_filtering(
        self,
        gaps: List[GapConcept],
        doc
    ) -> tuple[List[GapConcept], int]:
        """
        Apply TF-IDF filtering to distinguish domain-specific terms from common terms.

        Args:
            gaps: List of potential gaps
            doc: spaCy Doc object

        Returns:
            Tuple of (filtered_gaps, count_filtered)
        """
        if not gaps:
            return [], 0

        # Calculate term frequencies in the document
        doc_terms = []
        for token in doc:
            if hasattr(token, 'lemma_') and hasattr(token, 'is_stop') and hasattr(token, 'is_alpha'):
                if not token.is_stop and token.is_alpha:
                    doc_terms.append(token.lemma_.lower())

        term_freq = Counter(doc_terms)
        doc_length = len(doc_terms)

        # Calculate TF-IDF scores for each gap
        # For IDF, we use a simple heuristic: inverse of term frequency in document
        # In production, would use a corpus-based IDF
        filtered_gaps = []
        filtered_count = 0

        for gap in gaps:
            # Get lemmas from gap text (simple word splitting, not using spaCy for this part)
            gap_words = [word.lower() for word in gap.text.split() if len(word) > 2]

            if not gap_words:
                # Skip gaps with no meaningful words
                filtered_count += 1
                continue

            # Calculate TF-IDF score as average across gap words
            tfidf_scores = []
            for word in gap_words:
                tf = term_freq.get(word, 0) / doc_length if doc_length > 0 else 0
                # Simple IDF approximation: penalize very common terms
                idf = math.log(1.0 / (tf + 0.01))
                tfidf = tf * idf
                tfidf_scores.append(tfidf)

            avg_tfidf = sum(tfidf_scores) / len(tfidf_scores) if tfidf_scores else 0.0

            # Update gap with TF-IDF score
            gap.tf_idf_score = avg_tfidf

            # Filter based on threshold, but always keep CRITICAL priority gaps
            if gap.priority == GapPriority.CRITICAL or avg_tfidf >= self.tf_idf_threshold:
                filtered_gaps.append(gap)
            else:
                filtered_count += 1
                logger.debug(f"Filtered gap '{gap.text}' with TF-IDF={avg_tfidf:.3f} < {self.tf_idf_threshold}")

        # Sort by priority and TF-IDF score
        filtered_gaps.sort(key=lambda g: (
            0 if g.priority == GapPriority.CRITICAL else (1 if g.priority == GapPriority.IMPORTANT else 2),
            -(g.tf_idf_score or 0)
        ))

        return filtered_gaps, filtered_count
