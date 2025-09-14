"""
Unit tests for IdentityManager - Testing user identity, email verification, and trust systems.

Tests user registration, email verification, peer trust networks, and identity management.
"""

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from services.identity_manager import IdentityManager
from services.collaboration_models import UserIdentity
from services.s3_sync_manager import S3SyncManager


class TestIdentityManager:
    """Test cases for IdentityManager functionality."""

    @pytest.fixture(autouse=True)
    def reset_mocks(self):
        """Reset mock state between tests for proper isolation."""
        yield
        # Fixture cleanup happens automatically after each test

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session with proper tuple-like row responses."""
        db = Mock()

        # Configure execute() to return proper Mock result objects
        mock_result = Mock()
        mock_result.fetchone.return_value = None
        mock_result.fetchall.return_value = []
        mock_result.rowcount = 1

        db.execute.return_value = mock_result
        db.commit = Mock()
        db.rollback = Mock()

        return db

    @pytest.fixture
    def mock_s3_sync_manager(self):
        """Mock S3SyncManager."""
        return Mock(spec=S3SyncManager)

    @pytest.fixture
    def identity_manager(self, mock_db_session, mock_s3_sync_manager):
        """Create IdentityManager instance for testing."""
        return IdentityManager(
            db=mock_db_session,
            s3_sync_manager=mock_s3_sync_manager
        )

    @pytest.fixture
    def mock_user_identity(self):
        """Mock user identity for testing."""
        user = Mock(spec=UserIdentity)
        user.user_id = "user123"
        user.email = "test@example.com"
        user.display_name = "Test User"
        user.verified = False
        user.trust_level = 0
        user.created_at = datetime.now(timezone.utc)
        user.verified_at = None
        return user

    def test_initialization(self, identity_manager, mock_db_session, mock_s3_sync_manager):
        """Test IdentityManager initialization."""
        assert identity_manager.db == mock_db_session
        assert identity_manager.s3_sync == mock_s3_sync_manager

    def test_register_user_success(self, identity_manager):
        """Test successful user registration."""
        with patch.object(identity_manager, 'get_user', return_value=None):
            with patch.object(identity_manager, '_generate_user_id', return_value="user123"):
                with patch.object(identity_manager, '_store_identity_locally'):
                    with patch.object(identity_manager, '_generate_verification_code', return_value="123456"):
                        with patch.object(identity_manager, '_store_verification_code'):
                            
                            result = identity_manager.register_user(
                                email="test@example.com",
                                display_name="Test User"
                            )

        assert result["message"] == "User registered successfully"
        assert result["verification_code"] == "123456"
        assert result["user_identity"].user_id == "user123"
        assert result["user_identity"].email == "test@example.com"
        assert result["user_identity"].display_name == "Test User"

    def test_register_user_existing(self, identity_manager, mock_user_identity):
        """Test registration of existing user."""
        with patch.object(identity_manager, 'get_user', return_value=mock_user_identity):
            with patch.object(identity_manager, '_generate_user_id', return_value="user123"):
                with patch.object(identity_manager, '_generate_verification_code', return_value="654321"):
                    with patch.object(identity_manager, '_store_verification_code'):
                        
                        result = identity_manager.register_user(
                            email="test@example.com",
                            display_name="Test User"
                        )

        assert result["message"] == "User already exists, new verification code generated"
        assert result["verification_code"] == "654321"
        assert result["user_identity"] == mock_user_identity

    def test_register_user_invalid_email(self, identity_manager):
        """Test user registration with invalid email."""
        with pytest.raises(ValueError, match="Invalid email format"):
            identity_manager.register_user(
                email="invalid-email",
                display_name="Test User"
            )

        with pytest.raises(ValueError, match="Invalid email format"):
            identity_manager.register_user(
                email="test@",
                display_name="Test User"
            )

    def test_register_user_empty_fields(self, identity_manager):
        """Test user registration with empty fields."""
        with pytest.raises(ValueError, match="Email and display name are required"):
            identity_manager.register_user(
                email="",
                display_name="Test User"
            )

        with pytest.raises(ValueError, match="Email and display name are required"):
            identity_manager.register_user(
                email="test@example.com",
                display_name=""
            )

    def test_verify_email_success(self, identity_manager, mock_db_session):
        """Test successful email verification."""
        with patch.object(identity_manager, '_get_verification_code', return_value="123456"):
            with patch.object(identity_manager, '_delete_verification_code'):
                mock_db_session.execute.return_value.rowcount = 1
                
                success = identity_manager.verify_email("user123", "123456")

        assert success is True

    def test_verify_email_invalid_code(self, identity_manager):
        """Test email verification with invalid code."""
        with patch.object(identity_manager, '_get_verification_code', return_value="123456"):
            success = identity_manager.verify_email("user123", "wrong_code")

        assert success is False

    def test_verify_email_no_code(self, identity_manager):
        """Test email verification when no code exists."""
        with patch.object(identity_manager, '_get_verification_code', return_value=None):
            success = identity_manager.verify_email("user123", "123456")

        assert success is False

    def test_verify_email_user_not_found(self, identity_manager, mock_db_session):
        """Test email verification when user not found."""
        with patch.object(identity_manager, '_get_verification_code', return_value="123456"):
            mock_db_session.execute.return_value.rowcount = 0
            
            success = identity_manager.verify_email("nonexistent", "123456")

        assert success is False

    def test_trust_user_success(self, identity_manager, mock_db_session):
        """Test successful trust relationship establishment."""
        # Mock verified trustee
        mock_trustee = Mock()
        mock_trustee.trust_level = 1

        # Mock trusted user
        mock_trusted = Mock()
        mock_trusted.trust_level = 0

        with patch.object(identity_manager, 'get_user') as mock_get_user:
            mock_get_user.side_effect = [mock_trustee, mock_trusted]
            with patch.object(identity_manager, '_count_trust_relationships', return_value=1):
                
                success = identity_manager.trust_user("trustee123", "trusted456")

        assert success is True

    def test_trust_user_trustee_not_verified(self, identity_manager):
        """Test trust establishment when trustee not verified."""
        # Mock unverified trustee
        mock_trustee = Mock()
        mock_trustee.trust_level = 0

        with patch.object(identity_manager, 'get_user', return_value=mock_trustee):
            success = identity_manager.trust_user("trustee123", "trusted456")

        assert success is False

    def test_trust_user_trustee_not_found(self, identity_manager):
        """Test trust establishment when trustee not found."""
        with patch.object(identity_manager, 'get_user', return_value=None):
            success = identity_manager.trust_user("nonexistent", "trusted456")

        assert success is False

    def test_trust_user_trusted_not_found(self, identity_manager):
        """Test trust establishment when trusted user not found."""
        # Mock verified trustee
        mock_trustee = Mock()
        mock_trustee.trust_level = 1

        with patch.object(identity_manager, 'get_user') as mock_get_user:
            mock_get_user.side_effect = [mock_trustee, None]
            
            success = identity_manager.trust_user("trustee123", "nonexistent")

        assert success is False

    def test_trust_user_self_trust(self, identity_manager):
        """Test trust establishment when trying to trust self."""
        # Mock verified user
        mock_user = Mock()
        mock_user.trust_level = 1

        with patch.object(identity_manager, 'get_user', return_value=mock_user):
            success = identity_manager.trust_user("user123", "user123")

        assert success is False

    def test_trust_user_promotion_to_team_verified(self, identity_manager, mock_db_session):
        """Test user promotion to team-verified when reaching trust threshold."""
        # Mock verified trustee
        mock_trustee = Mock()
        mock_trustee.trust_level = 1

        # Mock trusted user
        mock_trusted = Mock()
        mock_trusted.trust_level = 0

        with patch.object(identity_manager, 'get_user') as mock_get_user:
            mock_get_user.side_effect = [mock_trustee, mock_trusted]
            with patch.object(identity_manager, '_count_trust_relationships', return_value=2):
                
                success = identity_manager.trust_user("trustee123", "trusted456")

        assert success is True
        # Verify trust level was updated to 2 (team-verified)
        # Check that the database execute was called with trust_level update
        call_found = False
        for call in mock_db_session.execute.call_args_list:
            if len(call.args) > 0:
                sql_statement = str(call.args[0])
                if "trust_level = 2" in sql_statement:
                    call_found = True
                    break
        assert call_found, f"Expected trust_level=2 update not found in calls: {mock_db_session.execute.call_args_list}"

    def test_get_user_success(self, identity_manager, mock_db_session):
        """Test successful user retrieval."""
        # Mock database response - needs to be indexable like a tuple
        mock_row = ("user123", "test@example.com", "Test User", None, 1, 1, "2023-01-01T00:00:00+00:00", "2023-01-01T01:00:00+00:00")

        mock_db_session.execute.return_value.fetchone.return_value = mock_row

        user = identity_manager.get_user("user123")

        assert user is not None
        assert user.user_id == "user123"
        assert user.email == "test@example.com"
        assert user.display_name == "Test User"

    def test_get_user_not_found(self, identity_manager, mock_db_session):
        """Test user retrieval when not found."""
        mock_db_session.execute.return_value.fetchone.return_value = None

        user = identity_manager.get_user("nonexistent")

        assert user is None

    def test_get_user_by_email_success(self, identity_manager, mock_db_session):
        """Test successful user retrieval by email."""
        # Mock database response - needs to be indexable like a tuple
        mock_row = ("user123", "test@example.com", "Test User", None, 1, 1, "2023-01-01T00:00:00+00:00", "2023-01-01T01:00:00+00:00")

        mock_db_session.execute.return_value.fetchone.return_value = mock_row

        user = identity_manager.get_user_by_email("test@example.com")

        assert user is not None
        assert user.email == "test@example.com"

    def test_get_user_by_email_case_insensitive(self, identity_manager, mock_db_session):
        """Test user retrieval by email is case insensitive."""
        mock_db_session.execute.return_value.fetchone.return_value = None

        identity_manager.get_user_by_email("Test@Example.COM")

        # Verify the email was converted to lowercase
        call_args = mock_db_session.execute.call_args
        assert call_args[0][1][0] == "test@example.com"

    def test_list_users_with_filters(self, identity_manager, mock_db_session):
        """Test listing users with filters."""
        # Mock database response - needs to be indexable like a tuple
        mock_row = ("user123", "test@example.com", "Test User", None, 1, 2, "2023-01-01T00:00:00+00:00", "2023-01-01T01:00:00+00:00")

        mock_db_session.execute.return_value.fetchall.return_value = [mock_row]

        users = identity_manager.list_users(
            verified_only=True,
            min_trust_level=2,
            limit=50
        )

        assert len(users) == 1
        assert users[0].user_id == "user123"
        assert users[0].trust_level == 2

    def test_get_trust_network_success(self, identity_manager, mock_db_session):
        """Test getting trust network."""
        # Mock trustees (users who trust this user) - needs to be indexable like tuples
        mock_trustee_rows = [
            ("trustee1", "2023-01-01T00:00:00+00:00"),
            ("trustee2", "2023-01-02T00:00:00+00:00")
        ]

        # Mock trusted (users this user trusts) - needs to be indexable like tuples
        mock_trusted_rows = [
            ("trusted1", "2023-01-03T00:00:00+00:00")
        ]

        mock_db_session.execute.side_effect = [
            Mock(fetchall=Mock(return_value=mock_trustee_rows)),
            Mock(fetchall=Mock(return_value=mock_trusted_rows))
        ]

        network = identity_manager.get_trust_network("user123")

        assert "trusted_by" in network
        assert "trusts" in network
        assert "trust_score" in network
        assert "trusts_count" in network

    def test_generate_user_id_deterministic(self, identity_manager):
        """Test user ID generation is deterministic."""
        email = "test@example.com"
        
        user_id1 = identity_manager._generate_user_id(email)
        user_id2 = identity_manager._generate_user_id(email)
        
        assert user_id1 == user_id2
        assert len(user_id1) == 16  # First 16 chars of SHA-256

    def test_generate_verification_code_format(self, identity_manager):
        """Test verification code generation format."""
        code = identity_manager._generate_verification_code()
        
        assert len(code) == 6
        assert code.isdigit()

    def test_store_identity_locally(self, identity_manager, mock_db_session):
        """Test storing identity in local database."""
        mock_identity = Mock()
        mock_identity.user_id = "user123"
        mock_identity.email = "test@example.com"
        mock_identity.display_name = "Test User"
        mock_identity.public_key = None
        mock_identity.verified = False
        mock_identity.trust_level = 0
        mock_identity.created_at = datetime.now(timezone.utc)
        mock_identity.verified_at = None

        identity_manager._store_identity_locally(mock_identity)

        # Verify database insert was called
        mock_db_session.execute.assert_called()

    def test_count_trust_relationships(self, identity_manager, mock_db_session):
        """Test counting trust relationships."""
        # Mock database response - needs to be indexable like a tuple/list
        mock_db_session.execute.return_value.fetchone.return_value = (3,)

        count = identity_manager._count_trust_relationships("user123")

        assert count == 3

    def test_database_transaction_rollback_on_error(self, identity_manager, mock_db_session):
        """Test database rollback on error."""
        with patch.object(identity_manager, 'get_user', return_value=None):
            with patch.object(identity_manager, '_generate_user_id', return_value="user123"):
                mock_db_session.execute.side_effect = Exception("Database error")

                with pytest.raises(RuntimeError, match="Failed to register user"):
                    identity_manager.register_user(
                        email="test@example.com",
                        display_name="Test User"
                    )

        # Verify rollback was called
        mock_db_session.rollback.assert_called_once()

    def test_verification_code_cleanup_on_verification(self, identity_manager, mock_db_session):
        """Test verification code is cleaned up after successful verification."""
        with patch.object(identity_manager, '_get_verification_code', return_value="123456"):
            with patch.object(identity_manager, '_delete_verification_code') as mock_delete:
                mock_db_session.execute.return_value.rowcount = 1
                
                success = identity_manager.verify_email("user123", "123456")

        assert success is True
        mock_delete.assert_called_once_with("user123")