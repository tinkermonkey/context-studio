"""
Transaction management utilities for ACID compliance.

This module provides:
- atomic_transaction context manager for ACID guarantees
- Optimistic locking for concurrent updates
- Audit logging for all changes
- Cache invalidation hooks
"""

import time
import json
from contextlib import contextmanager
from typing import Generator, Dict, Any, Optional, Callable
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, OperationalError

from database.models import AuditLog
from database.input_validation import sanitize_audit_log_value
from utils.logger import get_logger

logger = get_logger(__name__)


class OptimisticLockException(Exception):
    """Exception raised when optimistic locking detects concurrent modification."""
    pass


class TransactionException(Exception):
    """Exception raised for transaction-related errors."""
    pass


@contextmanager
def atomic_transaction(
    session: Session,
    isolation_level: str = "SERIALIZABLE"
) -> Generator[Session, None, None]:
    """
    Context manager for atomic database transactions with ACID guarantees.

    This context manager ensures:
    - Atomicity: All operations succeed or all fail
    - Consistency: Database constraints are enforced
    - Isolation: Transactions are isolated (configurable level)
    - Durability: Committed changes are persisted

    On success, the transaction is committed.
    On failure, the transaction is automatically rolled back and exception is re-raised.

    Args:
        session: SQLAlchemy session to use for the transaction
        isolation_level: Transaction isolation level
                        ("READ_UNCOMMITTED", "READ_COMMITTED", "REPEATABLE_READ", "SERIALIZABLE")

    Yields:
        The session object for use within the transaction

    Raises:
        TransactionException: If transaction cannot be started or committed
        Any exception raised within the transaction block

    Example:
        >>> with atomic_transaction(session) as tx_session:
        ...     predicate = tx_session.query(Predicate).filter_by(id=pred_id).first()
        ...     predicate.mapping = json.dumps(new_mapping)
        ...     create_audit_log(tx_session, "predicate", pred_id, "update", ...)
        ...     invalidate_predicate_cache(pred_id)

    Performance target: <50ms overhead for transaction management (PT-MAP-004)
    """
    start_time = time.perf_counter()

    try:
        # Set isolation level using SQLAlchemy's execution options
        # Map isolation levels to SQLite PRAGMA settings
        isolation_map = {
            "SERIALIZABLE": "IMMEDIATE",
            "READ_COMMITTED": "DEFERRED",
            "READ_UNCOMMITTED": "DEFERRED",
            "REPEATABLE_READ": "IMMEDIATE"
        }

        # Get the connection and set isolation level
        connection = session.connection()
        if isolation_level in isolation_map:
            # For SQLite, we use transaction locking modes
            # IMMEDIATE = SERIALIZABLE/REPEATABLE_READ
            # DEFERRED = READ_COMMITTED/READ_UNCOMMITTED
            lock_mode = isolation_map[isolation_level]
            connection.execution_options(
                isolation_level=lock_mode
            )

        session.begin()
        logger.debug(f"Transaction started with isolation level: {isolation_level}")

        # Yield control to the transaction block
        yield session

        # Commit if no exceptions occurred
        session.commit()

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.debug(f"Transaction committed successfully in {elapsed_ms:.2f}ms")

    except IntegrityError as e:
        # Handle constraint violations
        session.rollback()
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.error(f"Transaction rolled back due to integrity error in {elapsed_ms:.2f}ms: {e}")
        raise TransactionException(f"Integrity constraint violated: {str(e)}") from e

    except OperationalError as e:
        # Handle database operational errors
        session.rollback()
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.error(f"Transaction rolled back due to operational error in {elapsed_ms:.2f}ms: {e}")
        raise TransactionException(f"Database operation failed: {str(e)}") from e

    except Exception as e:
        # Handle all other exceptions
        session.rollback()
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.error(f"Transaction rolled back due to exception in {elapsed_ms:.2f}ms: {e}")
        raise


def check_optimistic_lock(session: Session, entity: Any, expected_version: int) -> None:
    """
    Check optimistic lock version to detect concurrent modifications.

    This function implements optimistic locking by comparing the expected version
    with the current version in the database. If they don't match, a concurrent
    modification has occurred.

    Args:
        session: SQLAlchemy session
        entity: Entity to check (must have 'version' attribute)
        expected_version: Expected version number

    Raises:
        OptimisticLockException: If version mismatch detected

    Example:
        >>> predicate = session.query(Predicate).filter_by(id=pred_id).with_for_update().first()
        >>> check_optimistic_lock(session, predicate, expected_version)
        >>> predicate.mapping = new_mapping
        >>> predicate.version += 1
    """
    if not hasattr(entity, 'version'):
        logger.warning(f"Entity {type(entity).__name__} does not have version field for optimistic locking")
        return

    current_version = entity.version
    if current_version != expected_version:
        raise OptimisticLockException(
            f"Optimistic lock failed: expected version {expected_version}, "
            f"but current version is {current_version}. "
            f"Entity was modified by another transaction."
        )


def create_audit_log(
    session: Session,
    entity_type: str,
    entity_id: str,
    action: str,
    old_value: Optional[Dict[str, Any]] = None,
    new_value: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
    execution_time_ms: Optional[int] = None
) -> AuditLog:
    """
    Create an audit log entry for an entity change.

    This function records all changes to critical entities for compliance
    and debugging purposes.

    Args:
        session: SQLAlchemy session (must be within a transaction)
        entity_type: Type of entity (e.g., "predicate", "structure_node")
        entity_id: ID of the affected entity
        action: Action performed ("create", "update", "delete")
        old_value: Previous state of the entity (for updates/deletes)
        new_value: New state of the entity (for creates/updates)
        user_id: Optional user ID who performed the action
        execution_time_ms: Optional execution time for the operation

    Returns:
        AuditLog: The created audit log entry

    Example:
        >>> with atomic_transaction(session) as tx_session:
        ...     old_mapping = json.loads(predicate.mapping)
        ...     predicate.mapping = json.dumps(new_mapping)
        ...     create_audit_log(
        ...         tx_session, "predicate", predicate.id, "update",
        ...         old_value={"mapping": old_mapping},
        ...         new_value={"mapping": new_mapping}
        ...     )

    Performance target: <20ms per audit log entry (PT-MAP-005)
    """
    start_time = time.perf_counter()

    # Sanitize and serialize values to JSON
    sanitized_old_value = sanitize_audit_log_value(old_value) if old_value else None
    sanitized_new_value = sanitize_audit_log_value(new_value) if new_value else None

    old_value_json = json.dumps(sanitized_old_value) if sanitized_old_value else None
    new_value_json = json.dumps(sanitized_new_value) if sanitized_new_value else None

    audit_log = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        user_id=user_id,
        old_value=old_value_json,
        new_value=new_value_json,
        timestamp=datetime.utcnow(),
        execution_time_ms=execution_time_ms
    )

    session.add(audit_log)

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.debug(
        f"Audit log created in {elapsed_ms:.2f}ms: "
        f"{entity_type}:{entity_id} action={action}"
    )

    return audit_log


def get_audit_history(
    session: Session,
    entity_type: str,
    entity_id: str,
    limit: int = 100
) -> list:
    """
    Get audit history for a specific entity.

    Args:
        session: SQLAlchemy session
        entity_type: Type of entity (e.g., "predicate")
        entity_id: ID of the entity
        limit: Maximum number of entries to return (default: 100)

    Returns:
        List of AuditLog entries ordered by timestamp descending

    Example:
        >>> history = get_audit_history(session, "predicate", pred_id)
        >>> for entry in history:
        ...     print(f"{entry.timestamp}: {entry.action} by {entry.user_id}")
    """
    return (
        session.query(AuditLog)
        .filter(
            AuditLog.entity_type == entity_type,
            AuditLog.entity_id == entity_id
        )
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
        .all()
    )


# Cache invalidation callback registry
_cache_invalidation_callbacks: Dict[str, list[Callable]] = {}


def register_cache_invalidation_callback(entity_type: str, callback: Callable[[str], None]) -> None:
    """
    Register a callback to be invoked when an entity is modified.

    This allows services to invalidate their caches when entities change.

    Args:
        entity_type: Type of entity to watch (e.g., "predicate")
        callback: Function to call with entity_id when entity is modified

    Example:
        >>> def invalidate_predicate_cache(predicate_id: str):
        ...     similarity_service.invalidate_cache()
        >>> register_cache_invalidation_callback("predicate", invalidate_predicate_cache)
    """
    if entity_type not in _cache_invalidation_callbacks:
        _cache_invalidation_callbacks[entity_type] = []
    _cache_invalidation_callbacks[entity_type].append(callback)
    logger.debug(f"Registered cache invalidation callback for entity type: {entity_type}")


def invalidate_entity_cache(entity_type: str, entity_id: str) -> None:
    """
    Invoke all registered cache invalidation callbacks for an entity.

    Args:
        entity_type: Type of entity (e.g., "predicate")
        entity_id: ID of the modified entity

    Example:
        >>> with atomic_transaction(session) as tx_session:
        ...     predicate.mapping = new_mapping
        ...     tx_session.commit()
        ...     invalidate_entity_cache("predicate", predicate.id)
    """
    callbacks = _cache_invalidation_callbacks.get(entity_type, [])
    for callback in callbacks:
        try:
            callback(entity_id)
            logger.debug(f"Cache invalidated for {entity_type}:{entity_id}")
        except Exception as e:
            logger.error(f"Cache invalidation callback failed for {entity_type}:{entity_id}: {e}")
