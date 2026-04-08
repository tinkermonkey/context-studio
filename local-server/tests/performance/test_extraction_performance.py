"""Performance tests for knowledge extraction at various text scales.

Tests measure end-to-end extraction time at multiple text lengths (100, 500, 2000, 5000 words)
using both fake and real NLP adapters.
"""

import sys
import os
import time
import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from domain.extraction.services import ExtractionService
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_llm_provider import FakeLLMProvider
from tests.fakes.fake_nlp_processor import FakeNLPProcessor
from tests.fakes.fake_extraction_repository import FakeExtractionRepository
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_reference_source import FakeReferenceSource


def _generate_sample_text(num_words: int) -> str:
    """Generate sample text with specified word count.

    Args:
        num_words: Number of words to generate

    Returns:
        Sample text string
    """
    words = [
        "Microsoft", "Google", "Apple", "Amazon", "Meta", "Tesla", "Netflix", "Uber",
        "technology", "company", "software", "hardware", "cloud", "artificial",
        "intelligence", "machine", "learning", "data", "analysis", "processing",
        "develops", "creates", "produces", "manufactures", "builds", "designs",
        "launches", "releases", "announces", "reports", "introduces", "unveils"
    ]

    # Generate text by cycling through words
    text = []
    for i in range(num_words):
        text.append(words[i % len(words)])

    return " ".join(text)


def _setup_extraction_service(
    nlp_processor: "object | None" = None,
) -> ExtractionService:
    """Set up extraction service with fake dependencies.

    Args:
        nlp_processor: Optional NLP processor. If None, uses FakeNLPProcessor.

    Returns:
        ExtractionService instance
    """
    ontology_repo = FakeOntologyRepository()
    ontology_repo.setup_sample_data()
    embedding_service = FakeEmbeddingService()
    llm_provider = FakeLLMProvider(response_content='{"entities": []}')
    if nlp_processor is None:
        nlp_processor = FakeNLPProcessor()
    reference_source = FakeReferenceSource()
    extraction_repo = FakeExtractionRepository()
    event_publisher = FakeEventPublisher()

    service = ExtractionService(
        ontology_repo=ontology_repo,
        embedding_service=embedding_service,
        llm=llm_provider,
        nlp=nlp_processor,
        reference_sources=[reference_source],
        extraction_repo=extraction_repo,
        event_publisher=event_publisher,
    )
    return service


@pytest.mark.performance
def test_extraction_100_words_fake_nlp():
    """Measure end-to-end extraction time for 100 words with fake NLP."""
    service = _setup_extraction_service()
    text = _generate_sample_text(100)

    start = time.perf_counter()
    result = service.extract(text)
    elapsed = time.perf_counter() - start

    print(f"\nExtraction (100 words, fake NLP): {elapsed:.4f}s")
    assert result is not None
    assert elapsed < 1.0


@pytest.mark.performance
def test_extraction_500_words_fake_nlp():
    """Measure end-to-end extraction time for 500 words with fake NLP."""
    service = _setup_extraction_service()
    text = _generate_sample_text(500)

    start = time.perf_counter()
    result = service.extract(text)
    elapsed = time.perf_counter() - start

    print(f"\nExtraction (500 words, fake NLP): {elapsed:.4f}s")
    assert result is not None
    assert elapsed < 2.0


@pytest.mark.performance
def test_extraction_2000_words_fake_nlp():
    """Measure end-to-end extraction time for 2000 words with fake NLP."""
    service = _setup_extraction_service()
    text = _generate_sample_text(2000)

    start = time.perf_counter()
    result = service.extract(text)
    elapsed = time.perf_counter() - start

    print(f"\nExtraction (2000 words, fake NLP): {elapsed:.4f}s")
    assert result is not None
    assert elapsed < 5.0


@pytest.mark.performance
def test_extraction_5000_words_fake_nlp():
    """Measure end-to-end extraction time for 5000 words with fake NLP."""
    service = _setup_extraction_service()
    text = _generate_sample_text(5000)

    start = time.perf_counter()
    result = service.extract(text)
    elapsed = time.perf_counter() - start

    print(f"\nExtraction (5000 words, fake NLP): {elapsed:.4f}s")
    assert result is not None
    assert elapsed < 10.0


@pytest.mark.performance
@pytest.mark.nlp
def test_extraction_100_words_real_nlp():
    """Measure end-to-end extraction time for 100 words with real spaCy NLP.

    This test requires the spaCy library and en_core_web_sm model to be installed.
    """
    try:
        from adapters.nlp.spacy_processor import SpacyNLPProcessor
    except ImportError:
        pytest.skip("SpacyNLPProcessor not installed")

    nlp_processor = SpacyNLPProcessor()
    if not nlp_processor.is_ready():
        pytest.skip("spaCy model en_core_web_sm not available")

    service = _setup_extraction_service(nlp_processor=nlp_processor)
    text = _generate_sample_text(100)

    start = time.perf_counter()
    result = service.extract(text)
    elapsed = time.perf_counter() - start

    print(f"\nExtraction (100 words, real spaCy NLP): {elapsed:.4f}s")
    assert result is not None
    assert elapsed < 5.0


@pytest.mark.performance
@pytest.mark.nlp
def test_extraction_500_words_real_nlp():
    """Measure end-to-end extraction time for 500 words with real spaCy NLP.

    This test requires the spaCy library and en_core_web_sm model to be installed.
    """
    try:
        from adapters.nlp.spacy_processor import SpacyNLPProcessor
    except ImportError:
        pytest.skip("SpacyNLPProcessor not installed")

    nlp_processor = SpacyNLPProcessor()
    if not nlp_processor.is_ready():
        pytest.skip("spaCy model en_core_web_sm not available")

    service = _setup_extraction_service(nlp_processor=nlp_processor)
    text = _generate_sample_text(500)

    start = time.perf_counter()
    result = service.extract(text)
    elapsed = time.perf_counter() - start

    print(f"\nExtraction (500 words, real spaCy NLP): {elapsed:.4f}s")
    assert result is not None
    assert elapsed < 10.0
