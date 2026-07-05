"""spaCy NLP processor adapter for named entity recognition and tokenization."""

from typing import Any, Optional

try:
    import spacy

    HAS_SPACY = True
except ImportError:
    HAS_SPACY = False
    spacy = None  # type: ignore[assignment]

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from domain.extraction.ports import (
    NLPEntity,
    NLPResult,
    NounChunkSpan,
    OpenExtractionResult,
    OpenToken,
)
from utils.async_executor import run_sync_in_executor
from utils.logger import get_logger

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

# spaCy's base NER pipeline does not produce per-entity confidence scores.
# This synthetic default is used as a conservative confidence for all extracted entities.
SPACY_DEFAULT_ENTITY_CONFIDENCE = 0.85


class SpacyNLPProcessor:
    """
    NLP processor implementation using spaCy.

    Provides graceful degradation when the spaCy model is not installed.
    If the model cannot be loaded, all methods return empty results without raising exceptions.
    """

    MODEL_NAME = "en_core_web_sm"

    def __init__(self, model_name: Optional[str] = None) -> None:
        """
        Initialize the spaCy NLP processor.

        Attempts to load the configured spaCy model. If loading fails, logs a warning
        and continues in a degraded state where is_ready() returns False.

        Args:
            model_name: spaCy model to load (e.g. 'en_core_web_sm', 'en_core_web_lg').
                Defaults to MODEL_NAME. Exposed so the open-extraction pipeline can
                tune the model as an optimization knob.
        """
        self._model_name = model_name or self.MODEL_NAME
        self._nlp: Optional[Any] = None
        if not HAS_SPACY:
            logger.warning("spaCy not installed. NLP processing will be unavailable.")
            return
        try:
            self._nlp = spacy.load(self._model_name)
            logger.info(f"Loaded spaCy model: {self._model_name}")
        except OSError as e:
            logger.warning(
                f"spaCy model '{self._model_name}' not available: {e}. "
                "NLP processing will be unavailable."
            )

    def is_ready(self) -> bool:
        """
        Check if the processor is ready to use.

        Returns:
            True if the spaCy model is loaded and ready, False otherwise.
                 No exception is raised if the model is unavailable.
        """
        return self._nlp is not None

    def process(self, text: str) -> NLPResult:
        """
        Perform full NLP processing on text.

        Args:
            text: Text to process

        Returns:
            NLPResult with tokens, entities, and language.
            Returns empty results if the processor is not ready.
        """
        with tracer.start_as_current_span("nlp.process") as span:
            span.set_attribute("nlp.model", self._model_name)
            span.set_attribute("nlp.text_length", len(text))

            try:
                if not self.is_ready():
                    logger.warning(
                        "NLP processor not ready. Returning empty results for text:"
                        f" {text[:100]}"
                    )
                    return NLPResult(tokens=(), entities=[], noun_chunks=[], language="unknown")

                assert self._nlp is not None
                doc = self._nlp(text)
                tokens = tuple(token.text for token in doc)
                entities = self._extract_from_doc(doc)
                noun_chunks = [chunk.text for chunk in doc.noun_chunks]

                return NLPResult(
                    tokens=tokens,
                    entities=entities,
                    noun_chunks=noun_chunks,
                    language="en",
                )
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR))
                span.record_exception(e)
                raise

    def extract_entities(self, text: str) -> list[NLPEntity]:
        """
        Extract named entities from text.

        Args:
            text: Text to process

        Returns:
            List of NLPEntity objects found in the text.
            Returns empty list if the processor is not ready.
        """
        with tracer.start_as_current_span("nlp.process") as span:
            span.set_attribute("nlp.model", self._model_name)
            span.set_attribute("nlp.text_length", len(text))

            try:
                if not self.is_ready():
                    logger.warning(
                        "NLP processor not ready. Returning empty entities for text:"
                        f" {text[:100]}"
                    )
                    return []

                assert self._nlp is not None
                doc = self._nlp(text)
                return self._extract_from_doc(doc)
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR))
                span.record_exception(e)
                raise

    def _extract_from_doc(self, doc) -> list[NLPEntity]:
        """
        Extract entities from a processed spaCy Doc object.

        Args:
            doc: Processed spaCy Doc object

        Returns:
            List of NLPEntity objects with optional entity linking URIs.
        """
        entities = []
        for ent in doc.ents:
            linked_uri = None

            # Populate linked_uri from entity linker KB if available
            if hasattr(ent, "kb_id_") and ent.kb_id_:
                linked_uri = ent.kb_id_

            entities.append(
                NLPEntity(
                    text=ent.text,
                    label=ent.label_,
                    start=ent.start_char,
                    end=ent.end_char,
                    confidence=SPACY_DEFAULT_ENTITY_CONFIDENCE,
                    linked_uri=linked_uri,
                )
            )

        return entities

    def process_open(self, text: str) -> OpenExtractionResult:
        """
        Perform open-extraction NLP processing on text.

        Produces per-token POS + dependency metadata and noun-chunk spans for
        the open knowledge-graph extraction flow. Returns an empty result if the
        processor is not ready.

        Args:
            text: Text to process

        Returns:
            OpenExtractionResult with tokens, noun-chunk spans, sentence count,
            and language.
        """
        with tracer.start_as_current_span("nlp.process_open") as span:
            span.set_attribute("nlp.model", self._model_name)
            span.set_attribute("nlp.text_length", len(text))

            try:
                if not self.is_ready():
                    logger.warning(
                        "NLP processor not ready. Returning empty open result for text:"
                        f" {text[:100]}"
                    )
                    return OpenExtractionResult(
                        tokens=(), noun_chunks=(), sentence_count=0, language="unknown"
                    )

                assert self._nlp is not None
                doc = self._nlp(text)
                return self._build_open_result(doc)
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR))
                span.record_exception(e)
                raise

    def _build_open_result(self, doc) -> OpenExtractionResult:
        """
        Build an OpenExtractionResult from a processed spaCy Doc.

        Args:
            doc: Processed spaCy Doc object

        Returns:
            OpenExtractionResult with per-token POS/dependency metadata and
            noun-chunk spans.
        """
        # Map each token index to the index of its sentence.
        sentence_index_by_token: dict[int, int] = {}
        sentence_count = 0
        for sentence_count, sent in enumerate(doc.sents):
            for tok in sent:
                sentence_index_by_token[tok.i] = sentence_count
        sentence_count = sentence_count + 1 if sentence_index_by_token else 0

        tokens = tuple(
            OpenToken(
                index=tok.i,
                text=tok.text,
                lemma=tok.lemma_.lower(),
                pos=tok.pos_,
                tag=tok.tag_,
                dep=tok.dep_,
                head_index=tok.head.i,
                start=tok.idx,
                end=tok.idx + len(tok.text),
                sentence_index=sentence_index_by_token.get(tok.i, 0),
                is_stop=bool(tok.is_stop),
                is_alpha=bool(tok.is_alpha),
            )
            for tok in doc
        )

        noun_chunks = tuple(
            NounChunkSpan(
                text=chunk.text,
                start_token=chunk.start,
                end_token=chunk.end,
                root_index=chunk.root.i,
                start=chunk.start_char,
                end=chunk.end_char,
                sentence_index=sentence_index_by_token.get(chunk.root.i, 0),
            )
            for chunk in doc.noun_chunks
        )

        return OpenExtractionResult(
            tokens=tokens,
            noun_chunks=noun_chunks,
            sentence_count=sentence_count,
            language="en",
        )

    async def process_open_async(self, text: str) -> OpenExtractionResult:
        """
        Perform open-extraction NLP processing on text (async version).

        Runs the processing in a thread pool to avoid blocking the event loop.

        Args:
            text: Text to process

        Returns:
            OpenExtractionResult with tokens, noun-chunk spans, sentence count,
            and language.
        """
        return await run_sync_in_executor(self.process_open, text)

    async def process_async(self, text: str) -> NLPResult:
        """
        Perform full NLP processing on text (async version).

        Runs the processing in a thread pool to avoid blocking the event loop.

        Args:
            text: Text to process

        Returns:
            NLPResult with tokens, entities, and language.
            Returns empty results if the processor is not ready.
        """
        return await run_sync_in_executor(self.process, text)

    async def extract_entities_async(self, text: str) -> list[NLPEntity]:
        """
        Extract named entities from text (async version).

        Runs the extraction in a thread pool to avoid blocking the event loop.

        Args:
            text: Text to process

        Returns:
            List of NLPEntity objects found in the text.
            Returns empty list if the processor is not ready.
        """
        return await run_sync_in_executor(self.extract_entities, text)
