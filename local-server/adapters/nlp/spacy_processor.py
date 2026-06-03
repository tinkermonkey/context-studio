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

from domain.extraction.ports import NLPEntity, NLPResult
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

    def __init__(self) -> None:
        """
        Initialize the spaCy NLP processor.

        Attempts to load the configured spaCy model. If loading fails, logs a warning
        and continues in a degraded state where is_ready() returns False.
        """
        self._nlp: Optional[Any] = None
        if not HAS_SPACY:
            logger.warning("spaCy not installed. NLP processing will be unavailable.")
            return
        try:
            self._nlp = spacy.load(self.MODEL_NAME)
            logger.info(f"Loaded spaCy model: {self.MODEL_NAME}")
        except OSError as e:
            logger.warning(
                f"spaCy model '{self.MODEL_NAME}' not available: {e}. "
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
            span.set_attribute("nlp.model", self.MODEL_NAME)
            span.set_attribute("nlp.text_length", len(text))

            try:
                if not self.is_ready():
                    logger.warning(
                        "NLP processor not ready. Returning empty results for text:"
                        f" {text[:100]}"
                    )
                    return NLPResult(
                        tokens=[], entities=[], noun_chunks=[], language="unknown"
                    )

                assert self._nlp is not None
                doc = self._nlp(text)
                tokens = [token.text for token in doc]
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
            span.set_attribute("nlp.model", self.MODEL_NAME)
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
