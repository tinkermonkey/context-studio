"""
Authentication dependencies for API endpoints.

This module provides authentication and authorization utilities for securing
API endpoints with user context tracking for audit trails.
"""

from typing import Optional
from fastapi import Header, HTTPException, status
from pydantic import BaseModel

from utils.logger import get_logger

logger = get_logger(__name__)


class UserContext(BaseModel):
    """User context information for authenticated requests."""
    user_id: str
    username: Optional[str] = None
    roles: list[str] = []


def get_current_user(
    x_user_id: Optional[str] = Header(None, description="User ID for authentication"),
    x_auth_token: Optional[str] = Header(None, description="Authentication token")
) -> UserContext:
    """
    Authentication dependency for API endpoints.

    This function validates user authentication and returns user context for audit logging.
    In production, this should integrate with a proper authentication system (OAuth, JWT, etc.).

    For now, this implements a simple header-based authentication for audit tracking:
    - X-User-ID: User identifier
    - X-Auth-Token: Authentication token (optional, for future use)

    Args:
        x_user_id: User ID from request header
        x_auth_token: Authentication token from request header

    Returns:
        UserContext: User context with authenticated user information

    Raises:
        HTTPException: 401 if authentication fails

    Example:
        >>> @router.put("/predicates/{id}")
        >>> def update_predicate(
        ...     id: str,
        ...     predicate: PredicateUpdate,
        ...     current_user: UserContext = Depends(get_current_user),
        ...     db: Session = Depends(get_db)
        ... ):
        ...     # current_user.user_id is now available for audit logging
        ...     create_audit_log(db, ..., user_id=current_user.user_id)

    Note:
        This is a simple implementation for audit trail functionality.
        In production, replace with proper authentication (OAuth2, JWT, etc.).
    """
    # For now, accept any user_id provided in the header
    # In production, this would validate tokens and retrieve user info from auth service
    if not x_user_id:
        # Allow unauthenticated requests but log them as "system" for backward compatibility
        logger.warning("Request made without X-User-ID header, using 'system' user")
        return UserContext(user_id="system", roles=["system"])

    # Validate user_id format (basic validation)
    if not x_user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.debug(f"Authenticated request from user: {x_user_id}")

    return UserContext(
        user_id=x_user_id,
        username=x_user_id,  # In production, fetch username from user service
        roles=["user"]  # In production, fetch roles from user service
    )


def get_optional_user(
    x_user_id: Optional[str] = Header(None, description="User ID for authentication")
) -> Optional[UserContext]:
    """
    Optional authentication dependency that doesn't require authentication.

    Use this for endpoints that support both authenticated and unauthenticated access.

    Args:
        x_user_id: User ID from request header (optional)

    Returns:
        UserContext if authenticated, None otherwise

    Example:
        >>> @router.get("/predicates/{id}")
        >>> def get_predicate(
        ...     id: str,
        ...     current_user: Optional[UserContext] = Depends(get_optional_user),
        ...     db: Session = Depends(get_db)
        ... ):
        ...     # current_user may be None for anonymous access
        ...     user_id = current_user.user_id if current_user else None
    """
    if not x_user_id or not x_user_id.strip():
        return None

    return UserContext(
        user_id=x_user_id,
        username=x_user_id,
        roles=["user"]
    )


def require_role(required_role: str):
    """
    Authorization dependency factory for role-based access control.

    This creates a dependency that checks if the authenticated user has
    the required role.

    Args:
        required_role: Role required to access the endpoint

    Returns:
        Dependency function that checks user roles

    Example:
        >>> @router.delete("/predicates/{id}")
        >>> def delete_predicate(
        ...     id: str,
        ...     current_user: UserContext = Depends(require_role("admin")),
        ...     db: Session = Depends(get_db)
        ... ):
        ...     # Only users with "admin" role can access this endpoint
        ...     pass

    Note:
        This is a placeholder for future role-based authorization.
        Currently, it just ensures user is authenticated.
    """
    def check_role(current_user: UserContext = Depends(get_current_user)) -> UserContext:
        """Check if user has required role."""
        if required_role not in current_user.roles and "system" not in current_user.roles:
            logger.warning(
                f"User {current_user.user_id} attempted to access resource requiring "
                f"role '{required_role}' but has roles: {current_user.roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role}"
            )
        return current_user

    return check_role
