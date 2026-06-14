"""Integration tests for SpacyNLPProcessor."""

import pytest


def test_process_returns_empty_result_when_not_ready():
    """Test that process() returns empty result when processor is not ready."""
    from adapters.nlp.spacy_processor import SpacyNLPProcessor
    from domain.extraction.ports import NLPResult

    # Create a processor in degraded state
    processor = SpacyNLPProcessor()
    processor._nlp = None

    result = processor.process("Hello world.")
    assert isinstance(result, NLPResult)
    assert result.tokens == []
    assert result.entities == []
    assert result.language == "unknown"


def test_extract_entities_returns_empty_list_when_not_ready():
    """Test that extract_entities() returns empty list when processor is not ready."""
    from adapters.nlp.spacy_processor import SpacyNLPProcessor

    processor = SpacyNLPProcessor()
    processor._nlp = None

    entities = processor.extract_entities("Hello world.")
    assert entities == []


@pytest.mark.nlp
def test_extract_entities_returns_entities():
    """Test that extract_entities() returns entities when model is available."""
    from adapters.nlp.spacy_processor import SpacyNLPProcessor

    processor = SpacyNLPProcessor()
    if not processor.is_ready():
        pytest.skip("spaCy model not installed")

    entities = processor.extract_entities("Apple acquired Beats Electronics in 2014.")
    assert len(entities) >= 1
    assert all(e.text and e.label for e in entities)


@pytest.mark.nlp
def test_process_returns_tokens_and_language():
    """Test that process() returns tokens and language when model is available."""
    from adapters.nlp.spacy_processor import SpacyNLPProcessor

    processor = SpacyNLPProcessor()
    if not processor.is_ready():
        pytest.skip("spaCy model not installed")

    result = processor.process("Hello world.")
    assert len(result.tokens) > 0
    assert result.language == "en"


@pytest.mark.nlp
def test_extract_entities_populates_text_label_offsets():
    """Test that extracted entities have correct text, label, and character offsets."""
    from adapters.nlp.spacy_processor import SpacyNLPProcessor

    processor = SpacyNLPProcessor()
    if not processor.is_ready():
        pytest.skip("spaCy model not installed")

    text = "Apple acquired Beats Electronics in 2014."
    entities = processor.extract_entities(text)

    assert len(entities) >= 1
    for entity in entities:
        # Verify entity text matches the substring at the given offsets
        assert text[entity.start : entity.end] == entity.text
        # Verify entity has a label
        assert isinstance(entity.label, str) and entity.label


@pytest.mark.nlp
def test_model_name_is_configured():
    """Test that the model name is correctly configured."""

    from adapters.nlp.spacy_processor import SpacyNLPProcessor

    assert SpacyNLPProcessor.MODEL_NAME == "en_core_web_sm"


def test_model_name_override():
    """Test that an explicit model_name overrides the default."""
    from adapters.nlp.spacy_processor import SpacyNLPProcessor

    processor = SpacyNLPProcessor(model_name="en_core_web_md")
    assert processor._model_name == "en_core_web_md"


def test_process_open_returns_empty_result_when_not_ready():
    """process_open() returns an empty OpenExtractionResult when not ready."""
    from adapters.nlp.spacy_processor import SpacyNLPProcessor
    from domain.extraction.ports import OpenExtractionResult

    processor = SpacyNLPProcessor()
    processor._nlp = None

    result = processor.process_open("Hello world.")
    assert isinstance(result, OpenExtractionResult)
    assert result.tokens == []
    assert result.noun_chunks == []
    assert result.sentence_count == 0
    assert result.language == "unknown"


@pytest.mark.nlp
def test_process_open_populates_pos_dep_and_offsets():
    """process_open() exposes POS, dependency, head, and accurate char offsets."""
    from adapters.nlp.spacy_processor import SpacyNLPProcessor

    processor = SpacyNLPProcessor()
    if not processor.is_ready():
        pytest.skip("spaCy model not installed")

    text = "Apache Kafka streams events between microservices."
    result = processor.process_open(text)

    assert len(result.tokens) > 0
    assert result.sentence_count >= 1
    assert result.language == "en"

    # Token indices are positional; offsets recover the surface text;
    # POS/dep/head are populated.
    for i, tok in enumerate(result.tokens):
        assert tok.index == i
        assert text[tok.start : tok.end] == tok.text
        assert tok.pos and tok.dep
        assert 0 <= tok.head_index < len(result.tokens)

    # At least one verb and one noun-chunk are found; chunk roots are in range.
    assert any(tok.pos == "VERB" for tok in result.tokens)
    assert len(result.noun_chunks) > 0
    for chunk in result.noun_chunks:
        assert chunk.start_token <= chunk.root_index < chunk.end_token
        assert text[chunk.start : chunk.end] == chunk.text


@pytest.mark.nlp
def test_process_open_assigns_sentence_indices():
    """process_open() numbers sentences and tags tokens with their sentence."""
    from adapters.nlp.spacy_processor import SpacyNLPProcessor

    processor = SpacyNLPProcessor()
    if not processor.is_ready():
        pytest.skip("spaCy model not installed")

    result = processor.process_open("Kafka streams events. Systems scale well.")
    assert result.sentence_count == 2
    sentence_indices = {tok.sentence_index for tok in result.tokens}
    assert sentence_indices == {0, 1}
