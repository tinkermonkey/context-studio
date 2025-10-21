"""
Pydantic models for RAG processor inputs and outputs.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class GapPriority(str, Enum):
    """Priority levels for syntactic gaps"""
    CRITICAL = "critical"
    IMPORTANT = "important"
    CONTEXTUAL = "contextual"


class ResolutionMethod(str, Enum):
    """Methods used for concept resolution"""
    CACHED_KG = "cached_kg"
    FULL_KG = "full_kg"
    WEB_SEARCH = "web_search"
    UNRESOLVED = "unresolved"


class ProcessorInput(BaseModel):
    """Base input model for all processors"""
    text: str = Field(..., description="Input text to process")
    enable_trace: bool = Field(default=False, description="Enable trace capture for observability")


class ProcessorOutput(BaseModel):
    """Base output model for all processors"""
    trace_data: Dict[str, Any] = Field(default_factory=dict, description="Trace data for observability")


class ExtractedPhrase(BaseModel):
    """A phrase extracted from text for KG search"""
    text: str = Field(..., description="The extracted phrase text")
    sentence_index: int = Field(..., description="Index of sentence containing this phrase")
    start_char: int = Field(..., description="Starting character position in original text")
    end_char: int = Field(..., description="Ending character position in original text")


class KGNode(BaseModel):
    """A knowledge graph node returned from vector search"""
    node_id: str = Field(..., description="Unique node identifier")
    title: str = Field(..., description="Node title/label")
    node_type: str = Field(..., description="Type of node (term, domain, layer)")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Vector similarity score")
    definition: Optional[str] = Field(None, description="Node definition if available")


class KGContextOutput(ProcessorOutput):
    """Output from Layer 0: KG Context Preparation"""
    extracted_phrases: List[ExtractedPhrase] = Field(default_factory=list, description="Phrases extracted from text")
    kg_nodes: List[KGNode] = Field(default_factory=list, description="Top-k KG nodes from vector search")
    total_sentences: int = Field(..., description="Total number of sentences processed")
    phrase_to_kg_map: Optional[Dict[str, List[Dict[str, Any]]]] = Field(
        None,
        description="Mapping of phrase text to list of matched KG nodes with similarities (for Layer 3 reuse)"
    )


class ExtractedEntity(BaseModel):
    """Entity extracted by LLM"""
    text: str = Field(..., description="Entity text")
    entity_type: str = Field(..., description="Entity type (e.g., CONCEPT, PERSON, ORG)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    sentence_indices: List[int] = Field(default_factory=list, description="Sentence indices where entity appears")
    matched_kg_node: Optional[str] = Field(None, description="Matched KG node ID if found")
    start_char: int = Field(..., description="Starting character position")
    end_char: int = Field(..., description="Ending character position")


class LLMExtractionOutput(ProcessorOutput):
    """Output from Layer 1: LLM Extraction"""
    entities: List[ExtractedEntity] = Field(default_factory=list, description="Entities extracted by LLM")
    kg_context_size: int = Field(..., description="Number of KG nodes provided as context")
    token_usage: Optional[Dict[str, int]] = Field(None, description="LLM token usage stats")


class GapConcept(BaseModel):
    """A syntactic gap detected by spaCy"""
    text: str = Field(..., description="Gap text (noun phrase)")
    sentence_index: int = Field(..., description="Sentence containing this gap")
    priority: GapPriority = Field(..., description="Gap priority based on grammatical role")
    dep_role: str = Field(..., description="Dependency role (nsubj, dobj, pobj)")
    head_word: str = Field(..., description="Head word of the dependency")
    connected_verb: Optional[str] = Field(None, description="Connected verb if applicable")
    start_char: int = Field(..., description="Starting character position")
    end_char: int = Field(..., description="Ending character position")
    tf_idf_score: Optional[float] = Field(None, description="TF-IDF significance score")


class SpaCyGapOutput(ProcessorOutput):
    """Output from Layer 2: spaCy Gap Detection"""
    gaps: List[GapConcept] = Field(default_factory=list, description="Detected syntactic gaps")
    total_noun_phrases: int = Field(..., description="Total noun phrases analyzed")
    filtered_count: int = Field(..., description="Number of gaps filtered by TF-IDF")


class ResolvedConcept(BaseModel):
    """A concept resolved through KG or web search"""
    original_gap: GapConcept = Field(..., description="Original gap that was resolved")
    resolution_method: ResolutionMethod = Field(..., description="Method used for resolution")
    matched_kg_node: Optional[KGNode] = Field(None, description="Matched KG node if found")
    web_definition: Optional[str] = Field(None, description="Definition from web search")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Resolution confidence score")


class ConceptResolutionOutput(ProcessorOutput):
    """Output from Layer 3: Concept Resolution"""
    resolved_concepts: List[ResolvedConcept] = Field(default_factory=list, description="Successfully resolved concepts")
    unresolved_gaps: List[GapConcept] = Field(default_factory=list, description="Gaps that could not be resolved")
    web_searches_performed: int = Field(default=0, description="Number of web searches performed")
    cached_kg_hits: int = Field(default=0, description="Resolutions from cached KG")
    full_kg_hits: int = Field(default=0, description="Resolutions from full KG search")
