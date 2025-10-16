"""
Layer 0: Knowledge Graph Context Preparation Processor

This processor extracts phrases from input text at sentence granularity and performs
vector search against knowledge graph embeddings to retrieve relevant context.
"""
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
import numpy as np

from rag.processors.models import (
    ProcessorInput,
    KGContextOutput,
    ExtractedPhrase,
    KGNode
)
from database.models import StructureNode
from embeddings.generate_embeddings import get_model
from nlp.pipeline import get_pipeline
from utils.logger import get_logger

logger = get_logger(__name__)


class KGContextProcessor:
    """
    Layer 0: Knowledge Graph Context Preparation

    Processes paragraph-level input but retrieves relevant KG subsets at sentence granularity:
    - Process each sentence individually through spaCy
    - Extract meaningful phrases from each sentence
    - Execute vector search for each sentence's phrases
    - Aggregate and deduplicate results across all sentences
    - Return top-k matching KG concepts
    """

    def __init__(self, db_session: Session, top_k: int = 50):
        """
        Initialize KG Context Processor.

        Args:
            db_session: Database session for KG queries
            top_k: Number of top KG nodes to return (default: 50)
        """
        self.db_session = db_session
        self.top_k = top_k
        self.nlp_pipeline = get_pipeline()
        self.embedding_model = get_model()
        logger.info(f"KGContextProcessor initialized with top_k={top_k}")

    def process(self, input_data: ProcessorInput) -> KGContextOutput:
        """
        Process input text and retrieve relevant KG context.

        Args:
            input_data: Input containing text and trace settings

        Returns:
            KGContextOutput with extracted phrases and top-k KG nodes
        """
        logger.info("Starting KG context preparation")
        trace_data = {} if input_data.enable_trace else {}

        # Split text into sentences using spaCy
        doc = self.nlp_pipeline.process(input_data.text)
        sentences = list(doc.sents)

        logger.debug(f"Split input into {len(sentences)} sentences")

        # Extract phrases from each sentence
        all_phrases: List[ExtractedPhrase] = []
        sentence_phrase_map: Dict[int, List[str]] = {}

        for sent_idx, sent in enumerate(sentences):
            phrases = self._extract_phrases_from_sentence(sent, sent_idx)
            all_phrases.extend(phrases)
            sentence_phrase_map[sent_idx] = [p.text for p in phrases]

        logger.debug(f"Extracted {len(all_phrases)} total phrases from {len(sentences)} sentences")

        if input_data.enable_trace:
            trace_data['extracted_phrases'] = [
                {
                    'text': p.text,
                    'sentence_index': p.sentence_index,
                    'char_range': [p.start_char, p.end_char]
                }
                for p in all_phrases
            ]

        # Perform vector search for all phrases
        kg_nodes = self._search_kg_nodes(all_phrases, input_data.enable_trace, trace_data)

        logger.info(f"Retrieved {len(kg_nodes)} unique KG nodes (top {self.top_k})")

        return KGContextOutput(
            extracted_phrases=all_phrases,
            kg_nodes=kg_nodes,
            total_sentences=len(sentences),
            trace_data=trace_data
        )

    def _extract_phrases_from_sentence(self, sent, sent_idx: int) -> List[ExtractedPhrase]:
        """
        Extract meaningful phrases from a sentence using spaCy noun chunks.

        Args:
            sent: spaCy Span representing a sentence
            sent_idx: Sentence index

        Returns:
            List of ExtractedPhrase objects
        """
        phrases = []

        # Extract noun chunks as meaningful phrases
        for chunk in sent.noun_chunks:
            # Filter out very short chunks (single character) or stopword-only chunks
            if len(chunk.text.strip()) < 2:
                continue

            # Skip chunks that are all stopwords
            if all(token.is_stop for token in chunk):
                continue

            phrase = ExtractedPhrase(
                text=chunk.text,
                sentence_index=sent_idx,
                start_char=chunk.start_char,
                end_char=chunk.end_char
            )
            phrases.append(phrase)

        # Also extract named entities as phrases
        for ent in sent.ents:
            if len(ent.text.strip()) < 2:
                continue

            phrase = ExtractedPhrase(
                text=ent.text,
                sentence_index=sent_idx,
                start_char=ent.start_char,
                end_char=ent.end_char
            )
            phrases.append(phrase)

        return phrases

    def _search_kg_nodes(
        self,
        phrases: List[ExtractedPhrase],
        enable_trace: bool,
        trace_data: Dict[str, Any]
    ) -> List[KGNode]:
        """
        Perform vector search against KG embeddings for all phrases.

        Args:
            phrases: List of extracted phrases
            enable_trace: Whether to capture trace data
            trace_data: Dictionary to store trace information

        Returns:
            Top-k KG nodes sorted by relevance
        """
        if not phrases:
            logger.debug("No phrases to search")
            return []

        # Aggregate all unique phrase texts
        unique_phrase_texts = list(set(p.text for p in phrases))

        logger.debug(f"Searching KG for {len(unique_phrase_texts)} unique phrases")

        # Generate embeddings for all phrases
        phrase_embeddings = {}
        for phrase_text in unique_phrase_texts:
            try:
                embedding = self.embedding_model.encode([phrase_text])[0]
                phrase_embeddings[phrase_text] = np.array(embedding, dtype=np.float32)
            except Exception as e:
                logger.warning(f"Failed to generate embedding for phrase '{phrase_text}': {e}")

        # Count total nodes with embeddings
        total_nodes = self.db_session.query(func.count(StructureNode.id)).filter(
            StructureNode.title_embedding.isnot(None)
        ).scalar()

        logger.debug(f"Found {total_nodes} KG nodes with embeddings")

        # Calculate similarity scores for each phrase-node pair using batch processing
        node_scores: Dict[str, float] = {}  # node_id -> max similarity score
        node_objects: Dict[str, StructureNode] = {}  # node_id -> StructureNode object

        if enable_trace:
            trace_data['vector_searches'] = []

        # Process nodes in batches to avoid loading all into memory
        batch_size = 1000
        offset = 0

        while offset < total_nodes:
            # Query batch of nodes
            batch_nodes = self.db_session.query(StructureNode).filter(
                StructureNode.title_embedding.isnot(None)
            ).offset(offset).limit(batch_size).all()

            if not batch_nodes:
                break

            logger.debug(f"Processing batch of {len(batch_nodes)} nodes (offset: {offset})")

            # Process each phrase against this batch
            for phrase_text, phrase_emb in phrase_embeddings.items():
                phrase_trace = {
                    'phrase': phrase_text,
                    'matches': []
                } if enable_trace else None

                for node in batch_nodes:
                    try:
                        # Convert BLOB to numpy array
                        node_emb = np.frombuffer(node.title_embedding, dtype=np.float32)

                        # Validate embedding dimensions
                        if phrase_emb.shape != node_emb.shape:
                            logger.warning(
                                f"Embedding dimension mismatch: phrase={phrase_emb.shape}, "
                                f"node={node_emb.shape}. Expected 384 dimensions."
                            )
                            continue

                        # Calculate cosine similarity
                        similarity = self._cosine_similarity(phrase_emb, node_emb)

                        # Track the best score for each node
                        if node.id not in node_scores or similarity > node_scores[node.id]:
                            node_scores[node.id] = float(similarity)
                            node_objects[node.id] = node

                        if enable_trace and phrase_trace:
                            phrase_trace['matches'].append({
                                'node_id': node.id,
                                'node_title': node.title,
                                'similarity': float(similarity)
                            })

                    except Exception as e:
                        logger.debug(f"Error calculating similarity for node {node.id}: {e}")

                if enable_trace and phrase_trace and offset == 0:  # Only add trace once per phrase
                    # Sort matches by similarity and keep top 5 for trace
                    phrase_trace['matches'] = sorted(
                        phrase_trace['matches'],
                        key=lambda x: x['similarity'],
                        reverse=True
                    )[:5]
                    trace_data['vector_searches'].append(phrase_trace)

            offset += batch_size

        # Sort nodes by score and take top-k
        sorted_node_ids = sorted(node_scores.keys(), key=lambda nid: node_scores[nid], reverse=True)
        top_node_ids = sorted_node_ids[:self.top_k]

        # Convert to KGNode objects
        kg_nodes = []
        for node_id in top_node_ids:
            node = node_objects[node_id]
            kg_node = KGNode(
                node_id=node.id,
                title=node.title,
                node_type=node.node_type.value,
                similarity_score=node_scores[node_id],
                definition=node.definition
            )
            kg_nodes.append(kg_node)

        if enable_trace:
            trace_data['top_kg_nodes'] = [
                {
                    'node_id': n.node_id,
                    'title': n.title,
                    'similarity': n.similarity_score
                }
                for n in kg_nodes
            ]

        return kg_nodes

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
