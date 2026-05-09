"""
Unit tests for ExtractionRun domain entity.

Tests cover entity construction, validation of invariants, and factory method
for the ExtractionRun first-class domain entity.
"""

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest
from uuid import uuid4

from domain.extraction.entities import ExtractionRun, ExtractionRunStatus


class TestExtractionRunConstruction:
    """Tests for ExtractionRun construction and field initialization."""

    def test_construct_with_all_fields(self):
        """Create an ExtractionRun with all fields specified."""
        run_id = str(uuid4())
        run = ExtractionRun(
            id=run_id,
            source_document_uri="https://example.com/doc.txt",
            source_text_hash="abc123def456",
            pipeline_config_ref="extraction-default",
            model="claude-opus-4-7",
            temperature=0.7,
            tokens_used=1500,
            duration_ms=5000,
            triples_extracted=25,
            triples_committed=20,
            status=ExtractionRunStatus.COMPLETED,
        )

        assert run.id == run_id
        assert run.source_document_uri == "https://example.com/doc.txt"
        assert run.source_text_hash == "abc123def456"
        assert run.pipeline_config_ref == "extraction-default"
        assert run.model == "claude-opus-4-7"
        assert run.temperature == 0.7
        assert run.tokens_used == 1500
        assert run.duration_ms == 5000
        assert run.triples_extracted == 25
        assert run.triples_committed == 20
        assert run.status == ExtractionRunStatus.COMPLETED

    def test_construct_minimal_fields(self):
        """Create an ExtractionRun with required fields only."""
        run_id = str(uuid4())
        run = ExtractionRun(
            id=run_id,
            source_document_uri=None,
            source_text_hash="hash123",
            pipeline_config_ref="default",
            model="gpt-4",
            temperature=0.0,
            tokens_used=0,
            duration_ms=0,
            triples_extracted=0,
            triples_committed=0,
            status=ExtractionRunStatus.PENDING,
        )

        assert run.id == run_id
        assert run.source_document_uri is None
        assert run.source_text_hash == "hash123"
        assert run.status == ExtractionRunStatus.PENDING

    def test_extraction_run_is_frozen(self):
        """ExtractionRun is frozen (immutable) after construction."""
        run = ExtractionRun(
            id=str(uuid4()),
            source_document_uri=None,
            source_text_hash="hash",
            pipeline_config_ref="default",
            model="gpt-4",
            temperature=0.5,
            tokens_used=0,
            duration_ms=0,
            triples_extracted=0,
            triples_committed=0,
            status=ExtractionRunStatus.PENDING,
        )

        with pytest.raises(AttributeError):
            run.status = ExtractionRunStatus.COMPLETED


class TestExtractionRunTemperatureValidation:
    """Tests for temperature field validation (0.0–2.0)."""

    def test_temperature_valid_minimum(self):
        """ExtractionRun accepts temperature=0.0."""
        run = ExtractionRun(
            id=str(uuid4()),
            source_document_uri=None,
            source_text_hash="hash",
            pipeline_config_ref="default",
            model="gpt-4",
            temperature=0.0,
            tokens_used=0,
            duration_ms=0,
            triples_extracted=0,
            triples_committed=0,
            status=ExtractionRunStatus.PENDING,
        )
        assert run.temperature == 0.0

    def test_temperature_valid_maximum(self):
        """ExtractionRun accepts temperature=2.0."""
        run = ExtractionRun(
            id=str(uuid4()),
            source_document_uri=None,
            source_text_hash="hash",
            pipeline_config_ref="default",
            model="gpt-4",
            temperature=2.0,
            tokens_used=0,
            duration_ms=0,
            triples_extracted=0,
            triples_committed=0,
            status=ExtractionRunStatus.PENDING,
        )
        assert run.temperature == 2.0

    def test_temperature_valid_typical(self):
        """ExtractionRun accepts typical temperature values."""
        for temp in [0.1, 0.5, 0.7, 1.0, 1.5, 1.9]:
            run = ExtractionRun(
                id=str(uuid4()),
                source_document_uri=None,
                source_text_hash="hash",
                pipeline_config_ref="default",
                model="gpt-4",
                temperature=temp,
                tokens_used=0,
                duration_ms=0,
                triples_extracted=0,
                triples_committed=0,
                status=ExtractionRunStatus.PENDING,
            )
            assert run.temperature == temp

    def test_temperature_invalid_negative(self):
        """ExtractionRun rejects negative temperature."""
        with pytest.raises(ValueError, match="temperature must be between 0.0 and 2.0"):
            ExtractionRun(
                id=str(uuid4()),
                source_document_uri=None,
                source_text_hash="hash",
                pipeline_config_ref="default",
                model="gpt-4",
                temperature=-0.1,
                tokens_used=0,
                duration_ms=0,
                triples_extracted=0,
                triples_committed=0,
                status=ExtractionRunStatus.PENDING,
            )

    def test_temperature_invalid_too_high(self):
        """ExtractionRun rejects temperature > 2.0."""
        with pytest.raises(ValueError, match="temperature must be between 0.0 and 2.0"):
            ExtractionRun(
                id=str(uuid4()),
                source_document_uri=None,
                source_text_hash="hash",
                pipeline_config_ref="default",
                model="gpt-4",
                temperature=2.1,
                tokens_used=0,
                duration_ms=0,
                triples_extracted=0,
                triples_committed=0,
                status=ExtractionRunStatus.PENDING,
            )

    def test_temperature_invalid_far_too_high(self):
        """ExtractionRun rejects very high temperature."""
        with pytest.raises(ValueError, match="temperature must be between 0.0 and 2.0"):
            ExtractionRun(
                id=str(uuid4()),
                source_document_uri=None,
                source_text_hash="hash",
                pipeline_config_ref="default",
                model="gpt-4",
                temperature=10.0,
                tokens_used=0,
                duration_ms=0,
                triples_extracted=0,
                triples_committed=0,
                status=ExtractionRunStatus.PENDING,
            )


class TestExtractionRunMetricsValidation:
    """Tests for metrics field validation (non-negative)."""

    def test_tokens_used_valid_zero(self):
        """ExtractionRun accepts tokens_used=0."""
        run = ExtractionRun(
            id=str(uuid4()),
            source_document_uri=None,
            source_text_hash="hash",
            pipeline_config_ref="default",
            model="gpt-4",
            temperature=0.5,
            tokens_used=0,
            duration_ms=0,
            triples_extracted=0,
            triples_committed=0,
            status=ExtractionRunStatus.PENDING,
        )
        assert run.tokens_used == 0

    def test_tokens_used_valid_positive(self):
        """ExtractionRun accepts positive tokens_used."""
        run = ExtractionRun(
            id=str(uuid4()),
            source_document_uri=None,
            source_text_hash="hash",
            pipeline_config_ref="default",
            model="gpt-4",
            temperature=0.5,
            tokens_used=5000,
            duration_ms=0,
            triples_extracted=0,
            triples_committed=0,
            status=ExtractionRunStatus.PENDING,
        )
        assert run.tokens_used == 5000

    def test_tokens_used_invalid_negative(self):
        """ExtractionRun rejects negative tokens_used."""
        with pytest.raises(ValueError, match="tokens_used must be non-negative"):
            ExtractionRun(
                id=str(uuid4()),
                source_document_uri=None,
                source_text_hash="hash",
                pipeline_config_ref="default",
                model="gpt-4",
                temperature=0.5,
                tokens_used=-1,
                duration_ms=0,
                triples_extracted=0,
                triples_committed=0,
                status=ExtractionRunStatus.PENDING,
            )

    def test_duration_ms_valid_zero(self):
        """ExtractionRun accepts duration_ms=0."""
        run = ExtractionRun(
            id=str(uuid4()),
            source_document_uri=None,
            source_text_hash="hash",
            pipeline_config_ref="default",
            model="gpt-4",
            temperature=0.5,
            tokens_used=0,
            duration_ms=0,
            triples_extracted=0,
            triples_committed=0,
            status=ExtractionRunStatus.PENDING,
        )
        assert run.duration_ms == 0

    def test_duration_ms_invalid_negative(self):
        """ExtractionRun rejects negative duration_ms."""
        with pytest.raises(ValueError, match="duration_ms must be non-negative"):
            ExtractionRun(
                id=str(uuid4()),
                source_document_uri=None,
                source_text_hash="hash",
                pipeline_config_ref="default",
                model="gpt-4",
                temperature=0.5,
                tokens_used=0,
                duration_ms=-100,
                triples_extracted=0,
                triples_committed=0,
                status=ExtractionRunStatus.PENDING,
            )

    def test_triples_extracted_valid_zero(self):
        """ExtractionRun accepts triples_extracted=0."""
        run = ExtractionRun(
            id=str(uuid4()),
            source_document_uri=None,
            source_text_hash="hash",
            pipeline_config_ref="default",
            model="gpt-4",
            temperature=0.5,
            tokens_used=0,
            duration_ms=0,
            triples_extracted=0,
            triples_committed=0,
            status=ExtractionRunStatus.PENDING,
        )
        assert run.triples_extracted == 0

    def test_triples_extracted_invalid_negative(self):
        """ExtractionRun rejects negative triples_extracted."""
        with pytest.raises(ValueError, match="triples_extracted must be non-negative"):
            ExtractionRun(
                id=str(uuid4()),
                source_document_uri=None,
                source_text_hash="hash",
                pipeline_config_ref="default",
                model="gpt-4",
                temperature=0.5,
                tokens_used=0,
                duration_ms=0,
                triples_extracted=-5,
                triples_committed=0,
                status=ExtractionRunStatus.PENDING,
            )

    def test_triples_committed_valid_zero(self):
        """ExtractionRun accepts triples_committed=0."""
        run = ExtractionRun(
            id=str(uuid4()),
            source_document_uri=None,
            source_text_hash="hash",
            pipeline_config_ref="default",
            model="gpt-4",
            temperature=0.5,
            tokens_used=0,
            duration_ms=0,
            triples_extracted=10,
            triples_committed=0,
            status=ExtractionRunStatus.PENDING,
        )
        assert run.triples_committed == 0

    def test_triples_committed_invalid_negative(self):
        """ExtractionRun rejects negative triples_committed."""
        with pytest.raises(ValueError, match="triples_committed must be non-negative"):
            ExtractionRun(
                id=str(uuid4()),
                source_document_uri=None,
                source_text_hash="hash",
                pipeline_config_ref="default",
                model="gpt-4",
                temperature=0.5,
                tokens_used=0,
                duration_ms=0,
                triples_extracted=10,
                triples_committed=-1,
                status=ExtractionRunStatus.PENDING,
            )


class TestExtractionRunTriplesInvariant:
    """Tests for committed <= extracted invariant."""

    def test_triples_committed_equal_extracted(self):
        """ExtractionRun accepts triples_committed=triples_extracted."""
        run = ExtractionRun(
            id=str(uuid4()),
            source_document_uri=None,
            source_text_hash="hash",
            pipeline_config_ref="default",
            model="gpt-4",
            temperature=0.5,
            tokens_used=0,
            duration_ms=0,
            triples_extracted=25,
            triples_committed=25,
            status=ExtractionRunStatus.COMPLETED,
        )
        assert run.triples_committed == 25
        assert run.triples_extracted == 25

    def test_triples_committed_less_than_extracted(self):
        """ExtractionRun accepts triples_committed < triples_extracted."""
        run = ExtractionRun(
            id=str(uuid4()),
            source_document_uri=None,
            source_text_hash="hash",
            pipeline_config_ref="default",
            model="gpt-4",
            temperature=0.5,
            tokens_used=0,
            duration_ms=0,
            triples_extracted=25,
            triples_committed=20,
            status=ExtractionRunStatus.COMPLETED,
        )
        assert run.triples_committed == 20
        assert run.triples_extracted == 25

    def test_triples_committed_exceeds_extracted(self):
        """ExtractionRun rejects triples_committed > triples_extracted."""
        with pytest.raises(
            ValueError,
            match="triples_committed.*cannot exceed.*triples_extracted",
        ):
            ExtractionRun(
                id=str(uuid4()),
                source_document_uri=None,
                source_text_hash="hash",
                pipeline_config_ref="default",
                model="gpt-4",
                temperature=0.5,
                tokens_used=0,
                duration_ms=0,
                triples_extracted=20,
                triples_committed=25,
                status=ExtractionRunStatus.COMPLETED,
            )

    def test_triples_committed_far_exceeds_extracted(self):
        """ExtractionRun rejects large committed > extracted."""
        with pytest.raises(
            ValueError,
            match="triples_committed.*cannot exceed.*triples_extracted",
        ):
            ExtractionRun(
                id=str(uuid4()),
                source_document_uri=None,
                source_text_hash="hash",
                pipeline_config_ref="default",
                model="gpt-4",
                temperature=0.5,
                tokens_used=0,
                duration_ms=0,
                triples_extracted=10,
                triples_committed=100,
                status=ExtractionRunStatus.COMPLETED,
            )


class TestExtractionRunCreateFactory:
    """Tests for ExtractionRun.create() factory method."""

    def test_create_basic(self):
        """ExtractionRun.create() creates a run with PENDING status and zeroed metrics."""
        run_id = str(uuid4())
        run = ExtractionRun.create(
            id=run_id,
            source_document_uri="https://example.com/doc.txt",
            source_text_hash="abc123",
            pipeline_config_ref="extraction-default",
            model="claude-opus-4-7",
            temperature=0.7,
        )

        assert run.id == run_id
        assert run.source_document_uri == "https://example.com/doc.txt"
        assert run.source_text_hash == "abc123"
        assert run.pipeline_config_ref == "extraction-default"
        assert run.model == "claude-opus-4-7"
        assert run.temperature == 0.7
        assert run.status == ExtractionRunStatus.PENDING
        assert run.tokens_used == 0
        assert run.duration_ms == 0
        assert run.triples_extracted == 0
        assert run.triples_committed == 0

    def test_create_with_none_document_uri(self):
        """ExtractionRun.create() accepts None source_document_uri."""
        run = ExtractionRun.create(
            id=str(uuid4()),
            source_document_uri=None,
            source_text_hash="hash",
            pipeline_config_ref="default",
            model="gpt-4",
            temperature=0.5,
        )

        assert run.source_document_uri is None
        assert run.status == ExtractionRunStatus.PENDING

    def test_create_temperature_validation(self):
        """ExtractionRun.create() validates temperature bounds."""
        with pytest.raises(ValueError, match="temperature must be between 0.0 and 2.0"):
            ExtractionRun.create(
                id=str(uuid4()),
                source_document_uri=None,
                source_text_hash="hash",
                pipeline_config_ref="default",
                model="gpt-4",
                temperature=2.5,
            )

    def test_create_minimum_temperature(self):
        """ExtractionRun.create() accepts minimum temperature."""
        run = ExtractionRun.create(
            id=str(uuid4()),
            source_document_uri=None,
            source_text_hash="hash",
            pipeline_config_ref="default",
            model="gpt-4",
            temperature=0.0,
        )
        assert run.temperature == 0.0

    def test_create_maximum_temperature(self):
        """ExtractionRun.create() accepts maximum temperature."""
        run = ExtractionRun.create(
            id=str(uuid4()),
            source_document_uri=None,
            source_text_hash="hash",
            pipeline_config_ref="default",
            model="gpt-4",
            temperature=2.0,
        )
        assert run.temperature == 2.0

    def test_create_multiple_with_different_ids(self):
        """Multiple ExtractionRun.create() calls generate independent runs."""
        run1 = ExtractionRun.create(
            id=str(uuid4()),
            source_document_uri="doc1.txt",
            source_text_hash="hash1",
            pipeline_config_ref="default",
            model="gpt-4",
            temperature=0.5,
        )

        run2 = ExtractionRun.create(
            id=str(uuid4()),
            source_document_uri="doc2.txt",
            source_text_hash="hash2",
            pipeline_config_ref="default",
            model="claude-opus",
            temperature=0.7,
        )

        assert run1.id != run2.id
        assert run1.source_document_uri != run2.source_document_uri
        assert run1.model != run2.model
        assert run1.temperature != run2.temperature
        assert run1.status == run2.status == ExtractionRunStatus.PENDING


class TestExtractionRunStatus:
    """Tests for ExtractionRunStatus enum."""

    def test_status_pending(self):
        """ExtractionRun can have PENDING status."""
        run = ExtractionRun.create(
            id=str(uuid4()),
            source_document_uri=None,
            source_text_hash="hash",
            pipeline_config_ref="default",
            model="gpt-4",
            temperature=0.5,
        )
        assert run.status == ExtractionRunStatus.PENDING
        assert run.status.value == "pending"

    def test_status_completed(self):
        """ExtractionRun can have COMPLETED status."""
        run = ExtractionRun(
            id=str(uuid4()),
            source_document_uri=None,
            source_text_hash="hash",
            pipeline_config_ref="default",
            model="gpt-4",
            temperature=0.5,
            tokens_used=100,
            duration_ms=1000,
            triples_extracted=5,
            triples_committed=5,
            status=ExtractionRunStatus.COMPLETED,
        )
        assert run.status == ExtractionRunStatus.COMPLETED
        assert run.status.value == "completed"

    def test_status_failed(self):
        """ExtractionRun can have FAILED status."""
        run = ExtractionRun(
            id=str(uuid4()),
            source_document_uri=None,
            source_text_hash="hash",
            pipeline_config_ref="default",
            model="gpt-4",
            temperature=0.5,
            tokens_used=0,
            duration_ms=0,
            triples_extracted=0,
            triples_committed=0,
            status=ExtractionRunStatus.FAILED,
        )
        assert run.status == ExtractionRunStatus.FAILED
        assert run.status.value == "failed"
