"""
IdentityManager Service - Manages user identity and trust verification

This service provides lightweight identity management with email-based verification
and peer trust systems for collaborative workflows without complex infrastructure.
"""

import hashlib
import random
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text

from services.collaboration_models import UserIdentity, row_to_identity
from services.s3_sync_manager import S3SyncManager
from utils.logger import get_logger

logger = get_logger(__name__)


class IdentityManager:
    """Manages user identity and trust verification."""
    
    def __init__(self, db: Session, s3_sync_manager: S3SyncManager):
        """
        Initialize the IdentityManager.
        
        Args:
            db: SQLAlchemy database session
            s3_sync_manager: S3 synchronization manager
        """
        self.db = db
        self.s3_sync = s3_sync_manager
        logger.info("IdentityManager initialized")
    
    def register_user(self, email: str, display_name: str) -> Dict[str, Any]:
        """
        Register new user with email-based identity.
        
        Args:
            email: User's email address
            display_name: User's display name
            
        Returns:
            Dictionary with user identity and verification code
            
        Raises:
            ValueError: If validation fails
            RuntimeError: If registration fails
        """
        logger.info(f"Registering user with email {email}")
        
        # Validate inputs
        if not email or not display_name:
            raise ValueError("Email and display name are required")
            
        if '@' not in email or '.' not in email.split('@')[1]:
            raise ValueError("Invalid email format")
        
        # Generate deterministic user ID from email
        user_id = self._generate_user_id(email)
        
        # Check if user already exists
        existing = self.get_user(user_id)
        if existing:
            logger.info(f"User {user_id} already exists, returning existing identity")
            # Return existing user with new verification code
            verification_code = self._generate_verification_code()
            self._store_verification_code(user_id, verification_code)
            
            return {
                "user_identity": existing,
                "verification_code": verification_code,
                "message": "User already exists, new verification code generated"
            }
        
        try:
            # Create new user identity
            identity = UserIdentity(
                user_id=user_id,
                email=email.lower().strip(),
                display_name=display_name.strip(),
                public_key=None,
                verified=False,
                trust_level=0,
                created_at=datetime.now(timezone.utc)
            )
            
            # Store locally
            self._store_identity_locally(identity)
            
            # Generate and store verification code
            verification_code = self._generate_verification_code()
            self._store_verification_code(user_id, verification_code)
            
            # Commit transaction
            self.db.commit()
            
            logger.info(f"Successfully registered user {user_id} ({email})")
            
            return {
                "user_identity": identity,
                "verification_code": verification_code,
                "message": "User registered successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to register user {email}: {e}")
            self.db.rollback()
            raise RuntimeError(f"Failed to register user: {e}")
    
    def verify_email(self, user_id: str, verification_code: str) -> bool:
        """
        Verify user email with verification code.
        
        Args:
            user_id: User identifier
            verification_code: 6-digit verification code
            
        Returns:
            True if verification successful
        """
        logger.info(f"Verifying email for user {user_id}")
        
        try:
            # Get stored verification code
            stored_code = self._get_verification_code(user_id)
            if not stored_code:
                logger.warning(f"No verification code found for user {user_id}")
                return False
                
            if stored_code != verification_code:
                logger.warning(f"Invalid verification code for user {user_id}")
                return False
            
            # Update user verification status
            cursor = self.db.execute(
                text("""
                    UPDATE user_identities 
                    SET verified = 1, trust_level = 1, verified_at = ?
                    WHERE user_id = ?
                """),
                (datetime.now(timezone.utc).isoformat(), user_id)
            )
            
            if cursor.rowcount == 0:
                logger.warning(f"No user found with ID {user_id}")
                return False
            
            # Clean up verification code
            self._delete_verification_code(user_id)
            
            # Commit transaction
            self.db.commit()
            
            logger.info(f"Successfully verified email for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to verify email for user {user_id}: {e}")
            self.db.rollback()
            return False
    
    def trust_user(self, trustee_user_id: str, trusted_user_id: str) -> bool:
        """
        Allow one verified user to vouch for another (peer verification).
        
        Args:
            trustee_user_id: ID of user providing trust
            trusted_user_id: ID of user receiving trust
            
        Returns:
            True if trust relationship established
        """
        logger.info(f"User {trustee_user_id} trusting user {trusted_user_id}")
        
        try:
            # Validate trustee exists and is verified
            trustee = self.get_user(trustee_user_id)
            if not trustee or trustee.trust_level < 1:
                logger.warning(f"Trustee {trustee_user_id} not found or not verified")
                return False  # Only verified users can vouch for others
            
            # Validate trusted user exists
            trusted = self.get_user(trusted_user_id)
            if not trusted:
                logger.warning(f"Trusted user {trusted_user_id} not found")
                return False
            
            # Don't allow self-trust
            if trustee_user_id == trusted_user_id:
                logger.warning("Cannot trust self")
                return False
            
            # Record trust relationship (INSERT OR REPLACE for updates)
            self.db.execute(
                text("""
                    INSERT OR REPLACE INTO user_trust_relationships 
                    (trustee_user_id, trusted_user_id, created_at)
                    VALUES (?, ?, ?)
                """),
                (trustee_user_id, trusted_user_id, datetime.now(timezone.utc).isoformat())
            )
            
            # Check if user now has enough trust to be team-verified
            trust_count = self._count_trust_relationships(trusted_user_id)
            logger.debug(f"User {trusted_user_id} now has {trust_count} trust relationships")
            
            if trust_count >= 2:  # Require 2 team members to vouch
                logger.info(f"Promoting user {trusted_user_id} to team-verified (trust_level=2)")
                self.db.execute(
                    text("UPDATE user_identities SET trust_level = 2 WHERE user_id = ?"),
                    (trusted_user_id,)
                )
            
            self.db.commit()
            
            logger.info(f"Successfully established trust relationship: {trustee_user_id} -> {trusted_user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to establish trust relationship: {e}")
            self.db.rollback()
            return False
    
    def get_user(self, user_id: str) -> Optional[UserIdentity]:
        """
        Get user identity by ID.
        
        Args:
            user_id: User identifier
            
        Returns:
            UserIdentity instance or None if not found
        """
        logger.debug(f"Getting user {user_id}")
        
        try:
            result = self.db.execute(
                text("SELECT * FROM user_identities WHERE user_id = ?"),
                (user_id,)
            ).fetchone()
            
            if not result:
                logger.debug(f"User {user_id} not found")
                return None
                
            return row_to_identity(result)
            
        except Exception as e:
            logger.error(f"Failed to get user {user_id}: {e}")
            return None
    
    def get_user_by_email(self, email: str) -> Optional[UserIdentity]:
        """
        Get user identity by email address.
        
        Args:
            email: Email address
            
        Returns:
            UserIdentity instance or None if not found
        """
        logger.debug(f"Getting user by email {email}")
        
        try:
            result = self.db.execute(
                text("SELECT * FROM user_identities WHERE email = ?"),
                (email.lower().strip(),)
            ).fetchone()
            
            if not result:
                logger.debug(f"User with email {email} not found")
                return None
                
            return row_to_identity(result)
            
        except Exception as e:
            logger.error(f"Failed to get user by email {email}: {e}")
            return None
    
    def list_users(self, verified_only: bool = False, min_trust_level: int = 0,
                   limit: int = 100) -> List[UserIdentity]:
        """
        List users with optional filtering.
        
        Args:
            verified_only: Only return verified users
            min_trust_level: Minimum trust level filter
            limit: Maximum number of results
            
        Returns:
            List of UserIdentity instances
        """
        logger.debug(f"Listing users (verified_only={verified_only}, min_trust={min_trust_level})")
        
        try:
            query = "SELECT * FROM user_identities WHERE 1=1"
            params = []
            
            if verified_only:
                query += " AND verified = 1"
                
            if min_trust_level > 0:
                query += " AND trust_level >= ?"
                params.append(min_trust_level)
                
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            results = self.db.execute(text(query), params).fetchall()
            users = [row_to_identity(row) for row in results]
            
            logger.debug(f"Found {len(users)} users")
            return users
            
        except Exception as e:
            logger.error(f"Failed to list users: {e}")
            return []
    
    def get_trust_network(self, user_id: str) -> Dict[str, Any]:
        """
        Get trust network information for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary with trust relationships
        """
        logger.debug(f"Getting trust network for user {user_id}")
        
        try:
            # Get users who trust this user
            trustees = self.db.execute(
                text("""
                    SELECT trustee_user_id, created_at FROM user_trust_relationships 
                    WHERE trusted_user_id = ?
                    ORDER BY created_at
                """),
                (user_id,)
            ).fetchall()
            
            # Get users this user trusts
            trusted = self.db.execute(
                text("""
                    SELECT trusted_user_id, created_at FROM user_trust_relationships 
                    WHERE trustee_user_id = ?
                    ORDER BY created_at
                """),
                (user_id,)
            ).fetchall()
            
            return {
                "user_id": user_id,
                "trusted_by": [{"user_id": row[0], "since": row[1]} for row in trustees],
                "trusts": [{"user_id": row[0], "since": row[1]} for row in trusted],
                "trust_score": len(trustees),  # Number of users who trust this user
                "trusts_count": len(trusted)   # Number of users this user trusts
            }
            
        except Exception as e:
            logger.error(f"Failed to get trust network for user {user_id}: {e}")
            return {"user_id": user_id, "trusted_by": [], "trusts": [], "trust_score": 0, "trusts_count": 0}
    
    def revoke_trust(self, trustee_user_id: str, trusted_user_id: str) -> bool:
        """
        Revoke trust relationship.
        
        Args:
            trustee_user_id: ID of user revoking trust
            trusted_user_id: ID of user losing trust
            
        Returns:
            True if trust revoked successfully
        """
        logger.info(f"Revoking trust: {trustee_user_id} -> {trusted_user_id}")
        
        try:
            cursor = self.db.execute(
                text("""
                    DELETE FROM user_trust_relationships 
                    WHERE trustee_user_id = ? AND trusted_user_id = ?
                """),
                (trustee_user_id, trusted_user_id)
            )
            
            if cursor.rowcount == 0:
                logger.warning("No trust relationship found to revoke")
                return False
            
            # Recalculate trust level for trusted user
            trust_count = self._count_trust_relationships(trusted_user_id)
            new_trust_level = min(2, max(1, trust_count))  # At least 1 if verified, max 2
            
            # Update trust level
            user = self.get_user(trusted_user_id)
            if user and user.verified:
                final_trust_level = max(1, new_trust_level) if trust_count >= 2 else 1
            else:
                final_trust_level = 0  # Unverified users stay at 0
                
            self.db.execute(
                text("UPDATE user_identities SET trust_level = ? WHERE user_id = ?"),
                (final_trust_level, trusted_user_id)
            )
            
            self.db.commit()
            
            logger.info(f"Trust revoked, user {trusted_user_id} trust_level updated to {final_trust_level}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to revoke trust: {e}")
            self.db.rollback()
            return False
    
    def _generate_user_id(self, email: str) -> str:
        """
        Generate deterministic user ID from email.
        
        Args:
            email: Email address
            
        Returns:
            16-character hex user ID
        """
        return hashlib.sha256(email.lower().encode()).hexdigest()[:16]
    
    def _generate_verification_code(self) -> str:
        """
        Generate 6-digit verification code.
        
        Returns:
            6-digit verification code as string
        """
        return f"{random.randint(100000, 999999)}"
    
    def _store_identity_locally(self, identity: UserIdentity) -> None:
        """
        Store user identity in local SQLite database.
        
        Args:
            identity: UserIdentity instance to store
        """
        logger.debug(f"Storing identity {identity.user_id} locally")
        
        query = """
        INSERT INTO user_identities (
            user_id, email, display_name, public_key, verified, trust_level, 
            created_at, verified_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        params = (
            identity.user_id, identity.email, identity.display_name, 
            identity.public_key, identity.verified, identity.trust_level,
            identity.created_at.isoformat(),
            identity.verified_at.isoformat() if identity.verified_at else None
        )
        
        self.db.execute(text(query), params)
        logger.debug(f"Stored identity {identity.user_id} in database")
    
    def _store_verification_code(self, user_id: str, code: str) -> None:
        """
        Store verification code with expiration.
        
        Args:
            user_id: User identifier
            code: Verification code
        """
        logger.debug(f"Storing verification code for user {user_id}")
        
        # Code expires in 1 hour
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        
        # Use INSERT OR REPLACE to handle multiple verification attempts
        query = """
        INSERT OR REPLACE INTO verification_codes (
            user_id, code, created_at, expires_at
        ) VALUES (?, ?, ?, ?)
        """
        
        params = (
            user_id, code, 
            datetime.now(timezone.utc).isoformat(),
            expires_at.isoformat()
        )
        
        self.db.execute(text(query), params)
        logger.debug(f"Stored verification code for user {user_id}")
    
    def _get_verification_code(self, user_id: str) -> Optional[str]:
        """
        Get stored verification code for user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Verification code or None if not found/expired
        """
        logger.debug(f"Getting verification code for user {user_id}")
        
        try:
            result = self.db.execute(
                text("""
                    SELECT code, expires_at FROM verification_codes 
                    WHERE user_id = ?
                """),
                (user_id,)
            ).fetchone()
            
            if not result:
                logger.debug(f"No verification code found for user {user_id}")
                return None
            
            code, expires_at_str = result
            expires_at = datetime.fromisoformat(expires_at_str)
            
            # Check if code has expired
            if datetime.now(timezone.utc) > expires_at:
                logger.debug(f"Verification code expired for user {user_id}")
                # Clean up expired code
                self._delete_verification_code(user_id)
                return None
            
            return code
            
        except Exception as e:
            logger.error(f"Failed to get verification code for user {user_id}: {e}")
            return None
    
    def _delete_verification_code(self, user_id: str) -> None:
        """
        Delete verification code for user.
        
        Args:
            user_id: User identifier
        """
        logger.debug(f"Deleting verification code for user {user_id}")
        
        self.db.execute(
            text("DELETE FROM verification_codes WHERE user_id = ?"),
            (user_id,)
        )
    
    def _count_trust_relationships(self, trusted_user_id: str) -> int:
        """
        Count how many users trust the given user.
        
        Args:
            trusted_user_id: User identifier
            
        Returns:
            Number of trust relationships
        """
        try:
            result = self.db.execute(
                text("""
                    SELECT COUNT(*) FROM user_trust_relationships 
                    WHERE trusted_user_id = ?
                """),
                (trusted_user_id,)
            ).fetchone()
            
            return result[0] if result else 0
            
        except Exception as e:
            logger.error(f"Failed to count trust relationships for user {trusted_user_id}: {e}")
            return 0
    
    def cleanup_expired_codes(self) -> int:
        """
        Clean up expired verification codes.
        
        Returns:
            Number of codes cleaned up
        """
        logger.info("Cleaning up expired verification codes")
        
        try:
            cursor = self.db.execute(
                text("""
                    DELETE FROM verification_codes 
                    WHERE expires_at < ?
                """),
                (datetime.now(timezone.utc).isoformat(),)
            )
            
            cleaned_count = cursor.rowcount
            self.db.commit()
            
            logger.info(f"Cleaned up {cleaned_count} expired verification codes")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired codes: {e}")
            return 0