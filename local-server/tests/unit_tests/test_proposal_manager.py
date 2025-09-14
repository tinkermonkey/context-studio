"""
Unit tests for ProposalManager - Testing proposal creation, voting, and lifecycle management.

Tests proposal workflows, voting logic, auto-approval/rejection, and S3 integration.
"""

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest
import uuid
from unittest.mock import Mock, patch

from services.proposal_manager import ProposalManager
from services.collaboration_models import (
    Proposal, ProposalStatus, ChangesetState, Changeset
)
from services.changeset_manager import ChangesetManager
from services.s3_sync_manager import S3SyncManager


class TestProposalManager:
    """Test cases for ProposalManager functionality."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        db = Mock()
        db.execute.return_value.fetchone.return_value = None
        db.execute.return_value.fetchall.return_value = []
        db.execute.return_value.rowcount = 1
        db.rollback = Mock()
        db.commit = Mock()
        return db

    @pytest.fixture
    def mock_changeset_manager(self):
        """Mock ChangesetManager."""
        return Mock(spec=ChangesetManager)

    @pytest.fixture
    def mock_s3_sync_manager(self):
        """Mock S3SyncManager."""
        s3_sync = Mock(spec=S3SyncManager)
        s3_sync.s3_config = {'bucket': 'test-bucket'}
        s3_sync.parquet_writer = Mock()
        return s3_sync

    @pytest.fixture
    def proposal_manager(self, mock_db_session, mock_changeset_manager, mock_s3_sync_manager):
        """Create ProposalManager instance for testing."""
        return ProposalManager(
            db=mock_db_session,
            s3_sync_manager=mock_s3_sync_manager,
            changeset_manager=mock_changeset_manager
        )

    @pytest.fixture
    def mock_changeset(self):
        """Mock changeset for testing."""
        changeset = Mock(spec=Changeset)
        changeset.id = "changeset123"
        changeset.state = ChangesetState.DRAFT
        return changeset

    @pytest.fixture
    def mock_proposal(self):
        """Mock proposal for testing."""
        proposal = Mock(spec=Proposal)
        proposal.id = "proposal123"
        proposal.changeset_id = "changeset123"
        proposal.title = "Test Proposal"
        proposal.status = ProposalStatus.OPEN
        proposal.required_approvals = 2
        proposal.to_dict.return_value = {"id": "proposal123", "title": "Test Proposal"}
        return proposal

    def test_initialization(self, proposal_manager, mock_db_session, mock_changeset_manager, mock_s3_sync_manager):
        """Test ProposalManager initialization."""
        assert proposal_manager.db == mock_db_session
        assert proposal_manager.changeset_manager == mock_changeset_manager
        assert proposal_manager.s3_sync == mock_s3_sync_manager

    def test_create_proposal_success(self, proposal_manager, mock_changeset_manager, mock_changeset):
        """Test successful proposal creation."""
        mock_changeset_manager.get_changeset.return_value = mock_changeset

        with patch('uuid.uuid4') as mock_uuid:
            mock_uuid.return_value = uuid.UUID('12345678-1234-5678-9abc-123456789abc')
            
            proposal = proposal_manager.create_proposal(
                changeset_id="changeset123",
                title="Test Proposal",
                description="Test description",
                created_by="user123",
                required_approvals=2
            )

        assert proposal.id == "12345678-1234-5678-9abc-123456789abc"
        assert proposal.changeset_id == "changeset123"
        assert proposal.title == "Test Proposal"
        assert proposal.description == "Test description"
        assert proposal.created_by == "user123"
        assert proposal.required_approvals == 2
        assert proposal.status == ProposalStatus.OPEN

    def test_create_proposal_changeset_not_found(self, proposal_manager, mock_changeset_manager):
        """Test proposal creation when changeset not found."""
        mock_changeset_manager.get_changeset.return_value = None

        with pytest.raises(ValueError, match="Changeset changeset123 not found"):
            proposal_manager.create_proposal(
                changeset_id="changeset123",
                title="Test Proposal",
                description="Test description",
                created_by="user123"
            )

    def test_create_proposal_invalid_changeset_state(self, proposal_manager, mock_changeset_manager):
        """Test proposal creation with invalid changeset state."""
        mock_changeset = Mock()
        mock_changeset.state = ChangesetState.MERGED
        mock_changeset_manager.get_changeset.return_value = mock_changeset

        with pytest.raises(ValueError, match=r"Cannot create proposal for changeset in MERGED state"):
            proposal_manager.create_proposal(
                changeset_id="changeset123",
                title="Test Proposal",
                description="Test description",
                created_by="user123"
            )

    def test_create_proposal_invalid_approvals(self, proposal_manager, mock_changeset_manager, mock_changeset):
        """Test proposal creation with invalid required approvals."""
        mock_changeset_manager.get_changeset.return_value = mock_changeset

        with pytest.raises(ValueError, match="Required approvals must be at least 1"):
            proposal_manager.create_proposal(
                changeset_id="changeset123",
                title="Test Proposal",
                description="Test description",
                created_by="user123",
                required_approvals=0
            )

    def test_vote_on_proposal_success(self, proposal_manager, mock_proposal):
        """Test successful voting on proposal."""
        with patch.object(proposal_manager, 'get_proposal', return_value=mock_proposal):
            with patch.object(proposal_manager, 'get_user_vote', return_value=None):
                with patch.object(proposal_manager, '_store_vote_locally'):
                    with patch.object(proposal_manager, '_push_vote_to_s3'):
                        with patch.object(proposal_manager, '_evaluate_proposal_status'):
                            
                            vote = proposal_manager.vote_on_proposal(
                                proposal_id="proposal123",
                                user_id="user456",
                                vote="approve",
                                comment="Looks good!"
                            )

        assert vote.proposal_id == "proposal123"
        assert vote.user_id == "user456"
        assert vote.vote == "approve"
        assert vote.comment == "Looks good!"

    def test_vote_on_proposal_invalid_vote(self, proposal_manager):
        """Test voting with invalid vote value."""
        with pytest.raises(ValueError, match="Vote must be 'approve', 'reject', or 'abstain'"):
            proposal_manager.vote_on_proposal(
                proposal_id="proposal123",
                user_id="user456",
                vote="invalid",
                comment="Invalid vote"
            )

    def test_vote_on_proposal_not_found(self, proposal_manager):
        """Test voting on non-existent proposal."""
        with patch.object(proposal_manager, 'get_proposal', return_value=None):
            with pytest.raises(ValueError, match="Proposal proposal123 not found"):
                proposal_manager.vote_on_proposal(
                    proposal_id="proposal123",
                    user_id="user456",
                    vote="approve"
                )

    def test_vote_on_proposal_closed(self, proposal_manager):
        """Test voting on closed proposal."""
        mock_proposal = Mock()
        mock_proposal.status = ProposalStatus.APPROVED
        
        with patch.object(proposal_manager, 'get_proposal', return_value=mock_proposal):
            with pytest.raises(ValueError, match="Cannot vote on proposal with status approved"):
                proposal_manager.vote_on_proposal(
                    proposal_id="proposal123",
                    user_id="user456",
                    vote="approve"
                )

    def test_vote_update_existing(self, proposal_manager, mock_proposal):
        """Test updating existing vote."""
        existing_vote = Mock()
        existing_vote.vote = "abstain"
        
        with patch.object(proposal_manager, 'get_proposal', return_value=mock_proposal):
            with patch.object(proposal_manager, 'get_user_vote', return_value=existing_vote):
                with patch.object(proposal_manager, '_store_vote_locally') as mock_store:
                    with patch.object(proposal_manager, '_push_vote_to_s3'):
                        with patch.object(proposal_manager, '_evaluate_proposal_status'):
                            
                            proposal_manager.vote_on_proposal(
                                proposal_id="proposal123",
                                user_id="user456",
                                vote="approve"
                            )

        # Verify store was called with is_update=True
        mock_store.assert_called_once()
        call_args = mock_store.call_args
        assert call_args[0][1] is True  # is_update parameter

    def test_get_proposal_success(self, proposal_manager, mock_db_session):
        """Test successful proposal retrieval."""
        # Mock database response as tuple matching row_to_proposal() expectations
        mock_row = (
            "proposal123",                      # id
            "changeset123",                     # changeset_id
            "Test Proposal",                    # title
            "Test description",                 # description
            "open",                             # status
            2,                                  # required_approvals
            "user123",                          # created_by
            "2023-01-01T00:00:00+00:00",       # created_at
            None,                               # closed_at
            None,                               # merge_commit_id
            None                                # metadata
        )

        mock_db_session.execute.return_value.fetchone.return_value = mock_row

        proposal = proposal_manager.get_proposal("proposal123")

        assert proposal is not None
        assert proposal.id == "proposal123"
        assert proposal.title == "Test Proposal"
        assert proposal.status == ProposalStatus.OPEN

    def test_get_proposal_not_found(self, proposal_manager, mock_db_session):
        """Test proposal retrieval when not found."""
        mock_db_session.execute.return_value.fetchone.return_value = None

        proposal = proposal_manager.get_proposal("nonexistent")

        assert proposal is None

    def test_list_proposals_with_filters(self, proposal_manager, mock_db_session):
        """Test listing proposals with filters."""
        # Mock database response as tuple matching row_to_proposal() expectations
        mock_row = (
            "proposal123",                      # id
            "changeset123",                     # changeset_id
            "Test Proposal",                    # title
            "Test description",                 # description
            "open",                             # status
            2,                                  # required_approvals
            "user123",                          # created_by
            "2023-01-01T00:00:00+00:00",       # created_at
            None,                               # closed_at
            None,                               # merge_commit_id
            None                                # metadata
        )

        mock_db_session.execute.return_value.fetchall.return_value = [mock_row]

        proposals = proposal_manager.list_proposals(
            status=ProposalStatus.OPEN,
            created_by="user123",
            limit=50
        )

        assert len(proposals) == 1
        assert proposals[0].id == "proposal123"
        assert proposals[0].created_by == "user123"

    def test_get_proposal_votes(self, proposal_manager, mock_db_session):
        """Test getting proposal votes."""
        # Mock database response as tuple matching row_to_vote() expectations
        mock_row = (
            "proposal123",                      # proposal_id
            "user456",                          # user_id
            "approve",                          # vote
            "Looks good!",                      # comment
            "2023-01-01T00:00:00+00:00"        # voted_at
        )

        mock_db_session.execute.return_value.fetchall.return_value = [mock_row]

        votes = proposal_manager.get_proposal_votes("proposal123")

        assert len(votes) == 1
        assert votes[0].proposal_id == "proposal123"
        assert votes[0].user_id == "user456"
        assert votes[0].vote == "approve"

    def test_get_vote_summary(self, proposal_manager):
        """Test getting vote summary."""
        mock_votes = [
            Mock(vote="approve", user_id="user1"),
            Mock(vote="approve", user_id="user2"),
            Mock(vote="reject", user_id="user3"),
            Mock(vote="abstain", user_id="user4")
        ]

        with patch.object(proposal_manager, 'get_proposal_votes', return_value=mock_votes):
            summary = proposal_manager.get_vote_summary("proposal123")

        assert summary["total_votes"] == 4
        assert summary["approve_votes"] == 2
        assert summary["reject_votes"] == 1
        assert summary["abstain_votes"] == 1
        assert summary["voters"] == ["user1", "user2", "user3", "user4"]

    def test_evaluate_proposal_status_auto_approve(self, proposal_manager):
        """Test auto-approval when threshold met."""
        mock_proposal = Mock()
        mock_proposal.status = ProposalStatus.OPEN
        mock_proposal.required_approvals = 2

        vote_summary = {
            "approve_votes": 2,
            "reject_votes": 0,
            "abstain_votes": 0,
            "total_votes": 2
        }

        with patch.object(proposal_manager, 'get_proposal', return_value=mock_proposal):
            with patch.object(proposal_manager, 'get_proposal_votes', return_value=[]):
                with patch.object(proposal_manager, 'get_vote_summary', return_value=vote_summary):
                    with patch.object(proposal_manager, '_update_proposal_status') as mock_update:
                        with patch.object(proposal_manager, '_auto_merge_if_enabled'):
                            
                            proposal_manager._evaluate_proposal_status("proposal123")

        mock_update.assert_called_once_with("proposal123", ProposalStatus.APPROVED)

    def test_evaluate_proposal_status_auto_reject(self, proposal_manager):
        """Test auto-rejection when reject threshold met."""
        mock_proposal = Mock()
        mock_proposal.status = ProposalStatus.OPEN
        mock_proposal.required_approvals = 2

        vote_summary = {
            "approve_votes": 0,
            "reject_votes": 2,
            "abstain_votes": 0,
            "total_votes": 2
        }

        with patch.object(proposal_manager, 'get_proposal', return_value=mock_proposal):
            with patch.object(proposal_manager, 'get_proposal_votes', return_value=[]):
                with patch.object(proposal_manager, 'get_vote_summary', return_value=vote_summary):
                    with patch.object(proposal_manager, '_update_proposal_status') as mock_update:
                        
                        proposal_manager._evaluate_proposal_status("proposal123")

        mock_update.assert_called_once_with("proposal123", ProposalStatus.REJECTED)

    def test_update_proposal_status_with_changeset_update(self, proposal_manager, mock_changeset_manager):
        """Test proposal status update also updates changeset state."""
        mock_proposal = Mock()
        mock_proposal.changeset_id = "changeset123"
        
        with patch.object(proposal_manager, 'get_proposal', return_value=mock_proposal):
            proposal_manager._update_proposal_status("proposal123", ProposalStatus.APPROVED)

        mock_changeset_manager.update_changeset_state.assert_called_once_with(
            "changeset123", ChangesetState.APPROVED
        )

    def test_push_vote_to_s3_success(self, proposal_manager, mock_s3_sync_manager):
        """Test successful vote push to S3."""
        mock_vote = Mock()
        mock_vote.proposal_id = "proposal123"
        mock_vote.user_id = "user456"
        mock_vote.to_dict.return_value = {"proposal_id": "proposal123", "user_id": "user456"}

        proposal_manager._push_vote_to_s3(mock_vote)

        mock_s3_sync_manager.parquet_writer.write_metadata.assert_called_once()

    def test_push_vote_to_s3_failure_handling(self, proposal_manager, mock_s3_sync_manager):
        """Test S3 push failure doesn't break operation."""
        mock_vote = Mock()
        mock_vote.proposal_id = "proposal123"
        mock_vote.user_id = "user456"
        mock_vote.to_dict.return_value = {"proposal_id": "proposal123", "user_id": "user456"}

        mock_s3_sync_manager.parquet_writer.write_metadata.side_effect = Exception("S3 error")

        # Should not raise exception
        proposal_manager._push_vote_to_s3(mock_vote)

    def test_database_transaction_rollback_on_error(self, proposal_manager, mock_db_session, mock_changeset_manager, mock_changeset):
        """Test database rollback on error."""
        mock_changeset_manager.get_changeset.return_value = mock_changeset
        mock_db_session.execute.side_effect = Exception("Database error")

        with pytest.raises(RuntimeError, match="Failed to create proposal"):
            proposal_manager.create_proposal(
                changeset_id="changeset123",
                title="Test Proposal",
                description="Test description",
                created_by="user123"
            )

        # Verify rollback was called on vote operation error
        mock_db_session.rollback.assert_called()