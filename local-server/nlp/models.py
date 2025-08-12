"""
Pydantic models for NLP analysis requests and responses.
"""

from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

class NLPAnalysisRequest(BaseModel):
    """
    Request model for NLP analysis API.
    """
    text: str = Field(..., description="Text to analyze.")

class ConcepcyData(BaseModel):
    """
    ConceptNet/Concepcy data for a token.
    """
    related_terms: Optional[List[str]] = Field(default_factory=list, description="Related terms from ConceptNet.")
    score: Optional[float] = Field(None, description="ConceptNet similarity score.")

class Sense2VecData(BaseModel):
    """
    Sense2Vec data for a token.
    """
    in_s2v: bool = Field(default=False, description="Whether token is in sense2vec model")
    key: Optional[str] = Field(None, description="Sense2vec key (e.g., 'duck NOUN')")
    freq: Optional[int] = Field(None, description="Frequency in sense2vec corpus")
    other_senses: List[str] = Field(default_factory=list, description="Other senses for this word")
    most_similar: List[Dict[str, Any]] = Field(default_factory=list, description="Most similar words with scores")

class WordNetData(BaseModel):
    """
    WordNet data for a token.
    """
    synsets: Optional[List[dict]] = Field(
        default_factory=list,
        description="WordNet synsets with attributes, including domain context. Each synset dict includes: name, definition, lemmas, pos, offset, domain."
    )
    lemmas: Optional[List[dict]] = Field(default_factory=list, description="WordNet lemmas with attributes.")
    definitions: Optional[List[str]] = Field(default_factory=list, description="WordNet definitions.")

    # Example synset dict now includes 'domain': str

class DBpediaData(BaseModel):
    """
    DBpedia data for an entity.
    """
    uri: Optional[str] = Field(None, description="DBpedia URI.")
    label: Optional[str] = Field(None, description="DBpedia label.")
    similarity: Optional[float] = Field(None, description="DBpedia similarity score.")
    raw_result: Optional[Any] = Field(None, description="Raw DBpedia result.")

class TokenData(BaseModel):
    """
    Data for a single token in the analyzed text.
    """
    text: str = Field(None, description="Token text.")
    lemma: Optional[str] = Field(None, description="Token lemma.")
    pos: Optional[str] = Field(None, description="Part of speech tag.")
    tag: Optional[str] = Field(None, description="Detailed POS tag.")
    start: int = Field(None, description="Start character position.")
    end: int = Field(None, description="End character position.")
    concepcy: Optional[ConcepcyData] = Field(default_factory=ConcepcyData, description="Concepcy data.")
    wordnet: Optional[WordNetData] = Field(default_factory=WordNetData, description="WordNet data.")
    sense2vec: Optional[Sense2VecData] = Field(default_factory=Sense2VecData, description="Sense2vec data.")

class EntityData(BaseModel):
    """
    Data for a named entity in the analyzed text.
    """
    text: str = Field(..., description="Entity text.")
    label: Optional[str] = Field(None, description="Entity label.")
    kb_id: Optional[str] = Field(None, description="Knowledge base ID.")
    dbpedia: Optional[DBpediaData] = Field(None, description="DBpedia data.")

class NLPAnalysisResponse(BaseModel):
    """
    Response model for NLP analysis API.
    """
    tokens: List[TokenData] = Field(default_factory=list, description="List of token data.")
    entities: List[EntityData] = Field(default_factory=list, description="List of entity data.")
    text: str = Field(..., description="Original analyzed text.")

class SuccessResponse(BaseModel):
    """
    Success response wrapper for NLP API.
    """
    success: bool = Field(default=True, description="Indicates success.")
    data: NLPAnalysisResponse

class ErrorResponse(BaseModel):
    """
    Error response wrapper for NLP API.
    """
    success: bool = Field(default=False, description="Indicates failure.")
    error: str = Field(..., description="Error message.")
