"""
RAG Processors module.

This module implements the four-layer RAG processing pipeline:
- Layer 0: KG Context Preparation
- Layer 1: LLM Extraction
- Layer 2: spaCy Gap Detection
- Layer 3: Concept Resolution
"""

from rag.processors.concept_resolution import ConceptResolutionProcessor
from rag.processors.kg_context import KGContextProcessor
from rag.processors.llm_extraction import LLMExtractionProcessor
from rag.processors.models import (
    ConceptResolutionOutput,
    ExtractedEntity,
    ExtractedPhrase,
    GapConcept,
    KGContextOutput,
    LLMExtractionOutput,
    ProcessorInput,
    ProcessorOutput,
    ResolvedConcept,
    SpaCyGapOutput,
)
from rag.processors.spacy_gap import SpaCyGapProcessor

__all__ = [
    "ConceptResolutionOutput",
    "ConceptResolutionProcessor",
    "ExtractedEntity",
    "ExtractedPhrase",
    "GapConcept",
    "KGContextOutput",
    "KGContextProcessor",
    "LLMExtractionOutput",
    "LLMExtractionProcessor",
    "ProcessorInput",
    "ProcessorOutput",
    "ResolvedConcept",
    "SpaCyGapOutput",
    "SpaCyGapProcessor",
]
