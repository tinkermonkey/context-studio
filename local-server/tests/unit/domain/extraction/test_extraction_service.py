"""
Unit tests for ExtractionService.

Tests the four-layer extraction pipeline, deduplication logic, error handling,
and configuration options.
"""

from unittest.mock import Mock

import pytest

from domain.extraction.entities import ExtractedEntity, ExtractionResult
from domain.extraction.exceptions import ExtractionError
from domain.extraction.services import ExtractionService


class FakeOntologyRepository:
    """Fake ontology repository for testing."""

    def get_by_semantic_similarity(self, embedding, limit=5):
        return []


class FakeEmbeddingService:
    """Fake embedding service for testing."""

    def embed(self, text):
        return [0.0] * 384  # Dummy embedding


class FakeLLMProvider:
    """Fake LLM provider for testing."""

    def complete(self, system_prompt, user_prompt, model, **kwargs):
        from domain.pipelines.ports import LLMResponse

        # Simple response for testing
        return LLMResponse(
            content='[{"label": "Apple", "type": "ORG", "confidence": 0.9}]',
            tokens_in=10,
            tokens_out=20,
            duration_ms=100.0,
            finish_reason="stop",
            model=model,
        )

    def is_model_available(self, model):
        return True

    def list_available_models(self):
        return ["gpt-4"]


class FakeNLPProcessor:
    """Fake NLP processor for testing."""

    def extract_entities(self, text):
        from domain.extraction.ports import NLPEntity

        return [
            NLPEntity(
                text="Steve",
                label="PERSON",
                start=0,
                end=5,
                confidence=0.95,
                linked_uri=None,
            ),
        ]

    def is_ready(self):
        return True

    def process(self, text):
        return Mock()


class FakeReferenceSource:
    """Fake reference source for testing."""

    @property
    def source_name(self):
        return "TestSource"

    def search(self, term, limit=10):
        from domain.extraction.ports import ReferenceResult

        if term.lower() == "apple":
            return [
                ReferenceResult(
                    uri="https://example.com/Apple",
                    label="Apple Inc.",
                    description="Technology company",
                    confidence=0.95,
                    source="TestSource",
                )
            ]
        return []

    def get_relations(self, uri, limit=10):
        return []

    def is_available(self):
        return True


class FakeExtractionRepository:
    """Fake extraction repository for testing."""

    def __init__(self):
        self.saved_results = []

    def save_extraction_result(self, result):
        self.saved_results.append(result)
        return result

    def get_extraction_result(self, result_id):
        for result in self.saved_results:
            if result.id == result_id:
                return result
        return None

    def list_extraction_results(self, limit=100, offset=0):
        return self.saved_results[offset : offset + limit]


class FakeExtractionRunRepository:
    """Fake extraction run repository for testing."""

    def __init__(self):
        self.saved_runs = []

    def save_extraction_run(self, run):
        self.saved_runs.append(run)
        return run

    def get_extraction_run(self, run_id):
        for run in self.saved_runs:
            if run.id == run_id:
                return run
        return None

    def list_extraction_runs(self, limit=100, offset=0):
        return self.saved_runs[offset : offset + limit]

    def update_extraction_run(self, run):
        # Find and update the run
        for i, existing_run in enumerate(self.saved_runs):
            if existing_run.id == run.id:
                self.saved_runs[i] = run
                return run
        raise ValueError(f"ExtractionRun with id {run.id} not found")


class FakeEventPublisher:
    """Fake event publisher for testing."""

    def __init__(self):
        self.published_events = []

    def publish(self, event) -> list[tuple[str, Exception]]:
        self.published_events.append(event)
        return []


@pytest.fixture
def service_with_fakes():
    """Create an ExtractionService with fake dependencies."""
    ontology_repo = FakeOntologyRepository()
    embedding_service = FakeEmbeddingService()
    llm = FakeLLMProvider()
    nlp = FakeNLPProcessor()
    reference_sources = [FakeReferenceSource()]
    event_publisher = FakeEventPublisher()
    extraction_repo = FakeExtractionRepository()
    extraction_run_repo = FakeExtractionRunRepository()

    service = ExtractionService(
        ontology_repo=ontology_repo,
        embedding_service=embedding_service,
        llm=llm,
        nlp=nlp,
        reference_sources=reference_sources,
        event_publisher=event_publisher,
        extraction_repo=extraction_repo,
        extraction_run_repo=extraction_run_repo,
        similarity_threshold=0.85,
    )

    return {
        "service": service,
        "ontology_repo": ontology_repo,
        "embedding_service": embedding_service,
        "llm": llm,
        "nlp": nlp,
        "reference_sources": reference_sources,
        "event_publisher": event_publisher,
        "extraction_repo": extraction_repo,
        "extraction_run_repo": extraction_run_repo,
    }


class TestExtractionServiceConfiguration:
    """Test configuration and initialization."""

    def test_similarity_threshold_configurable(self, service_with_fakes):
        """Test that similarity threshold is configurable at runtime."""
        service = service_with_fakes["service"]
        assert service._similarity_threshold == 0.85

    def test_similarity_threshold_validation(self, service_with_fakes):
        """Test that invalid similarity thresholds are rejected."""
        ontology_repo = FakeOntologyRepository()
        embedding_service = FakeEmbeddingService()
        llm = FakeLLMProvider()
        nlp = FakeNLPProcessor()
        reference_sources = []
        event_publisher = FakeEventPublisher()
        extraction_repo = FakeExtractionRepository()
        extraction_run_repo = FakeExtractionRunRepository()

        with pytest.raises(ValueError):
            ExtractionService(
                ontology_repo=ontology_repo,
                embedding_service=embedding_service,
                llm=llm,
                nlp=nlp,
                reference_sources=reference_sources,
                event_publisher=event_publisher,
                extraction_repo=extraction_repo,
                extraction_run_repo=extraction_run_repo,
                similarity_threshold=1.5,  # Invalid: > 1.0
            )


class TestExtractionServiceDeduplication:
    """Test deduplication logic, especially reference enrichment."""

    def test_dedup_empty_list(self, service_with_fakes):
        """Test deduplication of empty list."""
        service = service_with_fakes["service"]
        result = service._deduplicate([])
        assert result == []

    def test_dedup_single_entity(self, service_with_fakes):
        """Test deduplication of single entity."""
        service = service_with_fakes["service"]
        entity = ExtractedEntity(
            label="Test",
            entity_type="ORG",
            source_layer=1,
            confidence=0.9,
        )
        result = service._deduplicate([entity])
        assert len(result) == 1
        assert result[0].label == "Test"

    def test_dedup_reference_enrichment_preferred(self, service_with_fakes):
        """Test that enriched entities from layer 3 are preferred over original."""
        service = service_with_fakes["service"]

        # Original entity from layer 1
        original = ExtractedEntity(
            id="entity-1",
            label="Apple",
            entity_type="ORG",
            source_layer=1,
            confidence=0.9,
            uri=None,
            description=None,
        )

        # Enriched copy from layer 3 with same ID
        enriched = ExtractedEntity(
            id="entity-1",  # SAME ID
            label="Apple",
            entity_type="ORG",
            source_layer=3,  # Reference layer
            confidence=0.9,
            uri="https://example.com/Apple",
            description="Technology company",
            properties={"reference_source": "TestSource"},
        )

        # Deduplicate
        result = service._deduplicate([original, enriched])

        # Should keep enriched version (has URI and description)
        assert len(result) == 1
        kept = result[0]
        assert kept.uri == "https://example.com/Apple"
        assert kept.description == "Technology company"
        assert "reference_source" in kept.properties

    def test_dedup_preserves_enrichment_data_merge(self, service_with_fakes):
        """Test that enrichment data is merged, not lost."""
        service = service_with_fakes["service"]

        # Original with some data
        original = ExtractedEntity(
            id="entity-2",
            label="Microsoft",
            entity_type="ORG",
            source_layer=1,
            confidence=0.85,
            uri=None,
            description="Software company",
            properties={"extracted_by": "llm"},
        )

        # Enriched with additional data
        enriched = ExtractedEntity(
            id="entity-2",
            label="Microsoft",
            entity_type="ORG",
            source_layer=3,
            confidence=0.85,
            uri="https://example.com/Microsoft",
            description="Multinational tech corporation",  # Better description
            properties={"reference_source": "DBpedia", "extracted_by": "llm"},
        )

        result = service._deduplicate([original, enriched])

        assert len(result) == 1
        kept = result[0]
        # Should have enriched URI
        assert kept.uri == "https://example.com/Microsoft"
        # Should have enriched description
        assert kept.description == "Multinational tech corporation"
        # Should have both property sources
        assert kept.properties["reference_source"] == "DBpedia"
        assert kept.properties["extracted_by"] == "llm"

    def test_dedup_priority_respects_layer_order(self, service_with_fakes):
        """Test that dedup respects layer priority order."""
        service = service_with_fakes["service"]

        # Layer 1 (LLM) - highest priority
        llm_entity = ExtractedEntity(
            id="entity-3",
            label="Google",
            entity_type="ORG",
            source_layer=1,
            confidence=0.95,
        )

        # Layer 0 (KG) - second priority
        kg_entity = ExtractedEntity(
            id="entity-3",
            label="Google",
            entity_type="ORG",
            source_layer=0,
            confidence=0.85,
        )

        # Deduplicate
        result = service._deduplicate([kg_entity, llm_entity])

        # Should keep layer 1 (higher priority) since there's no enrichment
        assert len(result) == 1
        assert result[0].source_layer == 1
        assert result[0].confidence == 0.95

    def test_dedup_label_similarity_threshold(self, service_with_fakes):
        """Test that label similarity respects the threshold."""
        service = service_with_fakes["service"]

        # Entities with very similar labels (Levenshtein distance = 1, similarity ~0.94)
        entity1 = ExtractedEntity(
            label="Microsoft",
            entity_type="ORG",
            source_layer=1,
            confidence=0.9,
        )

        entity2 = ExtractedEntity(
            label="Microsft",  # One character missing (Levenshtein distance = 1)
            entity_type="ORG",
            source_layer=2,
            confidence=0.85,
        )

        result = service._deduplicate([entity1, entity2])

        # With default threshold (0.85), should recognize as similar
        # (similarity = 1.0 - 1/9 = 0.889 >= 0.85)
        # and keep only the higher-priority one
        assert len(result) == 1
        assert result[0].label == "Microsoft"

    def test_dedup_multiple_entities_with_enrichment(self, service_with_fakes):
        """Test deduplication with multiple entities and selective enrichment."""
        service = service_with_fakes["service"]

        # Entity A from layer 1
        entity_a = ExtractedEntity(
            id="id-a",
            label="Apple",
            entity_type="ORG",
            source_layer=1,
            confidence=0.9,
        )

        # Entity B from layer 1
        entity_b = ExtractedEntity(
            id="id-b",
            label="Google",
            entity_type="ORG",
            source_layer=1,
            confidence=0.9,
        )

        # Enriched A from layer 3
        entity_a_enriched = ExtractedEntity(
            id="id-a",
            label="Apple",
            entity_type="ORG",
            source_layer=3,
            uri="https://example.com/Apple",
            description="Tech company",
            properties={"reference_source": "ConceptNet"},
        )

        # Deduplicate
        result = service._deduplicate([entity_a, entity_b, entity_a_enriched])

        assert len(result) == 2
        # Find enriched A
        enriched_a = next((e for e in result if e.id == "id-a"), None)
        assert enriched_a is not None
        assert enriched_a.uri == "https://example.com/Apple"

        # Find B (not enriched)
        b = next((e for e in result if e.id == "id-b"), None)
        assert b is not None
        assert b.uri is None


class TestExtractionServicePersistence:
    """Test persistence and error handling."""

    def test_extraction_returns_result_even_if_persistence_fails(self, service_with_fakes):
        """Test that extraction returns result even if persistence fails."""
        service = service_with_fakes["service"]
        extraction_repo = service_with_fakes["extraction_repo"]

        # Make persistence fail

        def failing_save(result):
            raise RuntimeError("Database connection failed")

        extraction_repo.save_extraction_result = failing_save

        # Extraction should still return a result
        result = service.extract("Test text with Apple in it")

        assert isinstance(result, ExtractionResult)
        assert len(result.extracted_entities) > 0  # Has entities despite persistence failure
        # Event should still be published
        assert len(service_with_fakes["event_publisher"].published_events) > 0

    def test_extraction_event_published_even_if_persistence_fails(self, service_with_fakes):
        """Test that completion event is published even if persistence fails."""
        service = service_with_fakes["service"]
        extraction_repo = service_with_fakes["extraction_repo"]
        event_publisher = service_with_fakes["event_publisher"]

        # Make persistence fail
        extraction_repo.save_extraction_result = Mock(side_effect=RuntimeError("DB error"))

        # Run extraction
        service.extract("Test text")

        # Event should still be published
        assert len(event_publisher.published_events) > 0
        from domain.extraction.events import ExtractionCompleted

        assert any(isinstance(e, ExtractionCompleted) for e in event_publisher.published_events)

    def test_analyze_text_returns_result_even_if_persistence_fails(self, service_with_fakes):
        """Test that analyze_text returns result even if persistence fails."""
        service = service_with_fakes["service"]
        extraction_repo = service_with_fakes["extraction_repo"]

        extraction_repo.save_extraction_result = Mock(
            side_effect=RuntimeError("Database connection failed")
        )

        result = service.analyze_text("Test text about Steve Jobs")

        assert isinstance(result, ExtractionResult)
        assert len(service_with_fakes["event_publisher"].published_events) > 0

    def test_enrich_from_references_returns_result_even_if_persistence_fails(
        self, service_with_fakes
    ):
        """Test that enrich_from_references returns result even if persistence fails."""
        service = service_with_fakes["service"]
        extraction_repo = service_with_fakes["extraction_repo"]
        from domain.extraction.entities import ExtractedEntity as DomainEntity

        extraction_repo.save_extraction_result = Mock(
            side_effect=RuntimeError("Database connection failed")
        )

        entities = [DomainEntity(label="Apple", entity_type="ORG", source_layer=1, confidence=0.9)]
        result = service.enrich_from_references("Apple is a tech company", entities)

        assert isinstance(result, ExtractionResult)
        assert len(service_with_fakes["event_publisher"].published_events) > 0

    def test_event_handler_failure_warning_logged(self, service_with_fakes):
        """Test that a warning is logged when an event handler fails."""
        from unittest.mock import patch

        fakes = service_with_fakes
        ontology_repo = fakes["ontology_repo"]
        embedding_service = fakes["embedding_service"]
        llm = fakes["llm"]
        nlp = fakes["nlp"]
        reference_sources = fakes["reference_sources"]
        extraction_repo = fakes["extraction_repo"]
        extraction_run_repo = fakes["extraction_run_repo"]

        class FailingEventPublisher:
            """Event publisher that simulates a handler failure."""

            def publish(self, event) -> list[tuple[str, Exception]]:
                return [("audit_handler", RuntimeError("handler failed"))]

        service = ExtractionService(
            ontology_repo=ontology_repo,
            embedding_service=embedding_service,
            llm=llm,
            nlp=nlp,
            reference_sources=reference_sources,
            event_publisher=FailingEventPublisher(),
            extraction_repo=extraction_repo,
            extraction_run_repo=extraction_run_repo,
            similarity_threshold=0.85,
        )

        with patch("domain.extraction.services._logger") as mock_logger:
            result = service.extract("Test text")

        assert isinstance(result, ExtractionResult)
        mock_logger.warning.assert_called_once()
        warning_msg = mock_logger.warning.call_args[0][0]
        assert "Event handlers failed" in warning_msg


class TestExtractionServiceErrorHandling:
    """Test error handling and edge cases."""

    def test_empty_text_raises_error(self, service_with_fakes):
        """Test that empty text raises ExtractionError."""
        service = service_with_fakes["service"]

        with pytest.raises(ExtractionError):
            service.extract("")

        with pytest.raises(ExtractionError):
            service.extract("   ")

    def test_layer_failure_doesnt_stop_pipeline(self, service_with_fakes):
        """Test that a single layer failure doesn't stop the pipeline."""
        service = service_with_fakes["service"]
        nlp = service_with_fakes["nlp"]

        # Make NLP layer fail
        nlp.extract_entities = Mock(side_effect=RuntimeError("NLP model error"))

        # But LLM layer has ready() that returns False to trigger exception
        nlp.is_ready = Mock(return_value=False)

        # Extraction should still succeed with partial results
        result = service.extract("Test text")

        assert isinstance(result, ExtractionResult)
        # Some layers may have failed, but the result is still valid
        assert result.total_duration_ms >= 0


class TestNlpGroundedTyping:
    """
    The retained NLP-grounded typing component (issue #1141): spaCy noun chunks
    -> vector retrieval -> LLM confirmation. Not the baseline pipeline (retrieval
    underperforms LLM typing on generic-class ontologies), but kept as a
    component, so its core invariants are locked.
    """

    def _service(self, *, schema_index, llm=None):
        from domain.extraction.services import ExtractionService

        return ExtractionService(
            ontology_repo=_RepoWithClass(),
            embedding_service=FakeEmbeddingService(),
            llm=llm or _ConfirmingLLM("technology.systemsoftware"),
            nlp=_OneChunkNLP("Kubernetes"),
            reference_sources=[],
            event_publisher=Mock(),
            extraction_repo=Mock(),
            extraction_run_repo=Mock(),
            schema_index=schema_index,
            extraction_mode="nlp_grounded",
        )

    def test_degrades_to_no_typing_without_a_schema_index(self):
        service = self._service(schema_index=None)
        triples, tokens = service._type_individuals_nlp_grounded(
            "Kubernetes runs pods.", object(), "onto", "m", 0.0
        )
        assert triples == [] and tokens == 0

    def test_confirmed_match_becomes_an_is_a_triple_typed_to_the_matched_class(self):
        service = self._service(schema_index=_OneMatchIndex())
        triples, _ = service._type_individuals_nlp_grounded(
            "Kubernetes runs pods.", _Ontology(), "onto", "m", 0.0
        )
        assert len(triples) == 1
        t = triples[0]
        assert t["subject"]["label"] == "Kubernetes"
        assert t["predicate"]["label"] == "is_a"
        assert t["object"]["kind"] == "class"
        assert t["object"]["label"] == "technology.systemsoftware"

    def test_llm_declining_all_candidates_yields_no_triple(self):
        service = self._service(schema_index=_OneMatchIndex(), llm=_ConfirmingLLM("none"))
        triples, _ = service._type_individuals_nlp_grounded(
            "Kubernetes runs pods.", _Ontology(), "onto", "m", 0.0
        )
        assert triples == []


class _Ontology:
    id = "onto-1"
    title = "Test Ontology"


class _OneChunkNLP:
    """process_open with a single NOUN-headed noun chunk."""

    def __init__(self, chunk_text):
        self._chunk_text = chunk_text

    def process_open(self, text):
        from domain.extraction.ports import NounChunkSpan, OpenExtractionResult, OpenToken

        tok = OpenToken(
            index=0, text=self._chunk_text, lemma=self._chunk_text.lower(), pos="PROPN",
            tag="NNP", dep="nsubj", head_index=0, start=0, end=len(self._chunk_text),
            sentence_index=0, is_stop=False, is_alpha=True,
        )
        chunk = NounChunkSpan(
            text=self._chunk_text, start_token=0, end_token=1, root_index=0,
            start=0, end=len(self._chunk_text), sentence_index=0,
        )
        return OpenExtractionResult(
            tokens=(tok,), noun_chunks=(chunk,), sentence_count=1, language="en",
        )


class _OneMatchIndex:
    def search(self, query_embedding, kinds, top_k=20, threshold=0.0, taxonomy_id=None):
        from domain.ontology.ports import SchemaMatch

        return [
            SchemaMatch(
                entity_id="cls-1", kind="class", label="System Software", score=0.5,
                matched_field="definition", external_id="technology.systemsoftware",
                identifier="systemsoftware",
            )
        ]


class _RepoWithClass:
    def get_class(self, class_id):
        from domain.ontology.entities import Class

        return Class(
            id=class_id, concept_scheme_id="cs", taxonomy_id="onto-1",
            title="System Software", identifier="systemsoftware",
            description="Software that provides a runtime environment.",
        )


class _ConfirmingLLM:
    def __init__(self, choice):
        self._choice = choice

    def complete(self, system_prompt, user_prompt, model, **kwargs):
        import json as _json

        from domain.pipelines.ports import LLMResponse

        return LLMResponse(
            content=_json.dumps({"class": self._choice}), model=model,
            tokens_in=5, tokens_out=5, duration_ms=1.0, finish_reason="stop",
        )


class TestRecognition:
    """
    Recognition logic (#1142): resolve extracted mentions to existing individuals.
    Precision-first — the tests lock exact-label, conservative vector acceptance,
    class scoping, the ambiguity/acronym guards (false-merge control), reference
    rewriting, and the index=None no-op. All infra-free (fake index + repo).
    """

    CLASS_SW = "cls-systemsoftware"
    CLASS_DB = "cls-datastore"
    _VEC = {
        "Kubernetes": [1.0, 0.0, 0.0],
        "K8s": [0.98, 0.02, 0.0],           # ~1.0 cos to Kubernetes
        "Nextflow": [0.0, 1.0, 0.0],        # orthogonal
        "Container Orchestrator": [0.6, 0.8, 0.0],  # ~0.6 cos -> below threshold
        "borderline": [0.93, 0.3676, 0.0],  # ~0.93 cos: passes long bar, fails acronym bar
        "Docker Swarm": [0.97, 0.243, 0.0],  # ~0.97 cos -> close to Kubernetes (ambiguity)
    }

    def _service(self, index):
        from domain.extraction.services import ExtractionService

        return ExtractionService(
            ontology_repo=_RecogRepo(),
            embedding_service=_RecogEmbedding(self._VEC),
            llm=Mock(),
            nlp=Mock(),
            reference_sources=[],
            event_publisher=Mock(),
            extraction_repo=Mock(),
            extraction_run_repo=Mock(),
            individual_index=index,
        )

    def _index_with_kubernetes(self):
        from tests.fakes.fake_individual_vector_index import FakeIndividualVectorIndex

        idx = FakeIndividualVectorIndex(self._VEC)
        idx.add("kube-id", "Kubernetes", [self.CLASS_SW])
        return idx

    def _typing_triple(self, mention, class_ref="technology.systemsoftware"):
        return {
            "subject": {"kind": "individual", "id": None, "label": mention},
            "predicate": {"label": "is_a"},
            "object": {"kind": "class", "label": class_ref},
        }

    def test_no_op_without_an_index(self):
        service = self._service(index=None)
        triples = [self._typing_triple("K8s")]
        out = service._recognize_individuals(triples, _Ontology())
        assert out[0]["subject"]["label"] == "K8s"
        assert out[0]["subject"]["id"] is None

    def test_exact_label_resolves_and_adopts_canonical_title(self):
        service = self._service(self._index_with_kubernetes())
        triples = [self._typing_triple("kubernetes")]  # case variant
        service._recognize_individuals(triples, _Ontology())
        assert triples[0]["subject"]["label"] == "Kubernetes"
        assert triples[0]["subject"]["id"] == "kube-id"

    def test_vector_match_resolves_a_variant(self):
        service = self._service(self._index_with_kubernetes())
        triples = [self._typing_triple("K8s")]
        service._recognize_individuals(triples, _Ontology())
        assert triples[0]["subject"]["label"] == "Kubernetes"
        assert triples[0]["subject"]["id"] == "kube-id"

    def test_below_threshold_stays_a_new_node(self):
        service = self._service(self._index_with_kubernetes())
        triples = [self._typing_triple("Container Orchestrator")]
        service._recognize_individuals(triples, _Ontology())
        assert triples[0]["subject"]["label"] == "Container Orchestrator"
        assert triples[0]["subject"]["id"] is None

    def test_ambiguity_margin_refuses_to_guess(self):
        # Two existing individuals both very close to the query -> refuse (false-merge guard).
        idx = self._index_with_kubernetes()
        idx.add("swarm-id", "Docker Swarm", [self.CLASS_SW])
        service = self._service(idx)
        triples = [self._typing_triple("K8s")]
        service._recognize_individuals(triples, _Ontology())
        assert triples[0]["subject"]["id"] is None  # ambiguous -> new node

    def test_acronym_guard_applies_a_stricter_bar_to_short_mentions(self):
        # "borderline" ~0.93: a long mention would resolve, but rename it to a
        # short surface so the acronym bar (0.95) rejects it.
        service = self._service(self._index_with_kubernetes())
        t = self._typing_triple("xyz")  # len 3 < recog_min_len
        # map the short surface to the borderline vector
        service._embedding_service = _RecogEmbedding({**self._VEC, "xyz": self._VEC["borderline"]})
        service._recognize_individuals([t], _Ontology())
        assert t["subject"]["id"] is None

    def test_class_scoping_prevents_cross_class_resolution(self):
        service = self._service(self._index_with_kubernetes())
        # same mention but typed to the Data Store class -> Kubernetes (SW class) excluded
        triples = [self._typing_triple("K8s", class_ref="application.dataobject")]
        service._recognize_individuals(triples, _Ontology())
        assert triples[0]["subject"]["id"] is None

    def test_empty_graph_is_a_no_op(self):
        # The scored tournament situation: an index is wired but the graph has no
        # prior individuals, so recognition resolves nothing and rewrites nothing
        # -> output identical to recognition off (non-regression guarantee).
        from tests.fakes.fake_individual_vector_index import FakeIndividualVectorIndex

        service = self._service(FakeIndividualVectorIndex(self._VEC))  # empty index
        triples = [self._typing_triple("K8s")]
        service._recognize_individuals(triples, _Ontology())
        assert triples[0]["subject"]["label"] == "K8s"
        assert triples[0]["subject"]["id"] is None

    def test_resolution_rewrites_relationship_object_references_too(self):
        service = self._service(self._index_with_kubernetes())
        triples = [
            self._typing_triple("K8s"),
            {
                "subject": {"kind": "individual", "id": None, "label": "Nextflow"},
                "predicate": {"label": "runs on"},
                "object": {"kind": "individual", "id": None, "label": "K8s"},
            },
        ]
        service._recognize_individuals(triples, _Ontology())
        assert triples[1]["object"]["label"] == "Kubernetes"
        assert triples[1]["object"]["id"] == "kube-id"


class _RecogEmbedding:
    def __init__(self, vectors):
        self._vectors = vectors

    def embed(self, text):
        return self._vectors.get(text, [0.0, 0.0, 0.0])

    def embed_batch(self, texts):
        return [self.embed(t) for t in texts]


class _RecogRepo:
    """Minimal ontology repo exposing the two classes recognition scopes against."""

    def list_concept_schemes(self, taxonomy_id, limit=None):
        return [type("S", (), {"id": "scheme-1"})()]

    def list_classes(self, concept_scheme_id, limit=None):
        from domain.ontology.entities import Class
        from domain.ontology.value_objects import ExternalReference

        return [
            Class(
                id=TestRecognition.CLASS_SW, concept_scheme_id="scheme-1", taxonomy_id="onto-1",
                title="System Software",
                external_references=[
                    ExternalReference(
                        source="dr", identifier="technology.systemsoftware", uri=None, metadata={}
                    )
                ],
            ),
            Class(
                id=TestRecognition.CLASS_DB, concept_scheme_id="scheme-1", taxonomy_id="onto-1",
                title="Data Object",
                external_references=[
                    ExternalReference(
                        source="dr", identifier="application.dataobject", uri=None, metadata={}
                    )
                ],
            ),
        ]


class TestTypeConceptObjects:
    """Test the _type_concept_objects method for pass-2 concept-object typing."""

    QUALITY_CLASS_ID = "quality-class-id"
    PROPERTY_DEF_ID = "prop-def-id"
    OUTCOME_CLASS_ID = "outcome-class-id"

    @pytest.fixture
    def ontology_with_classes_and_properties(self):
        """Create a mock ontology with classes and property definitions."""
        from domain.ontology.entities import Class, PropertyDefinition
        from domain.ontology.value_objects import ExternalReference

        quality_class = Class(
            id=self.QUALITY_CLASS_ID,
            concept_scheme_id="scheme-1",
            taxonomy_id="onto-1",
            title="Quality Attribute",
            identifier="quality",
            external_references=[
                ExternalReference(
                    source="dr", identifier="quality.attribute", uri=None, metadata={}
                )
            ],
        )

        outcome_class = Class(
            id=self.OUTCOME_CLASS_ID,
            concept_scheme_id="scheme-1",
            taxonomy_id="onto-1",
            title="Outcome",
            identifier="outcome",
            external_references=[
                ExternalReference(
                    source="dr", identifier="quality.outcome", uri=None, metadata={}
                )
            ],
        )

        improves_property = PropertyDefinition(
            id=self.PROPERTY_DEF_ID,
            identifier="improves",
            title="improves",
            canonical_predicate="improves",
            ontology_mapping=None,
            domain_class_id=None,
            range_class_id=self.QUALITY_CLASS_ID,
            external_references=[],
        )

        produces_property = PropertyDefinition(
            id="prop-produces-id",
            identifier="produces",
            title="produces",
            canonical_predicate="produces",
            ontology_mapping=None,
            domain_class_id=None,
            range_class_id=self.OUTCOME_CLASS_ID,
            external_references=[],
        )

        no_range_property = PropertyDefinition(
            id="prop-no-range-id",
            identifier="relates",
            title="relates",
            canonical_predicate="relates",
            ontology_mapping=None,
            domain_class_id=None,
            range_class_id=None,
            external_references=[],
        )

        ontology = Mock()
        ontology.id = "onto-1"

        return {
            "ontology": ontology,
            "quality_class": quality_class,
            "outcome_class": outcome_class,
            "improves_property": improves_property,
            "produces_property": produces_property,
            "no_range_property": no_range_property,
        }

    @pytest.fixture
    def extraction_service_for_typing(self, ontology_with_classes_and_properties):
        """Create an ExtractionService configured for concept-object typing tests."""
        ontology_repo = Mock()
        embedding_service = Mock()
        llm = Mock()
        nlp = Mock()
        event_publisher = Mock()
        extraction_repo = Mock()
        extraction_run_repo = Mock()

        ontology_data = ontology_with_classes_and_properties

        def mock_list_property_definitions(limit=None):
            return [
                ontology_data["improves_property"],
                ontology_data["produces_property"],
                ontology_data["no_range_property"],
            ]

        ontology_repo.list_property_definitions = mock_list_property_definitions

        def mock_list_concept_schemes(taxonomy_id=None, limit=None):
            scheme = Mock()
            scheme.id = "scheme-1"
            return [scheme]

        def mock_list_classes(concept_scheme_id=None, limit=None):
            return [
                ontology_data["quality_class"],
                ontology_data["outcome_class"],
            ]

        ontology_repo.list_concept_schemes = mock_list_concept_schemes
        ontology_repo.list_classes = mock_list_classes

        service = ExtractionService(
            ontology_repo=ontology_repo,
            embedding_service=embedding_service,
            llm=llm,
            nlp=nlp,
            reference_sources=[],
            event_publisher=event_publisher,
            extraction_repo=extraction_repo,
            extraction_run_repo=extraction_run_repo,
            similarity_threshold=0.85,
        )

        return {
            "service": service,
            "ontology": ontology_data["ontology"],
            "ontology_repo": ontology_repo,
            "quality_class": ontology_data["quality_class"],
            "outcome_class": ontology_data["outcome_class"],
        }

    def test_concept_object_with_resolvable_range(self, extraction_service_for_typing):
        """Test that a concept-object with a resolvable range emits a synthetic is_a triple."""
        service = extraction_service_for_typing["service"]
        ontology = extraction_service_for_typing["ontology"]
        quality_class = extraction_service_for_typing["quality_class"]

        individual_triples = [
            {
                "subject": {"kind": "individual", "label": "Caching"},
                "predicate": {"property_definition_id": None, "label": "is_a"},
                "object": {"kind": "class", "id": "cache-class-id", "label": "Pattern"},
                "confidence": 0.9,
                "provenance": "test",
            }
        ]

        relationship_triples = [
            {
                "subject": {"kind": "individual", "label": "Caching"},
                "predicate": {"property_definition_id": None, "label": "improves"},
                "object": {"kind": "individual", "label": "readability"},
                "confidence": 0.85,
                "provenance": "test",
            }
        ]

        result = service._type_concept_objects(
            relationship_triples, individual_triples, ontology
        )

        assert len(result) == 2
        typing_triple = result[1]

        assert typing_triple["subject"]["kind"] == "individual"
        assert typing_triple["subject"]["label"] == "readability"
        assert typing_triple["subject"]["class_id"] == self.QUALITY_CLASS_ID
        assert typing_triple["predicate"]["label"] == "is_a"
        assert typing_triple["object"]["kind"] == "class"
        assert typing_triple["object"]["id"] == self.QUALITY_CLASS_ID
        assert typing_triple["confidence"] == 0.85
        assert typing_triple["provenance"] == "test"

        assert relationship_triples[0]["predicate"]["property_definition_id"] == self.PROPERTY_DEF_ID

    def test_concept_object_property_definition_id_stamped(self, extraction_service_for_typing):
        """Test that property_definition_id is stamped on all relationship triples."""
        service = extraction_service_for_typing["service"]
        ontology = extraction_service_for_typing["ontology"]

        individual_triples = []
        relationship_triples = [
            {
                "subject": {"kind": "individual", "label": "System"},
                "predicate": {"property_definition_id": None, "label": "improves"},
                "object": {"kind": "individual", "label": "performance"},
                "confidence": 0.9,
                "provenance": "test",
            },
            {
                "subject": {"kind": "individual", "label": "Module"},
                "predicate": {"property_definition_id": None, "label": "produces"},
                "object": {"kind": "individual", "label": "result"},
                "confidence": 0.9,
                "provenance": "test",
            },
        ]

        result = service._type_concept_objects(
            relationship_triples, individual_triples, ontology
        )

        assert result[0]["predicate"]["property_definition_id"] == self.PROPERTY_DEF_ID
        assert result[1]["predicate"]["property_definition_id"] == "prop-produces-id"

    def test_concept_object_predicate_no_range(self, extraction_service_for_typing, caplog):
        """Test that a concept-object with a predicate having no range logs INFO and skips."""
        service = extraction_service_for_typing["service"]
        ontology = extraction_service_for_typing["ontology"]

        individual_triples = []
        relationship_triples = [
            {
                "subject": {"kind": "individual", "label": "Item"},
                "predicate": {"property_definition_id": None, "label": "relates"},
                "object": {"kind": "individual", "label": "something"},
                "confidence": 0.9,
                "provenance": "test",
            }
        ]

        with caplog.at_level("INFO"):
            result = service._type_concept_objects(
                relationship_triples, individual_triples, ontology
            )

        assert len(result) == 1
        assert not any(t.get("predicate", {}).get("label") == "is_a" for t in result)
        assert "no range_class_id" in caplog.text or "relates" in caplog.text

    def test_concept_object_predicate_not_found(self, extraction_service_for_typing, caplog):
        """Test that a concept-object whose predicate doesn't resolve logs INFO and skips."""
        service = extraction_service_for_typing["service"]
        ontology = extraction_service_for_typing["ontology"]

        individual_triples = []
        relationship_triples = [
            {
                "subject": {"kind": "individual", "label": "Item"},
                "predicate": {"property_definition_id": None, "label": "unknown_verb"},
                "object": {"kind": "individual", "label": "something"},
                "confidence": 0.9,
                "provenance": "test",
            }
        ]

        with caplog.at_level("INFO"):
            result = service._type_concept_objects(
                relationship_triples, individual_triples, ontology
            )

        assert len(result) == 1
        assert "PropertyDefinition not found" in caplog.text or "unknown_verb" in caplog.text

    def test_pass_1_individual_not_treated_as_concept_object(self, extraction_service_for_typing):
        """Test that pass-1 individuals are not treated as concept-objects."""
        service = extraction_service_for_typing["service"]
        ontology = extraction_service_for_typing["ontology"]

        individual_triples = [
            {
                "subject": {"kind": "individual", "label": "Caching"},
                "predicate": {"property_definition_id": None, "label": "is_a"},
                "object": {"kind": "class", "id": "cache-class-id", "label": "Pattern"},
                "confidence": 0.9,
                "provenance": "test",
            }
        ]

        relationship_triples = [
            {
                "subject": {"kind": "individual", "label": "Caching"},
                "predicate": {"property_definition_id": None, "label": "improves"},
                "object": {"kind": "individual", "label": "Caching"},
                "confidence": 0.85,
                "provenance": "test",
            }
        ]

        result = service._type_concept_objects(
            relationship_triples, individual_triples, ontology
        )

        assert len(result) == 1
        assert result[0]["predicate"]["label"] != "is_a"

    def test_class_object_not_treated_as_concept_object(self, extraction_service_for_typing):
        """Test that objects with kind='class' are not treated as concept-objects."""
        service = extraction_service_for_typing["service"]
        ontology = extraction_service_for_typing["ontology"]

        individual_triples = []
        relationship_triples = [
            {
                "subject": {"kind": "individual", "label": "Caching"},
                "predicate": {"property_definition_id": None, "label": "improves"},
                "object": {"kind": "class", "id": "quality-class-id", "label": "Quality Attribute"},
                "confidence": 0.85,
                "provenance": "test",
            }
        ]

        result = service._type_concept_objects(
            relationship_triples, individual_triples, ontology
        )

        assert len(result) == 1
        assert result[0] == relationship_triples[0]

    def test_multiple_concept_objects_same_label_deduplicated(self, extraction_service_for_typing):
        """Test that multiple triples referencing the same concept-object produce only one is_a triple."""
        service = extraction_service_for_typing["service"]
        ontology = extraction_service_for_typing["ontology"]

        individual_triples = [
            {
                "subject": {"kind": "individual", "label": "CacheLayer"},
                "predicate": {"property_definition_id": None, "label": "is_a"},
                "object": {"kind": "class", "id": "pattern-class-id", "label": "Pattern"},
                "confidence": 0.9,
                "provenance": "test",
            }
        ]

        relationship_triples = [
            {
                "subject": {"kind": "individual", "label": "CacheLayer"},
                "predicate": {"property_definition_id": None, "label": "improves"},
                "object": {"kind": "individual", "label": "readability"},
                "confidence": 0.85,
                "provenance": "test",
            },
            {
                "subject": {"kind": "individual", "label": "OptimizedCode"},
                "predicate": {"property_definition_id": None, "label": "improves"},
                "object": {"kind": "individual", "label": "readability"},
                "confidence": 0.9,
                "provenance": "test",
            },
        ]

        result = service._type_concept_objects(
            relationship_triples, individual_triples, ontology
        )

        typing_triples = [t for t in result if t.get("predicate", {}).get("label") == "is_a" and t.get("subject", {}).get("label") == "readability"]
        assert len(typing_triples) == 1

    def test_empty_relationship_triples_returns_empty(self, extraction_service_for_typing):
        """Test that empty relationship triples returns empty."""
        service = extraction_service_for_typing["service"]
        ontology = extraction_service_for_typing["ontology"]

        result = service._type_concept_objects([], [], ontology)
        assert result == []

    def test_no_ontology_id_returns_unchanged(self, extraction_service_for_typing):
        """Test that ontology without id returns relationship_triples unchanged."""
        service = extraction_service_for_typing["service"]
        ontology = Mock()
        ontology.id = None

        relationship_triples = [
            {
                "subject": {"kind": "individual", "label": "Test"},
                "predicate": {"property_definition_id": None, "label": "improves"},
                "object": {"kind": "individual", "label": "readability"},
                "confidence": 0.85,
                "provenance": "test",
            }
        ]

        result = service._type_concept_objects(relationship_triples, [], ontology)
        assert result == relationship_triples

    def test_range_class_id_present_but_class_not_in_ontology(self, extraction_service_for_typing, caplog):
        """Test that a concept-object with non-existent range_class_id logs INFO and skips synthetic triple."""
        from domain.ontology.entities import PropertyDefinition

        service = extraction_service_for_typing["service"]
        ontology = extraction_service_for_typing["ontology"]
        ontology_repo = extraction_service_for_typing["ontology_repo"]

        # Create a property with range_class_id pointing to non-existent class
        bad_range_property = PropertyDefinition(
            id="prop-bad-range-id",
            identifier="references",
            title="references",
            canonical_predicate="references",
            ontology_mapping=None,
            domain_class_id=None,
            range_class_id="non-existent-class-id",
            external_references=[],
        )

        # Get the original properties
        original_props = [
            extraction_service_for_typing["ontology_repo"].list_property_definitions(limit=None)[0],
            extraction_service_for_typing["ontology_repo"].list_property_definitions(limit=None)[1],
            extraction_service_for_typing["ontology_repo"].list_property_definitions(limit=None)[2],
        ]

        # Modify the mock to include the bad range property
        def mock_list_property_definitions(limit=None):
            return original_props + [bad_range_property]

        ontology_repo.list_property_definitions = mock_list_property_definitions

        individual_triples = []
        relationship_triples = [
            {
                "subject": {"kind": "individual", "label": "SomePattern"},
                "predicate": {"property_definition_id": None, "label": "references"},
                "object": {"kind": "individual", "label": "concept_object"},
                "confidence": 0.9,
                "provenance": "test",
            }
        ]

        with caplog.at_level("INFO"):
            result = service._type_concept_objects(
                relationship_triples, individual_triples, ontology
            )

        # Verify only original triple is returned (no synthetic triple)
        assert len(result) == 1
        assert result[0] == relationship_triples[0]
        # Verify property_definition_id was stamped
        assert result[0]["predicate"]["property_definition_id"] == "prop-bad-range-id"
        # Verify the specific log message appears
        assert "has range_class_id=non-existent-class-id, but class not found in ontology" in caplog.text

    def _is_typing_triple(self, triple):
        """Helper to identify typing triples."""
        return triple.get("object", {}).get("kind") == "class"
