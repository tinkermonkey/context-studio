"""
Integration tests for mapping CRUD operations with transaction management.

This module tests:
- ACID transaction guarantees
- Concurrent update handling with optimistic locking
- Rollback scenarios with partial failures
- Performance benchmarks for all acceptance criteria
- Input validation and sanitization
- Audit trail creation and retrieval
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import time
import json
import uuid
import pytest
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from database.models import Base, Predicate, AuditLog
from database.transaction_utils import (
    atomic_transaction,
    check_optimistic_lock,
    create_audit_log,
    get_audit_history,
    OptimisticLockException,
    TransactionException
)
from database.mapping_validation import validate_mapping, create_empty_mapping, add_reference_predicate
from database.input_validation import sanitize_user_input, ValidationError


# Test database setup
TEST_DB_URL = "sqlite:///:memory:"


def build_mapping(predicates: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Helper to build mapping from list of predicates."""
    mapping = create_empty_mapping()
    for pred in predicates:
        mapping = add_reference_predicate(
            mapping,
            source=pred["source"],
            source_id=pred["source_id"],
            title=pred["title"],
            confidence=pred["confidence"]
        )
    return mapping


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    engine = create_engine(TEST_DB_URL, echo=False)
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    yield session

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def sample_predicate(db_session: Session) -> Predicate:
    """Create a sample predicate for testing."""
    predicate = Predicate(
        id=str(uuid.uuid4()),
        identifier="test_predicate",
        title="Test Predicate",
        definition="A test predicate for integration tests",
        mapping=None,
        is_relevant=None,
        version=1
    )
    db_session.add(predicate)
    db_session.commit()
    db_session.refresh(predicate)
    return predicate


class TestACIDGuarantees:
    """Test ACID transaction guarantees."""

    def test_atomicity_successful_commit(self, db_session: Session, sample_predicate: Predicate):
        """Test that successful transactions are committed atomically."""
        # Create a mapping
        mapping = build_mapping([{
            "source": "conceptnet",
            "source_id": "r/RelatedTo",
            "title": "RelatedTo",
            "confidence": 0.85
        }])

        # Update predicate with atomic transaction
        with atomic_transaction(db_session) as tx_session:
            pred = tx_session.query(Predicate).filter_by(id=sample_predicate.id).first()
            pred.mapping = json.dumps(mapping)
            pred.version += 1

            create_audit_log(
                tx_session,
                "predicate",
                pred.id,
                "update",
                {"mapping": None},
                {"mapping": mapping},
                user_id="test_user"
            )

        # Verify both mapping and audit log were committed
        db_session.expire_all()
        updated_pred = db_session.query(Predicate).filter_by(id=sample_predicate.id).first()
        assert updated_pred.mapping is not None
        assert updated_pred.version == 2

        audit_logs = db_session.query(AuditLog).filter_by(entity_id=sample_predicate.id).all()
        assert len(audit_logs) == 1
        assert audit_logs[0].action == "update"
        assert audit_logs[0].user_id == "test_user"

    def test_atomicity_rollback_on_error(self, db_session: Session, sample_predicate: Predicate):
        """Test that failed transactions are rolled back completely."""
        original_mapping = sample_predicate.mapping
        original_version = sample_predicate.version

        # Try to update with an error in the transaction
        with pytest.raises(ValueError):
            with atomic_transaction(db_session) as tx_session:
                pred = tx_session.query(Predicate).filter_by(id=sample_predicate.id).first()
                pred.mapping = json.dumps({"test": "data"})
                pred.version += 1

                # Simulate an error
                raise ValueError("Simulated error")

        # Verify rollback - predicate should be unchanged
        db_session.expire_all()
        pred = db_session.query(Predicate).filter_by(id=sample_predicate.id).first()
        assert pred.mapping == original_mapping
        assert pred.version == original_version

        # Verify no audit log was created
        audit_logs = db_session.query(AuditLog).filter_by(entity_id=sample_predicate.id).all()
        assert len(audit_logs) == 0

    def test_isolation_concurrent_reads(self, db_session: Session, sample_predicate: Predicate):
        """Test that concurrent reads see consistent data."""
        results = []

        def read_predicate():
            """Read predicate in a separate transaction."""
            pred = db_session.query(Predicate).filter_by(id=sample_predicate.id).first()
            results.append(pred.version)

        # Start multiple concurrent reads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=read_predicate)
            threads.append(thread)
            thread.start()

        # Wait for all reads to complete
        for thread in threads:
            thread.join()

        # All reads should see the same version
        assert all(v == sample_predicate.version for v in results)


class TestOptimisticLocking:
    """Test optimistic locking for concurrent updates."""

    def test_optimistic_lock_success(self, db_session: Session, sample_predicate: Predicate):
        """Test successful update with correct version."""
        expected_version = sample_predicate.version

        with atomic_transaction(db_session) as tx_session:
            pred = tx_session.query(Predicate).filter_by(id=sample_predicate.id).with_for_update().first()
            check_optimistic_lock(tx_session, pred, expected_version)
            pred.title = "Updated Title"
            pred.version += 1

        # Verify update succeeded
        db_session.expire_all()
        updated_pred = db_session.query(Predicate).filter_by(id=sample_predicate.id).first()
        assert updated_pred.title == "Updated Title"
        assert updated_pred.version == expected_version + 1

    def test_optimistic_lock_failure(self, db_session: Session, sample_predicate: Predicate):
        """Test update failure with stale version."""
        # Simulate stale version
        stale_version = sample_predicate.version - 1

        with pytest.raises(OptimisticLockException):
            with atomic_transaction(db_session) as tx_session:
                pred = tx_session.query(Predicate).filter_by(id=sample_predicate.id).with_for_update().first()
                check_optimistic_lock(tx_session, pred, stale_version)

    def test_concurrent_updates_with_optimistic_locking(self, db_session: Session, sample_predicate: Predicate):
        """Test that optimistic locking prevents lost updates (PT-MAP-003)."""
        success_count = 0
        conflict_count = 0

        def update_predicate(user_id: str) -> Tuple[bool, float]:
            """Attempt to update predicate with optimistic locking."""
            start_time = time.perf_counter()

            try:
                # Create new session for this thread
                from sqlalchemy import create_engine
                from sqlalchemy.orm import sessionmaker
                engine = create_engine(TEST_DB_URL, echo=False)
                SessionLocal = sessionmaker(bind=engine)
                thread_session = SessionLocal()

                with atomic_transaction(thread_session) as tx_session:
                    pred = tx_session.query(Predicate).filter_by(id=sample_predicate.id).with_for_update().first()
                    current_version = pred.version

                    # Small delay to increase contention
                    time.sleep(0.01)

                    check_optimistic_lock(tx_session, pred, current_version)
                    pred.definition = f"Updated by {user_id}"
                    pred.version += 1

                    create_audit_log(
                        tx_session,
                        "predicate",
                        pred.id,
                        "update",
                        None,
                        {"user": user_id},
                        user_id=user_id
                    )

                thread_session.close()
                elapsed = (time.perf_counter() - start_time) * 1000
                return True, elapsed

            except OptimisticLockException:
                if 'thread_session' in locals():
                    thread_session.close()
                elapsed = (time.perf_counter() - start_time) * 1000
                return False, elapsed

        # Simulate 5 concurrent users (PT-MAP-003)
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(update_predicate, f"user_{i}") for i in range(5)]

            times = []
            for future in as_completed(futures):
                success, elapsed_ms = future.result()
                times.append(elapsed_ms)
                if success:
                    success_count += 1
                else:
                    conflict_count += 1

        # At least one update should succeed
        assert success_count >= 1

        # Calculate p95 time (PT-MAP-003: should be <200ms)
        times_sorted = sorted(times)
        p95_index = int(len(times_sorted) * 0.95)
        p95_time = times_sorted[p95_index]

        print(f"Concurrent updates: {success_count} succeeded, {conflict_count} conflicts")
        print(f"P95 time: {p95_time:.2f}ms")

        # Verify p95 time is under target
        assert p95_time < 200, f"P95 time {p95_time:.2f}ms exceeds 200ms target"


class TestMappingValidation:
    """Test mapping validation with jsonschema."""

    def test_valid_mapping_accepted(self, db_session: Session, sample_predicate: Predicate):
        """Test that valid mappings are accepted."""
        mapping = build_mapping([{
            "source": "conceptnet",
            "source_id": "r/RelatedTo",
            "title": "RelatedTo",
            "confidence": 0.85
        }])

        is_valid, error = validate_mapping(mapping)
        assert is_valid
        assert error is None

    def test_invalid_confidence_rejected(self, db_session: Session, sample_predicate: Predicate):
        """Test that out-of-range confidence scores are rejected."""
        mapping = build_mapping([{
            "source": "conceptnet",
            "source_id": "r/RelatedTo",
            "title": "RelatedTo",
            "confidence": 1.5  # Invalid: > 1.0
        }])

        is_valid, error = validate_mapping(mapping)
        assert not is_valid
        assert "confidence" in error.lower()

    def test_missing_required_fields_rejected(self, db_session: Session, sample_predicate: Predicate):
        """Test that mappings with missing required fields are rejected."""
        invalid_mapping = {
            "reference_predicates": [{
                "source": "conceptnet",
                # Missing source_id, title, confidence
            }]
        }

        is_valid, error = validate_mapping(invalid_mapping)
        assert not is_valid


class TestAuditLogging:
    """Test audit logging functionality."""

    def test_audit_log_creation_performance(self, db_session: Session, sample_predicate: Predicate):
        """Test audit log creation performance (PT-MAP-005: <20ms)."""
        start_time = time.perf_counter()

        with atomic_transaction(db_session) as tx_session:
            create_audit_log(
                tx_session,
                "predicate",
                sample_predicate.id,
                "update",
                {"old": "value"},
                {"new": "value"},
                user_id="test_user"
            )

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        print(f"Audit log creation time: {elapsed_ms:.2f}ms")
        assert elapsed_ms < 20, f"Audit log creation {elapsed_ms:.2f}ms exceeds 20ms target"

    def test_audit_history_retrieval(self, db_session: Session, sample_predicate: Predicate):
        """Test retrieving audit history for a predicate."""
        # Create multiple audit log entries
        with atomic_transaction(db_session) as tx_session:
            for i in range(5):
                create_audit_log(
                    tx_session,
                    "predicate",
                    sample_predicate.id,
                    "update",
                    {"version": i},
                    {"version": i + 1},
                    user_id=f"user_{i}"
                )

        # Retrieve history
        history = get_audit_history(db_session, "predicate", sample_predicate.id, limit=10)

        assert len(history) == 5
        # Should be ordered by timestamp descending
        assert history[0].user_id == "user_4"
        assert history[-1].user_id == "user_0"

    def test_audit_log_with_large_values(self, db_session: Session, sample_predicate: Predicate):
        """Test audit logging with large JSON values."""
        large_mapping = build_mapping([
            {
                "source": f"source_{i}",
                "source_id": f"id_{i}",
                "title": f"Title {i}",
                "confidence": 0.8
            }
            for i in range(100)
        ])

        with atomic_transaction(db_session) as tx_session:
            create_audit_log(
                tx_session,
                "predicate",
                sample_predicate.id,
                "update",
                None,
                {"mapping": large_mapping},
                user_id="test_user"
            )

        # Verify audit log was created
        audit_logs = db_session.query(AuditLog).filter_by(entity_id=sample_predicate.id).all()
        assert len(audit_logs) == 1


class TestInputValidation:
    """Test input validation and sanitization."""

    def test_sanitize_html_in_title(self):
        """Test that HTML in title is escaped."""
        data = {"title": "<script>alert('xss')</script>"}
        sanitized = sanitize_user_input(data, {"title": {"max_length": 500}})

        assert "<script>" not in sanitized["title"]
        assert "&lt;script&gt;" in sanitized["title"]

    def test_reject_oversized_input(self):
        """Test that oversized input is rejected."""
        data = {"title": "x" * 10001}

        with pytest.raises(ValidationError):
            sanitize_user_input(data, {"title": {"max_length": 10000}})

    def test_nested_json_sanitization(self):
        """Test that nested JSON structures are sanitized."""
        data = {
            "mapping": {
                "reference_predicates": [
                    {"title": "<b>Bold</b>", "confidence": 0.9}
                ]
            }
        }

        sanitized = sanitize_user_input(data)

        # Check that HTML was escaped in nested structure
        ref_pred = sanitized["mapping"]["reference_predicates"][0]
        assert "<b>" not in ref_pred["title"]
        assert "&lt;b&gt;" in ref_pred["title"]


class TestPerformanceBenchmarks:
    """Test performance benchmarks for all acceptance criteria."""

    def test_mapping_update_performance(self, db_session: Session, sample_predicate: Predicate):
        """Test mapping update performance (PT-MAP-001: <100ms)."""
        mapping = build_mapping([{
            "source": "conceptnet",
            "source_id": "r/RelatedTo",
            "title": "RelatedTo",
            "confidence": 0.85
        }])

        start_time = time.perf_counter()

        with atomic_transaction(db_session) as tx_session:
            pred = tx_session.query(Predicate).filter_by(id=sample_predicate.id).with_for_update().first()
            check_optimistic_lock(tx_session, pred, pred.version)
            pred.mapping = json.dumps(mapping)
            pred.version += 1

            create_audit_log(
                tx_session,
                "predicate",
                pred.id,
                "update",
                {"mapping": None},
                {"mapping": mapping},
                user_id="test_user"
            )

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        print(f"Mapping update time: {elapsed_ms:.2f}ms")
        assert elapsed_ms < 100, f"Mapping update {elapsed_ms:.2f}ms exceeds 100ms target"

    def test_batch_creation_performance(self, db_session: Session):
        """Test batch mapping creation performance (PT-MAP-002: <500ms for 10 mappings)."""
        start_time = time.perf_counter()

        with atomic_transaction(db_session) as tx_session:
            for i in range(10):
                predicate = Predicate(
                    id=str(uuid.uuid4()),
                    identifier=f"batch_pred_{i}",
                    title=f"Batch Predicate {i}",
                    mapping=json.dumps(build_mapping([{
                        "source": "conceptnet",
                        "source_id": f"r/Rel{i}",
                        "title": f"Relation {i}",
                        "confidence": 0.8
                    }])),
                    version=1
                )
                tx_session.add(predicate)

                create_audit_log(
                    tx_session,
                    "predicate",
                    predicate.id,
                    "create",
                    None,
                    {"title": predicate.title},
                    user_id="test_user"
                )

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        print(f"Batch creation time (10 mappings): {elapsed_ms:.2f}ms")
        assert elapsed_ms < 500, f"Batch creation {elapsed_ms:.2f}ms exceeds 500ms target"

    def test_rollback_performance(self, db_session: Session, sample_predicate: Predicate):
        """Test transaction rollback performance (PT-MAP-004: <50ms)."""
        start_time = time.perf_counter()

        try:
            with atomic_transaction(db_session) as tx_session:
                pred = tx_session.query(Predicate).filter_by(id=sample_predicate.id).first()
                pred.mapping = json.dumps({"test": "data"})
                raise ValueError("Forced rollback")
        except ValueError:
            pass

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        print(f"Rollback time: {elapsed_ms:.2f}ms")
        assert elapsed_ms < 50, f"Rollback {elapsed_ms:.2f}ms exceeds 50ms target"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
