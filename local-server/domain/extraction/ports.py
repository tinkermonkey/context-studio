"""
Extraction domain ports (interfaces).

Protocol definitions for external dependencies required by the extraction domain,
plus value objects used in port contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol, Sequence

if TYPE_CHECKING:
    from domain.extraction.entities import ExtractionResult, ExtractionRun


# ============================================================================
# Value types used in port contracts
# ============================================================================


@dataclass(frozen=True)
class NLPEntity:
    """
    A named entity identified by an NLP processor.

    Attributes:
        text: The literal text of the entity in the source document
        label: The entity type label (e.g., 'ORG', 'PERSON', 'GPE')
        start: Character offset where entity begins
        end: Character offset where entity ends
        confidence: Confidence score from 0.0 to 1.0
        linked_uri: Optional URI linking to external knowledge base

    Raises:
        ValueError: If confidence is not 0.0-1.0 or end < start
    """

    text: str
    label: str
    start: int
    end: int
    confidence: float
    linked_uri: str | None = None

    def __post_init__(self) -> None:
        """Validate NLP entity invariants."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be 0.0-1.0, got {self.confidence}")
        if self.end < self.start:
            raise ValueError(f"end must be >= start, got start={self.start}, end={self.end}")


@dataclass(frozen=True)
class NLPResult:
    """
    Complete output from NLP processing.

    Attributes:
        tokens: List of tokenized words/phrases
        entities: Named entities identified in the text
        noun_chunks: List of noun phrases extracted from the text
        language: Detected language code (e.g., 'en', 'es')
    """

    tokens: tuple[str, ...]
    entities: list[NLPEntity]
    noun_chunks: list[str]
    language: str


@dataclass(frozen=True)
class OpenToken:
    """
    A single token with the spaCy POS + dependency metadata needed to build
    concept candidates (NOUN/PROPN/ADJ) and relation candidates (VERB + edges).

    Attributes:
        index: Token position in the document (spaCy token.i). Used to resolve
            head_index and noun-chunk spans by reference.
        text: Literal token text
        lemma: Lemmatized form, lowercased by the adapter (spaCy lemma_)
        pos: Coarse universal POS tag (e.g. 'NOUN', 'PROPN', 'ADJ', 'VERB')
        tag: Fine-grained POS tag (e.g. 'NN', 'NNP', 'VBZ')
        dep: Dependency relation to the head (e.g. 'nsubj', 'dobj', 'amod')
        head_index: Token index of this token's syntactic head. Equals `index`
            for a sentence root (spaCy convention: root.head is itself).
        start: Character offset where the token begins
        end: Character offset where the token ends (exclusive)
        sentence_index: Zero-based index of the sentence this token belongs to
        is_stop: True if spaCy flags this as a stopword
        is_alpha: True if the token is alphabetic

    Raises:
        ValueError: If index, head_index, or sentence_index is negative,
            or end < start
    """

    index: int
    text: str
    lemma: str
    pos: str
    tag: str
    dep: str
    head_index: int
    start: int
    end: int
    sentence_index: int
    is_stop: bool
    is_alpha: bool

    def __post_init__(self) -> None:
        """Validate open token invariants."""
        if self.index < 0:
            raise ValueError(f"index must be >= 0, got {self.index}")
        if self.head_index < 0:
            raise ValueError(f"head_index must be >= 0, got {self.head_index}")
        if self.sentence_index < 0:
            raise ValueError(f"sentence_index must be >= 0, got {self.sentence_index}")
        if self.end < self.start:
            raise ValueError(f"end must be >= start, got start={self.start}, end={self.end}")


@dataclass(frozen=True)
class NounChunkSpan:
    """
    A noun-phrase span with the token references needed to recover its
    grammatical role (via the root token's dep and head).

    Attributes:
        text: Literal text of the noun chunk
        start_token: Index of the first token in the chunk (inclusive)
        end_token: Index one past the last token in the chunk (exclusive,
            matching spaCy span.end convention)
        root_index: Token index of the chunk's syntactic root (spaCy chunk.root.i).
            The root's dep/head/connected-verb drive concept-candidate priority.
        start: Character offset where the chunk begins
        end: Character offset where the chunk ends (exclusive)
        sentence_index: Zero-based index of the sentence this chunk belongs to

    Raises:
        ValueError: If token/char offsets are negative or inverted, or
            root_index falls outside [start_token, end_token)
    """

    text: str
    start_token: int
    end_token: int
    root_index: int
    start: int
    end: int
    sentence_index: int

    def __post_init__(self) -> None:
        """Validate noun-chunk span invariants."""
        if self.start_token < 0:
            raise ValueError(f"start_token must be >= 0, got {self.start_token}")
        if self.end_token < self.start_token:
            raise ValueError(
                f"end_token must be >= start_token, got "
                f"start_token={self.start_token}, end_token={self.end_token}"
            )
        if not self.start_token <= self.root_index < self.end_token:
            raise ValueError(
                f"root_index {self.root_index} must be within "
                f"[{self.start_token}, {self.end_token})"
            )
        if self.end < self.start:
            raise ValueError(f"end must be >= start, got start={self.start}, end={self.end}")
        if self.sentence_index < 0:
            raise ValueError(f"sentence_index must be >= 0, got {self.sentence_index}")


@dataclass(frozen=True)
class OpenExtractionResult:
    """
    Rich per-token spaCy output for open knowledge-graph extraction.

    Unlike NLPResult (which carries only token/chunk text), this captures the
    POS + dependency structure needed to derive concept candidates
    (NOUN/PROPN/ADJ + noun chunks) and relation candidates (VERB + dep edges).

    Attributes:
        tokens: All tokens in document order; tokens[i].index == i
        noun_chunks: Noun-phrase spans detected across the document
        sentence_count: Number of sentences detected
        language: Detected language code (e.g. 'en')

    Raises:
        ValueError: If sentence_count is negative
    """

    tokens: tuple[OpenToken, ...]
    noun_chunks: tuple[NounChunkSpan, ...]
    sentence_count: int
    language: str

    def __post_init__(self) -> None:
        """Validate open extraction result and cross-collection index invariants.

        Beyond sentence_count, this enforces the referential invariants that the
        pure candidate builders rely on, converting what would otherwise be
        latent IndexErrors deep inside those functions into a single, clear
        boundary error:

        - ``tokens[i].index == i`` for every position i (positional identity).
        - every ``OpenToken.head_index`` is a valid index into ``tokens``
          (a sentence root points at itself, which is in range).
        - every ``NounChunkSpan.root_index`` is a valid index into ``tokens``,
          and each chunk's ``start_token``/``end_token`` span lies within
          ``tokens`` (end_token is exclusive, so it may equal ``len(tokens)``).
        """
        if self.sentence_count < 0:
            raise ValueError(f"sentence_count must be >= 0, got {self.sentence_count}")

        token_count = len(self.tokens)
        for i, token in enumerate(self.tokens):
            if token.index != i:
                raise ValueError(f"tokens[{i}].index must equal its position, got {token.index}")
            if not 0 <= token.head_index < token_count:
                raise ValueError(
                    f"tokens[{i}].head_index {token.head_index} out of range " f"[0, {token_count})"
                )

        for j, chunk in enumerate(self.noun_chunks):
            if not 0 <= chunk.start_token < token_count:
                raise ValueError(
                    f"noun_chunks[{j}].start_token {chunk.start_token} out of range "
                    f"[0, {token_count})"
                )
            if not 0 < chunk.end_token <= token_count:
                raise ValueError(
                    f"noun_chunks[{j}].end_token {chunk.end_token} out of range "
                    f"(0, {token_count}]"
                )
            if not 0 <= chunk.root_index < token_count:
                raise ValueError(
                    f"noun_chunks[{j}].root_index {chunk.root_index} out of range "
                    f"[0, {token_count})"
                )


@dataclass(frozen=True)
class ClusterAssignment:
    """
    The cluster label assigned to one input vector.

    Attributes:
        index: Position of the vector in the input list
        label: Cluster id, or -1 for noise / unclustered points

    Raises:
        ValueError: If index is negative
    """

    index: int
    label: int

    def __post_init__(self) -> None:
        """Validate cluster assignment invariants."""
        if self.index < 0:
            raise ValueError(f"index must be >= 0, got {self.index}")


@dataclass(frozen=True)
class ReferenceResult:
    """
    A single search result from a reference source.

    Attributes:
        uri: Unique URI for this resource
        label: Human-readable label or title
        description: Optional longer description
        confidence: Confidence score from 0.0 to 1.0
        source: Which reference source returned this result

    Raises:
        ValueError: If confidence is not 0.0-1.0
    """

    uri: str
    label: str
    description: str | None = None
    confidence: float = 1.0
    source: str = ""

    def __post_init__(self) -> None:
        """Validate reference result invariants."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be 0.0-1.0, got {self.confidence}")


@dataclass(frozen=True)
class ReferenceRelation:
    """
    A relationship between concepts in a reference source.

    Attributes:
        subject_uri: URI of the source concept
        predicate: Type of relationship (e.g., 'narrower', 'broader')
        object_uri: URI of the target concept
        weight: Optional strength/confidence weight for the relation
        source: Which reference source this relation comes from
    """

    subject_uri: str
    predicate: str
    object_uri: str
    weight: float | None = None
    source: str = ""


@dataclass(frozen=True)
class RecognitionMatch:
    """
    An existing graph individual that an extracted mention was resolved to.

    Attributes:
        individual_id: ID of the matched existing individual.
        title: The individual's canonical title — the label recognition
            adopts when it resolves a mention to this node.
        score: Confidence the match was accepted at, 0.0-1.0. 1.0 for an
            exact-label match; the vector cosine similarity for a vector or
            LLM-tiebreak resolution.
        method: Which cascade tier produced the match — an exact label match,
            a clear vector-similarity winner (including the no-LLM ambiguous
            fallback, still a vector-based pick), or an LLM tiebreak among
            near-equal candidates.

    Raises:
        ValueError: If score is not 0.0-1.0
    """

    individual_id: str
    title: str
    score: float
    method: Literal["exact", "vector", "llm"]

    def __post_init__(self) -> None:
        """Validate recognition match invariants."""
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"score must be 0.0-1.0, got {self.score}")


# ============================================================================
# Port interfaces (Protocols)
# ============================================================================


class NLPProcessor(Protocol):
    """
    Port for natural language processing.

    Implementations provide entity extraction, tokenization, and
    language detection capabilities.
    """

    def process(self, text: str) -> NLPResult:
        """
        Perform full NLP processing on text.

        Args:
            text: Text to process

        Returns:
            NLPResult with tokens, entities, and language
        """
        ...

    def extract_entities(self, text: str) -> list[NLPEntity]:
        """
        Extract named entities from text.

        Args:
            text: Text to process

        Returns:
            List of NLPEntity objects found in the text
        """
        ...

    def process_open(self, text: str) -> OpenExtractionResult:
        """
        Perform open-extraction NLP processing on text.

        Produces rich per-token POS and dependency metadata plus noun-chunk
        spans, sufficient to build concept and relation candidates without a
        second pass. Returns an empty result (no tokens, no chunks,
        sentence_count=0) if the processor is not ready.

        Args:
            text: Text to process

        Returns:
            OpenExtractionResult with tokens, noun-chunk spans, sentence count,
            and language
        """
        ...

    def is_ready(self) -> bool:
        """
        Check if the processor is ready to use.

        Returns:
            True if initialized and ready, False otherwise
        """
        ...


class ClusteringPort(Protocol):
    """
    Port for clustering embedding vectors.

    Used by the open-extraction schema flow to distil many concept-candidate
    embeddings into a smaller set of cluster representatives. The backing
    adapter (e.g. sklearn AgglomerativeClustering/DBSCAN) lives at
    adapters/clustering/sklearn_clusterer.py.
    """

    def cluster(
        self,
        vectors: list[list[float]],
        distance_threshold: float,
        min_cluster_size: int = 1,
    ) -> list[ClusterAssignment]:
        """
        Cluster embedding vectors.

        Args:
            vectors: Embedding vectors to cluster; all must share one dimensionality
            distance_threshold: Maximum distance for two points to share a cluster
                (cosine/Euclidean per the adapter's configured metric)
            min_cluster_size: Clusters smaller than this collapse to noise (label -1)

        Returns:
            One ClusterAssignment per input vector, in input order. Returns an
            empty list when given an empty input.
        """
        ...


class ReferenceSource(Protocol):
    """
    Port for external reference knowledge sources.

    Implementations provide search and relationship retrieval from
    sources like ConceptNet, DBpedia, Wikidata, or schema.org.
    """

    @property
    def source_name(self) -> str:
        """
        Get the name of this reference source.

        Returns:
            Human-readable name (e.g., 'ConceptNet', 'DBpedia')
        """
        ...

    def search(self, term: str, limit: int = 10) -> list[ReferenceResult]:
        """
        Search for entities matching a term.

        Args:
            term: Search query
            limit: Maximum number of results

        Returns:
            List of matching ReferenceResult objects
        """
        ...

    def get_relations(self, uri: str, limit: int = 10) -> list[ReferenceRelation]:
        """
        Get relationships connected to a URI.

        Args:
            uri: URI of the resource to find relations for
            limit: Maximum number of relations

        Returns:
            List of ReferenceRelation objects
        """
        ...

    def is_available(self) -> bool:
        """
        Check if this source is available.

        Returns:
            True if the source can be queried, False otherwise
        """
        ...

    async def search_async(self, term: str, limit: int = 10) -> list[ReferenceResult]:
        """
        Search for entities matching a term asynchronously.

        Async variant of search(). Implementations must ensure this method
        does not block the event loop, typically by delegating to the
        synchronous search() method via an executor.

        Args:
            term: Search query
            limit: Maximum number of results

        Returns:
            List of matching ReferenceResult objects
        """
        ...

    async def get_relations_async(self, uri: str, limit: int = 10) -> list[ReferenceRelation]:
        """
        Get relationships connected to a URI asynchronously.

        Async variant of get_relations(). Implementations must ensure this method
        does not block the event loop, typically by delegating to the
        synchronous get_relations() method via an executor.

        Args:
            uri: URI of the resource to find relations for
            limit: Maximum number of relations

        Returns:
            List of ReferenceRelation objects
        """
        ...

    async def is_available_async(self) -> bool:
        """
        Check if this source is available asynchronously.

        Async variant of is_available(). Implementations must ensure this method
        does not block the event loop, typically by delegating to the
        synchronous is_available() method via an executor.

        Returns:
            True if the source can be queried, False otherwise
        """
        ...


class IndividualRecognizer(Protocol):
    """
    Port for resolving an extracted individual mention to an existing graph node.

    Entity resolution ("does this individual already exist?") kept as its own
    port — separate from ExtractionService's inline recognition logic — so the
    match cascade can be tuned and observed independently. Implementations run
    a three-tier cascade over the candidate classes: an exact label match
    returns immediately, a single clear vector-similarity winner returns
    immediately, and multiple candidates within a small score band of each
    other trigger an LLM tiebreak (degrading to the highest-scoring candidate
    when no LLM is configured).
    """

    def recognize(
        self,
        label: str,
        context: str,
        class_ids: Sequence[str],
        taxonomy_id: str | None = None,
        threshold: float | None = None,
    ) -> RecognitionMatch | None:
        """
        Resolve an extracted mention to an existing individual, or None.

        Args:
            label: The extracted mention's surface text (e.g. "K8s").
            context: Surrounding text (e.g. the mention's sentence) offered to
                an LLM tiebreak to disambiguate near-equal candidates.
            class_ids: Candidate classes to scope the search to — matching is
                restricted to individuals instantiating at least one of these.
                Cross-class matching is out of scope for this port's first
                adapter, but the signature does not preclude it later.
            taxonomy_id: Optional taxonomy to further scope candidates within.
                Reserved for a future multi-taxonomy index; the first adapter
                does not filter on it.
            threshold: Minimum similarity (0.0-1.0) a vector or LLM-tiebreak
                resolution must clear to be accepted. Defaults to the
                implementation's own configured value when omitted, kept
                independent of any class-grounding similarity threshold used
                elsewhere in extraction.

        Returns:
            A RecognitionMatch on resolution, or None when no existing
            individual is confidently identified as the same entity.
        """
        ...


class ExtractionRepository(Protocol):
    """
    Port for persistence of extraction results.

    Implementations store and retrieve extraction results, processing metrics,
    and related extraction pipeline artifacts.
    """

    def save_extraction_result(self, result: ExtractionResult) -> ExtractionResult:
        """
        Save an extraction result to persistent storage.

        Args:
            result: The ExtractionResult to save

        Returns:
            The saved ExtractionResult (may have updated metadata like id or timestamp)
        """
        ...

    def get_extraction_result(self, result_id: str) -> ExtractionResult | None:
        """
        Retrieve an extraction result by ID.

        Args:
            result_id: The ID of the extraction result

        Returns:
            The ExtractionResult or None if not found
        """
        ...

    def list_extraction_results(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[ExtractionResult]:
        """
        List extraction results with pagination.

        Args:
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            Sequence of ExtractionResult objects
        """
        ...


class ExtractionRunRepository(Protocol):
    """
    Port for persistence of extraction runs.

    Implementations store and retrieve extraction run records, which track
    extraction operations from initiation through completion, including
    pipeline configuration, LLM settings, and resource metrics.
    """

    def save_extraction_run(self, run: ExtractionRun) -> ExtractionRun:
        """
        Save an extraction run to persistent storage.

        Args:
            run: The ExtractionRun to save

        Returns:
            The saved ExtractionRun
        """
        ...

    def get_extraction_run(self, run_id: str) -> ExtractionRun | None:
        """
        Retrieve an extraction run by ID.

        Args:
            run_id: The ID of the extraction run

        Returns:
            The ExtractionRun or None if not found
        """
        ...

    def list_extraction_runs(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[ExtractionRun]:
        """
        List extraction runs with pagination.

        Args:
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            Sequence of ExtractionRun objects
        """
        ...

    def update_extraction_run(self, run: ExtractionRun) -> ExtractionRun:
        """
        Update an existing extraction run.

        Args:
            run: The ExtractionRun with updated fields

        Returns:
            The updated ExtractionRun
        """
        ...
