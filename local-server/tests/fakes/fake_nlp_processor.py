"""Fake implementation of NLPProcessor for testing."""

from domain.extraction.ports import (
    NLPEntity,
    NLPResult,
    NounChunkSpan,
    OpenExtractionResult,
    OpenToken,
)


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

    def process_open(self, text: str) -> OpenExtractionResult:
        """
        Perform open-extraction NLP processing on text.

        Produces deterministic per-token data by whitespace tokenization: each
        word becomes a NOUN token heading the sentence root, and each alphabetic
        word also becomes a single-token noun chunk. Enough structure for
        consumers to exercise the open-extraction code paths.

        Args:
            text: Text to process

        Returns:
            OpenExtractionResult with tokens and noun-chunk spans.

        Raises:
            RuntimeError: If should_fail is True
        """
        if self.should_fail:
            raise RuntimeError("NLP processor error")

        self.call_count += 1
        self.last_text_processed = text

        words = text.split() if text else []
        tokens: list[OpenToken] = []
        chunks: list[NounChunkSpan] = []
        offset = 0
        for i, word in enumerate(words):
            start = offset
            end = offset + len(word)
            offset = end + 1
            tokens.append(
                OpenToken(
                    index=i,
                    text=word,
                    lemma=word.lower(),
                    pos="NOUN",
                    tag="NN",
                    dep="ROOT" if i == 0 else "nsubj",
                    head_index=0,
                    start=start,
                    end=end,
                    sentence_index=0,
                    is_stop=False,
                    is_alpha=word.isalpha(),
                )
            )
            if word.isalpha():
                chunks.append(
                    NounChunkSpan(
                        text=word,
                        start_token=i,
                        end_token=i + 1,
                        root_index=i,
                        start=start,
                        end=end,
                        sentence_index=0,
                    )
                )

        return OpenExtractionResult(
            tokens=tokens,
            noun_chunks=chunks,
            sentence_count=1 if tokens else 0,
            language=self.language,
        )

    def is_ready(self) -> bool:
        """
        Check if the processor is ready to use.

        Returns:
            Always True for the fake implementation
        """
        return True
