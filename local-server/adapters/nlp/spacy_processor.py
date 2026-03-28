"""spaCy NLP processor adapter for named entity recognition and tokenization."""

import logging
from domain.extraction.ports import NLPProcessor, NLPResult, NLPEntity

logger = logging.getLogger(__name__)


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
        self._nlp = None
        try:
            import spacy

            self._nlp = spacy.load(self.MODEL_NAME)
            logger.info(f"Loaded spaCy model: {self.MODEL_NAME}")
        except (ImportError, OSError) as e:
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
        if not self.is_ready():
            return NLPResult(tokens=[], entities=[], language="unknown")

        doc = self._nlp(text)
        tokens = [token.text for token in doc]
        entities = self._extract_from_doc(doc)

        return NLPResult(tokens=tokens, entities=entities, language="en")

    def extract_entities(self, text: str) -> list[NLPEntity]:
        """
        Extract named entities from text.

        Args:
            text: Text to process

        Returns:
            List of NLPEntity objects found in the text.
            Returns empty list if the processor is not ready.
        """
        if not self.is_ready():
            return []

        doc = self._nlp(text)
        return self._extract_from_doc(doc)

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
                    linked_uri=linked_uri,
                )
            )

        return entities
