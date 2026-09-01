"""
Pydantic models for NLP analysis requests and responses.
"""

from typing import Any

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

    subject: ConcepcyNode | None = Field(
        None, description="The 'start' of the concepcy relation."
    )
    object: ConcepcyNode | None = Field(
        None, description="The 'end' of the concepcy relation."
    )
    relation: str = Field(..., description="The type of the concepcy relation.")
    text: str | None = Field(
        None, description="Text representation of the relation."
    )
    weight: float | None = Field(None, description="Weight of the relation.")


class ConcepcyData(BaseModel):
    """
    ConceptNet/Concepcy data for a token.
    """

    related_terms: list[ConcepcyRelation] | None = Field(
        default_factory=list,
        description="Related terms from ConceptNet.",
    )


class WordNetData(BaseModel):
    """
    WordNet data for a token.
    """

    synsets: list[dict] | None = Field(
        default_factory=list,
        description=(
            "WordNet synsets with attributes, including domain context. "
            "Each synset dict includes: name, definition, lemmas, pos, "
            "offset, domain."
        ),
    )
    lemmas: list[dict] | None = Field(
        default_factory=list, description="WordNet lemmas with attributes."
    )
    definitions: list[str] | None = Field(
        default_factory=list, description="WordNet definitions."
    )

    # Example synset dict now includes 'domain': str


class DBpediaData(BaseModel):
    """
    DBpedia data for an entity.
    """

    uri: str | None = Field(None, description="DBpedia URI.")
    label: str | None = Field(None, description="DBpedia label.")
    similarity: float | None = Field(None, description="DBpedia similarity score.")
    raw_result: Any | None = Field(None, description="Raw DBpedia result.")


class TokenReference(BaseModel):
    """
    Reference to a token by its index in the token list.
    """

    index: int | None = Field(
        None, description="Index of the token in the token list."
    )
    text: str | None = Field(None, description="Token text.")
    pos: str | None = Field(None, description="Part of speech tag.")
    start_idx: int | None = Field(None, description="Start character position.")
    end_idx: int | None = Field(None, description="End character position.")


class TokenData(BaseModel):
    """
    Data for a single token in the analyzed text.
    """

    text: str | None = Field(None, description="Token text.")
    lemma: str | None = Field(None, description="Token lemma.")
    pos: str | None = Field(None, description="Part of speech tag.")
    dep: str | None = Field(None, description="Syntactic Dependency Relation.")
    tag: str | None = Field(None, description="Detailed POS tag.")
    start_idx: int | None = Field(None, description="Start character position.")
    end_idx: int | None = Field(None, description="End character position.")
    head: TokenReference | None = Field(None, description="Head token reference.")
    children: list[TokenReference] = Field(
        default_factory=list, description="List of child token references."
    )
    ancestors: list[TokenReference] = Field(
        default_factory=list, description="List of ancestor token references."
    )
    subtree: list[TokenReference] = Field(
        default_factory=list, description="List of tokens in the subtree."
    )
    is_alpha: bool | None = Field(None, description="Is alphabetic.")
    is_stop: bool | None = Field(None, description="Is stop word.")
    is_oov: bool | None = Field(None, description="Is out-of-vocabulary.")
    like_url: bool | None = Field(None, description="Is like a URL.")
    is_digit: bool | None = Field(None, description="Is a digit.")
    ent_iob: str | None = Field(
        None, description="Inside-Outside-Beginning tag for named entities."
    )
    ent_type: str | None = Field(None, description="Named entity type.")
    ent_kb_id: str | None = Field(
        None, description="Knowledge base ID for the entity."
    )
    ent_id: int | None = Field(None, description="Entity ID.")
    sentiment: float | None = Field(None, description="Sentiment score.")
    concepcy: ConcepcyData | None = Field(
        default_factory=ConcepcyData, description="Concepcy data."
    )
    wordnet: WordNetData | None = Field(
        default_factory=WordNetData, description="WordNet data."
    )


class EntityData(BaseModel):
    """
    Data for a named entity in the analyzed text.
    """

    text: str = Field(..., description="Entity text.")
    label: str | None = Field(None, description="Entity label.")
    kb_id: str | None = Field(None, description="Knowledge base ID.")
    dbpedia: DBpediaData | None = Field(None, description="DBpedia data.")


class NLPAnalysisResponse(BaseModel):
    """
    Response model for NLP analysis API.
    """

    tokens: list[TokenData] = Field(
        default_factory=list, description="List of token data."
    )
    entities: list[EntityData] = Field(
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
