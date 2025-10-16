"""
RAG Processors module.

This module implements the four-layer RAG processing pipeline:
- Layer 0: KG Context Preparation
- Layer 1: LLM Extraction
- Layer 2: spaCy Gap Detection
- Layer 3: Concept Resolution
"""
from rag.processors.kg_context import KGContextProcessor
from rag.processors.llm_extraction import LLMExtractionProcessor
from rag.processors.spacy_gap import SpaCyGapProcessor
from rag.processors.concept_resolution import ConceptResolutionProcessor
from rag.processors.models import (
    ProcessorInput,
    ProcessorOutput,
    KGContextOutput,
    LLMExtractionOutput,
    SpaCyGapOutput,
    ConceptResolutionOutput,
    ExtractedPhrase,
    ExtractedEntity,
    GapConcept,
    ResolvedConcept
)

__all__ = [
    'KGContextProcessor',
    'LLMExtractionProcessor',
    'SpaCyGapProcessor',
    'ConceptResolutionProcessor',
    'ProcessorInput',
    'ProcessorOutput',
    'KGContextOutput',
    'LLMExtractionOutput',
    'SpaCyGapOutput',
    'ConceptResolutionOutput',
    'ExtractedPhrase',
    'ExtractedEntity',
    'GapConcept',
    'ResolvedConcept'
]
