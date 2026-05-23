"""Fake implementation of NLPProcessor for testing."""

import os
import sys
from domain.extraction.ports import NLPEntity, NLPResult

class FakeNLPProcessor:
    """Fake NLP processor that returns deterministic results for testing."""

    def __init__(self, language: str = "en", should_fail: bool = False) -> None:
        """
        Initialize the fake NLP processor.

        Args:
            language: Language code to return in results
            should_fail: If True, raise RuntimeError on process() and extract_entities() calls
        """

        self.language = language
        self.should_fail = should_fail
        self.call_count = 0
        self.last_text_processed: str | None = None

    def process(self, text: str) -> NLPResult:
        """
        Perform full NLP processing on text.

        Args:
            text: Text to process

        Returns:
            NLPResult with tokens, entities, and language

        Raises:
            RuntimeError: If should_fail is True
        """
        if self.should_fail:
            raise RuntimeError("NLP processor error")

        self.call_count += 1
        self.last_text_processed = text

        tokens = text.split() if text else []
        entities = self.extract_entities(text)

        return NLPResult(
            tokens=tokens,
            entities=entities,
            noun_chunks=[],
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

        Raises:
            RuntimeError: If should_fail is True
        """
        if self.should_fail:
            raise RuntimeError("NLP processor error")

        if not text:
            return []

        return [
            NLPEntity(
                text="FakeEntity",
                label="ORG",
                start=0,
                end=10,
                confidence=0.9,
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
