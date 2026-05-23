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
