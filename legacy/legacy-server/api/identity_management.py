"""
Identity Management API Endpoints

This module implements the identity management API endpoints for user registration,  # noqa: E501
email verification, and peer trust systems in collaborative workflows.

Endpoints:
- POST /api/identity/register - Register new user
- POST /api/identity/verify - Verify email with code
- POST /api/identity/trust - Establish trust relationship
- GET /api/identity/users/{user_id} - Get user by ID
- GET /api/identity/users/email/{email} - Get user by email
- GET /api/identity/users - List users with filtering
- GET /api/identity/users/{user_id}/trust-network - Get trust network
"""

from datetime import datetime

from database.utils import get_db
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, EmailStr
from services.identity_manager import IdentityManager
from services.service_factory import ServiceFactory
from sqlalchemy.orm import Session
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/identity", tags=["identity_management"])


# Request/Response Models
class RegisterUserRequest(BaseModel):
    """Request model for user registration."""

    email: EmailStr
    display_name: str


class VerifyEmailRequest(BaseModel):
    """Request model for email verification."""

    user_id: str
    verification_code: str


class TrustUserRequest(BaseModel):
    """Request model for establishing trust relationship."""

    trustee_user_id: str
    trusted_user_id: str


class UserIdentityResponse(BaseModel):
    """Response model for user identity data."""

    user_id: str
    email: str
    display_name: str
    public_key: str | None
    verified: bool
    trust_level: int
    created_at: datetime
    verified_at: datetime | None


class RegisterUserResponse(BaseModel):
    """Response model for user registration."""

    user_identity: UserIdentityResponse
    verification_code: str
    message: str


class UserListResponse(BaseModel):
    """Response model for user list."""

    users: list[UserIdentityResponse]
    total_count: int


class TrustNetworkResponse(BaseModel):
    """Response model for trust network."""

    user_id: str
    trustees: list[dict]  # Users who trust this user
    trusted: list[dict]  # Users this user trusts
    trust_count: int


# Dependency injection
def get_identity_manager(
    db: Session = Depends(get_db), service_factory: ServiceFactory = Depends()
) -> IdentityManager:
    """Get IdentityManager instance via service factory."""
    return service_factory.create_identity_manager(db)


# API Endpoints
@router.post("/register", response_model=RegisterUserResponse)
def register_user(
    request: RegisterUserRequest,
    identity_manager: IdentityManager = Depends(get_identity_manager),
):
    """
    Register a new user with email-based identity.

    Args:
        request: User registration request
        identity_manager: IdentityManager dependency

    Returns:
        User identity and verification code

    Raises:
        HTTPException: If validation fails or registration fails
    """
    logger.info(f"Registering user with email {request.email}")

    try:
        result = identity_manager.register_user(
            email=request.email, display_name=request.display_name
        )

        user_identity = result["user_identity"]

        return RegisterUserResponse(
            user_identity=UserIdentityResponse(
                user_id=user_identity.user_id,
                email=user_identity.email,
                display_name=user_identity.display_name,
                public_key=user_identity.public_key,
                verified=user_identity.verified,
                trust_level=user_identity.trust_level,
                created_at=user_identity.created_at,
                verified_at=user_identity.verified_at,
            ),
            verification_code=result["verification_code"],
            message=result["message"],
        )

    except ValueError as e:
        logger.warning(f"Invalid user registration request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error(f"Failed to register user: {e}")
        raise HTTPException(status_code=500, detail="Failed to register user")


@router.post("/verify")
def verify_email(
    request: VerifyEmailRequest,
    identity_manager: IdentityManager = Depends(get_identity_manager),
):
    """
    Verify user email with verification code.

    Args:
        request: Email verification request
        identity_manager: IdentityManager dependency

    Returns:
        Success message

    Raises:
        HTTPException: If verification fails
    """
    logger.info(f"Verifying email for user {request.user_id}")

    try:
        success = identity_manager.verify_email(
            user_id=request.user_id, verification_code=request.verification_code
        )

        if not success:
            raise HTTPException(
                status_code=400, detail="Invalid verification code or user not found"
            )

        return {
            "message": f"Email verified successfully for user {request.user_id}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to verify email for user {request.user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to verify email")


@router.post("/trust")
def trust_user(
    request: TrustUserRequest,
    identity_manager: IdentityManager = Depends(get_identity_manager),
):
    """
    Establish trust relationship between users.

    Args:
        request: Trust relationship request
        identity_manager: IdentityManager dependency

    Returns:
        Success message

    Raises:
        HTTPException: If trust establishment fails
    """
    logger.info(
        f"Establishing trust: {request.trustee_user_id} -> {request.trusted_user_id}"
    )

    try:
        success = identity_manager.trust_user(
            trustee_user_id=request.trustee_user_id,
            trusted_user_id=request.trusted_user_id,
        )

        if not success:
            raise HTTPException(
                status_code=400,
                detail="Failed to establish trust relationship. Check that trustee is verified and users exist.",
            )

        return {
            "message": f"Trust relationship established: {request.trustee_user_id} -> {request.trusted_user_id}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to establish trust relationship: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to establish trust relationship"
        )


@router.get("/users/{user_id}", response_model=UserIdentityResponse)
def get_user(
    user_id: str = Path(..., description="User ID"),
    identity_manager: IdentityManager = Depends(get_identity_manager),
):
    """
    Get user identity by ID.

    Args:
        user_id: User identifier
        identity_manager: IdentityManager dependency

    Returns:
        User identity details

    Raises:
        HTTPException: If user not found
    """
    logger.debug(f"Getting user {user_id}")

    try:
        user = identity_manager.get_user(user_id)
        if not user:
            raise HTTPException(
                status_code=404, detail=f"User {user_id} not found"
            )

        return UserIdentityResponse(
            user_id=user.user_id,
            email=user.email,
            display_name=user.display_name,
            public_key=user.public_key,
            verified=user.verified,
            trust_level=user.trust_level,
            created_at=user.created_at,
            verified_at=user.verified_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user")


@router.get("/users/email/{email}", response_model=UserIdentityResponse)
def get_user_by_email(
    email: str = Path(..., description="Email address"),
    identity_manager: IdentityManager = Depends(get_identity_manager),
):
    """
    Get user identity by email address.

    Args:
        email: Email address
        identity_manager: IdentityManager dependency

    Returns:
        User identity details

    Raises:
        HTTPException: If user not found
    """
    logger.debug(f"Getting user by email {email}")

    try:
        user = identity_manager.get_user_by_email(email)
        if not user:
            raise HTTPException(
                status_code=404, detail=f"User with email {email} not found"
            )

        return UserIdentityResponse(
            user_id=user.user_id,
            email=user.email,
            display_name=user.display_name,
            public_key=user.public_key,
            verified=user.verified,
            trust_level=user.trust_level,
            created_at=user.created_at,
            verified_at=user.verified_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user by email {email}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get user by email"
        )


@router.get("/users", response_model=UserListResponse)
def list_users(
    verified_only: bool = Query(
        False, description="Only return verified users"
    ),
    min_trust_level: int = Query(
        0, description="Minimum trust level filter", ge=0, le=2
    ),
    limit: int = Query(100, description="Maximum number of results", le=1000),
    identity_manager: IdentityManager = Depends(get_identity_manager),
):
    """
    List users with optional filtering.

    Args:
        verified_only: Only return verified users
        min_trust_level: Minimum trust level filter
        limit: Maximum number of results
        identity_manager: IdentityManager dependency

    Returns:
        List of user identities
    """
    logger.debug(
        f"Listing users (verified_only={verified_only}, min_trust={min_trust_level}, limit={limit})"
    )

    try:
        users = identity_manager.list_users(
            verified_only=verified_only, min_trust_level=min_trust_level, limit=limit
        )

        user_responses = []
        for user in users:
            user_responses.append(
                UserIdentityResponse(
                    user_id=user.user_id,
                    email=user.email,
                    display_name=user.display_name,
                    public_key=user.public_key,
                    verified=user.verified,
                    trust_level=user.trust_level,
                    created_at=user.created_at,
                    verified_at=user.verified_at,
                )
            )

        return UserListResponse(users=user_responses, total_count=len(user_responses))

    except Exception as e:
        logger.error(f"Failed to list users: {e}")
        raise HTTPException(status_code=500, detail="Failed to list users")


@router.get(
    "/users/{user_id}/trust-network", response_model=TrustNetworkResponse
)
def get_trust_network(
    user_id: str = Path(..., description="User ID"),
    identity_manager: IdentityManager = Depends(get_identity_manager),
):
    """
    Get trust network information for a user.

    Args:
        user_id: User identifier
        identity_manager: IdentityManager dependency

    Returns:
        Trust network details

    Raises:
        HTTPException: If user not found
    """
    logger.debug(f"Getting trust network for user {user_id}")

    try:
        # Check if user exists
        user = identity_manager.get_user(user_id)
        if not user:
            raise HTTPException(
                status_code=404, detail=f"User {user_id} not found"
            )

        trust_network = identity_manager.get_trust_network(user_id)

        return TrustNetworkResponse(
            user_id=user_id,
            trustees=trust_network.get("trustees", []),
            trusted=trust_network.get("trusted", []),
            trust_count=trust_network.get("trust_count", 0),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get trust network for user {user_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get trust network"
        )
