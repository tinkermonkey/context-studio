"""
Pydantic models for NLP analysis requests and responses.
"""

from typing import List, Optional, Any
from pydantic import BaseModel, Field


class NLPAnalysisRequest(BaseModel):
    """
    Request model for NLP analysis API.
    """

    text: str = Field(..., description="Text to analyze.")


class ConcepcyNode(BaseModel):
    """
    Represents a node in the Concepcy graph.
    """

    id: str = Field(..., description="Unique identifier for the node.")
    label: str = Field(..., description="Label for the node.")
    language: str = Field(..., description="Language of the node.")
    term: str = Field(..., description="Term associated with the node.")


class ConcepcyRelation(BaseModel):
    """
    Represents a single relation in Concepcy.
    """

    subject: Optional[ConcepcyNode] = Field(
        None, description="The 'start' of the concepcy relation."
    )
    object: Optional[ConcepcyNode] = Field(
        None, description="The 'end' of the concepcy relation."
    )
    relation: str = Field(..., description="The type of the concepcy relation.")
    text: Optional[str] = Field(
        None, description="Text representation of the relation."
    )
    weight: Optional[float] = Field(None, description="Weight of the relation.")


class ConcepcyData(BaseModel):
    """
    ConceptNet/Concepcy data for a token.
    """

    related_terms: Optional[List[ConcepcyRelation]] = Field(
        default_factory=list,
        description="Related terms from ConceptNet.",
    )


class WordNetData(BaseModel):
    """
    WordNet data for a token.
    """

    synsets: Optional[List[dict]] = Field(
        default_factory=list,
        description=(
            "WordNet synsets with attributes, including domain context. "
            "Each synset dict includes: name, definition, lemmas, pos, "
            "offset, domain."
        ),
    )
    lemmas: Optional[List[dict]] = Field(
        default_factory=list, description="WordNet lemmas with attributes."
    )
    definitions: Optional[List[str]] = Field(
        default_factory=list, description="WordNet definitions."
    )

    # Example synset dict now includes 'domain': str


class DBpediaData(BaseModel):
    """
    DBpedia data for an entity.
    """

    uri: Optional[str] = Field(None, description="DBpedia URI.")
    label: Optional[str] = Field(None, description="DBpedia label.")
    similarity: Optional[float] = Field(None, description="DBpedia similarity score.")
    raw_result: Optional[Any] = Field(None, description="Raw DBpedia result.")


class TokenReference(BaseModel):
    """
    Reference to a token by its index in the token list.
    """

    index: Optional[int] = Field(
        None, description="Index of the token in the token list."
    )
    text: Optional[str] = Field(None, description="Token text.")
    pos: Optional[str] = Field(None, description="Part of speech tag.")
    start_idx: Optional[int] = Field(None, description="Start character position.")
    end_idx: Optional[int] = Field(None, description="End character position.")


class TokenData(BaseModel):
    """
    Data for a single token in the analyzed text.
    """

    text: Optional[str] = Field(None, description="Token text.")
    lemma: Optional[str] = Field(None, description="Token lemma.")
    pos: Optional[str] = Field(None, description="Part of speech tag.")
    dep: Optional[str] = Field(None, description="Syntactic Dependency Relation.")
    tag: Optional[str] = Field(None, description="Detailed POS tag.")
    start_idx: Optional[int] = Field(None, description="Start character position.")
    end_idx: Optional[int] = Field(None, description="End character position.")
    head: Optional[TokenReference] = Field(None, description="Head token reference.")
    children: List[TokenReference] = Field(
        default_factory=list, description="List of child token references."
    )
    ancestors: List[TokenReference] = Field(
        default_factory=list, description="List of ancestor token references."
    )
    subtree: List[TokenReference] = Field(
        default_factory=list, description="List of tokens in the subtree."
    )
    is_alpha: Optional[bool] = Field(None, description="Is alphabetic.")
    is_stop: Optional[bool] = Field(None, description="Is stop word.")
    is_oov: Optional[bool] = Field(None, description="Is out-of-vocabulary.")
    like_url: Optional[bool] = Field(None, description="Is like a URL.")
    is_digit: Optional[bool] = Field(None, description="Is a digit.")
    ent_iob: Optional[str] = Field(
        None, description="Inside-Outside-Beginning tag for named entities."
    )
    ent_type: Optional[str] = Field(None, description="Named entity type.")
    ent_kb_id: Optional[str] = Field(
        None, description="Knowledge base ID for the entity."
    )
    ent_id: Optional[int] = Field(None, description="Entity ID.")
    sentiment: Optional[float] = Field(None, description="Sentiment score.")
    concepcy: Optional[ConcepcyData] = Field(
        default_factory=ConcepcyData, description="Concepcy data."
    )
    wordnet: Optional[WordNetData] = Field(
        default_factory=WordNetData, description="WordNet data."
    )


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

    tokens: List[TokenData] = Field(
        default_factory=list, description="List of token data."
    )
    entities: List[EntityData] = Field(
        default_factory=list, description="List of entity data."
    )
    text: str = Field(..., description="Original analyzed text.")


class NLPSuccessResponse(BaseModel):
    """
    Success response wrapper for NLP API.
    """

    success: bool = Field(default=True, description="Indicates success.")
    data: NLPAnalysisResponse


class NLPErrorResponse(BaseModel):
    """
    Error response wrapper for NLP API.
    """

    success: bool = Field(default=False, description="Indicates failure.")
    error: str = Field(..., description="Error message.")
