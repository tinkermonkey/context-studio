# mypy: ignore-errors
"""
FastAPI dependencies for reference database access.

This module provides dependency injection functions for accessing the reference
database in FastAPI endpoints, using a singleton ReferenceManager pattern for
optimal performance.
"""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from reference_db.config import ReferenceConfig
from reference_db.manager import ReferenceManager, get_reference_manager


def get_reference_db_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency to get a reference database session.

    This provides a database session from the singleton ReferenceManager,
    ensuring proper cleanup after the request completes.

    Yields:
        SQLAlchemy Session for reference database operations

    Example:
        ```python
        @router.get("/api/predicates/external")
        async def list_external_predicates(
            session: Session = Depends(get_reference_db_session)
        ):
            predicates = session.query(ExternalPredicate).limit(10).all()
            return {"data": predicates}
        ```
    """
    manager = get_reference_manager()
    session = manager.SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def reference_manager_context(
    config: ReferenceConfig = None,
) -> Generator[ReferenceManager, None, None]:
    """
    Context manager for accessing the singleton ReferenceManager.

    This is a convenience wrapper around get_reference_manager() that provides
    a context manager interface while still using the singleton instance.

    Note: Unlike creating a new ReferenceManager with `with ReferenceManager(config) as manager:`,
    this does NOT dispose of the engine on exit since it's shared across requests.

    Args:
        config: Optional configuration (only used if no manager exists yet)

    Yields:
        Singleton ReferenceManager instance

    Example:
        ```python
        with reference_manager_context() as manager:
            results = manager.search_external_predicates_by_similarity(
                query_text="example",
                limit=10
            )
        ```
    """
    manager = get_reference_manager(config)
    try:
        yield manager
    except Exception:
        # Re-raise any exceptions that occur during usage
        raise
    # Note: We don't close() the manager here since it's a singleton
