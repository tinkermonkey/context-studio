"""Fake implementation of NLPProcessor for testing."""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from domain.extraction.ports import NLPEntity, NLPResult


class FakeNLPProcessor:
    """Fake NLP processor that returns deterministic results for testing."""

    def __init__(self, language: str = "en") -> None:
        """
        Initialize the fake NLP processor.

        Args:
            language: Language code to return in results
        """
        self.language = language
        self.call_count = 0
        self.last_text_processed: str | None = None

    def process(self, text: str) -> NLPResult:
        """
        Perform full NLP processing on text.

        Args:
            text: Text to process

        Returns:
            NLPResult with tokens, entities, and language
        """
        self.call_count += 1
        self.last_text_processed = text

        tokens = text.split() if text else []
        entities = self.extract_entities(text)

        return NLPResult(
            tokens=tokens,
            entities=entities,
            language=self.language,
        )

    def extract_entities(self, text: str) -> list[NLPEntity]:
        """
        Extract named entities from text.

        Returns a deterministic entity for non-empty text.

        Args:
            text: Text to process

        Returns:
            List of NLPEntity objects found in the text
        """
        if not text:
            return []

        return [
            NLPEntity(
                text="FakeEntity",
                label="ORG",
                start=0,
                end=10,
                linked_uri=None,
            )
        ]

    def is_ready(self) -> bool:
        """
        Check if the processor is ready to use.

        Returns:
            Always True for the fake implementation
        """
        return True
