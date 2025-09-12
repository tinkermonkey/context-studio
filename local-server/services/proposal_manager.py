"""
ProposalManager Service - Manages proposal creation, voting, and lifecycle

This service handles the creation and management of proposals for collaborative review
and voting on changesets in the change management workflow.
"""

import uuid
import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text

from services.collaboration_models import (
    Proposal, ProposalStatus, ProposalVote, ChangesetState,
    row_to_proposal, row_to_vote
)
from services.changeset_manager import ChangesetManager
from services.s3_sync_manager import S3SyncManager
from utils.logger import get_logger

logger = get_logger(__name__)


class ProposalManager:
    """Manages proposal creation, voting, and lifecycle."""
    
    def __init__(self, db: Session, s3_sync_manager: S3SyncManager, 
                 changeset_manager: ChangesetManager):
        """
        Initialize the ProposalManager.
        
        Args:
            db: SQLAlchemy database session
            s3_sync_manager: S3 synchronization manager
            changeset_manager: Changeset management service
        """
        self.db = db
        self.s3_sync = s3_sync_manager
        self.changeset_manager = changeset_manager
        logger.info("ProposalManager initialized")
    
    def create_proposal(self, changeset_id: str, title: str, description: str,
                       created_by: str, required_approvals: int = 1) -> Proposal:
        """
        Create a new proposal for changeset review.
        
        Args:
            changeset_id: ID of the changeset to propose
            title: Proposal title
            description: Detailed description
            created_by: User ID of proposal creator
            required_approvals: Number of approvals needed
            
        Returns:
            Created Proposal instance
            
        Raises:
            ValueError: If validation fails
            RuntimeError: If database operation fails
        """
        logger.info(f"Creating proposal for changeset {changeset_id} by {created_by}")
        
        # Validate changeset exists and is in appropriate state
        changeset = self.changeset_manager.get_changeset(changeset_id)
        if not changeset:
            raise ValueError(f"Changeset {changeset_id} not found")
            
        if changeset.state not in [ChangesetState.DRAFT, ChangesetState.PROPOSED]:
            raise ValueError(f"Cannot create proposal for changeset in {changeset.state.value} state")
        
        if required_approvals < 1:
            raise ValueError("Required approvals must be at least 1")
        
        proposal_id = str(uuid.uuid4())
        
        proposal = Proposal(
            id=proposal_id,
            changeset_id=changeset_id,
            title=title,
            description=description,
            status=ProposalStatus.OPEN,
            required_approvals=required_approvals,
            created_by=created_by,
            created_at=datetime.now(timezone.utc)
        )
        
        try:
            # Store proposal locally
            self._store_proposal_locally(proposal)
            
            # Update changeset state to PROPOSED
            self.changeset_manager.update_changeset_state(changeset_id, ChangesetState.PROPOSED)
            
            # Push proposal to S3
            self._push_proposal_to_s3(proposal)
            
            logger.info(f"Successfully created proposal {proposal_id} for changeset {changeset_id}")
            return proposal
            
        except Exception as e:
            logger.error(f"Failed to create proposal: {e}")
            # Attempt cleanup
            try:
                self.db.execute(text("DELETE FROM proposals WHERE id = ?"), (proposal_id,))
                self.db.commit()
            except:
                pass
            raise RuntimeError(f"Failed to create proposal: {e}")
    
    def vote_on_proposal(self, proposal_id: str, user_id: str, vote: str,
                        comment: Optional[str] = None) -> ProposalVote:
        """
        Cast vote on a proposal.
        
        Args:
            proposal_id: Proposal identifier
            user_id: Voter identifier
            vote: Vote value ('approve', 'reject', 'abstain')
            comment: Optional comment
            
        Returns:
            ProposalVote instance
            
        Raises:
            ValueError: If validation fails
            RuntimeError: If database operation fails
        """
        logger.info(f"User {user_id} voting '{vote}' on proposal {proposal_id}")
        
        if vote not in ['approve', 'reject', 'abstain']:
            raise ValueError("Vote must be 'approve', 'reject', or 'abstain'")
        
        # Check if proposal exists and is open
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")
            
        if proposal.status != ProposalStatus.OPEN:
            raise ValueError(f"Cannot vote on proposal with status {proposal.status.value}")
        
        # Check if user has already voted (for replacement)
        existing_vote = self.get_user_vote(proposal_id, user_id)
        
        # Create vote record
        proposal_vote = ProposalVote(
            proposal_id=proposal_id,
            user_id=user_id,
            vote=vote,
            comment=comment,
            voted_at=datetime.now(timezone.utc)
        )
        
        try:
            # Store vote locally (INSERT OR REPLACE for vote updates)
            self._store_vote_locally(proposal_vote, existing_vote is not None)
            
            # Push vote to S3
            self._push_vote_to_s3(proposal_vote)
            
            # Check if proposal should be automatically approved/rejected
            self._evaluate_proposal_status(proposal_id)
            
            if existing_vote:
                logger.info(f"Updated vote for user {user_id} on proposal {proposal_id}")
            else:
                logger.info(f"Recorded new vote for user {user_id} on proposal {proposal_id}")
            
            return proposal_vote
            
        except Exception as e:
            logger.error(f"Failed to record vote: {e}")
            self.db.rollback()
            raise RuntimeError(f"Failed to record vote: {e}")
    
    def get_proposal(self, proposal_id: str) -> Optional[Proposal]:
        """
        Retrieve proposal by ID.
        
        Args:
            proposal_id: Proposal identifier
            
        Returns:
            Proposal instance or None if not found
        """
        logger.debug(f"Retrieving proposal {proposal_id}")
        
        try:
            result = self.db.execute(
                text("SELECT * FROM proposals WHERE id = ?"),
                (proposal_id,)
            ).fetchone()
            
            if not result:
                logger.debug(f"Proposal {proposal_id} not found")
                return None
                
            return row_to_proposal(result)
            
        except Exception as e:
            logger.error(f"Failed to retrieve proposal {proposal_id}: {e}")
            return None
    
    def list_proposals(self, status: Optional[ProposalStatus] = None,
                      created_by: Optional[str] = None,
                      changeset_id: Optional[str] = None,
                      limit: int = 100) -> List[Proposal]:
        """
        List proposals with optional filtering.
        
        Args:
            status: Filter by proposal status
            created_by: Filter by creator ID
            changeset_id: Filter by changeset ID
            limit: Maximum number of results
            
        Returns:
            List of Proposal instances
        """
        logger.debug(f"Listing proposals (status={status}, created_by={created_by}, limit={limit})")
        
        try:
            query = "SELECT * FROM proposals WHERE 1=1"
            params = []
            
            if status:
                query += " AND status = ?"
                params.append(status.value)
                
            if created_by:
                query += " AND created_by = ?"
                params.append(created_by)
                
            if changeset_id:
                query += " AND changeset_id = ?"
                params.append(changeset_id)
                
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            results = self.db.execute(text(query), params).fetchall()
            proposals = [row_to_proposal(row) for row in results]
            
            logger.debug(f"Found {len(proposals)} proposals")
            return proposals
            
        except Exception as e:
            logger.error(f"Failed to list proposals: {e}")
            return []
    
    def get_proposal_votes(self, proposal_id: str) -> List[ProposalVote]:
        """
        Get all votes for a proposal.
        
        Args:
            proposal_id: Proposal identifier
            
        Returns:
            List of ProposalVote instances
        """
        logger.debug(f"Getting votes for proposal {proposal_id}")
        
        try:
            results = self.db.execute(
                text("""
                    SELECT * FROM proposal_votes 
                    WHERE proposal_id = ? 
                    ORDER BY voted_at
                """),
                (proposal_id,)
            ).fetchall()
            
            votes = [row_to_vote(row) for row in results]
            logger.debug(f"Found {len(votes)} votes for proposal {proposal_id}")
            return votes
            
        except Exception as e:
            logger.error(f"Failed to get votes for proposal {proposal_id}: {e}")
            return []
    
    def get_user_vote(self, proposal_id: str, user_id: str) -> Optional[ProposalVote]:
        """
        Get a specific user's vote on a proposal.
        
        Args:
            proposal_id: Proposal identifier
            user_id: User identifier
            
        Returns:
            ProposalVote instance or None if not found
        """
        try:
            result = self.db.execute(
                text("SELECT * FROM proposal_votes WHERE proposal_id = ? AND user_id = ?"),
                (proposal_id, user_id)
            ).fetchone()
            
            return row_to_vote(result) if result else None
            
        except Exception as e:
            logger.error(f"Failed to get user vote: {e}")
            return None
    
    def get_vote_summary(self, proposal_id: str) -> Dict[str, Any]:
        """
        Get vote summary for a proposal.
        
        Args:
            proposal_id: Proposal identifier
            
        Returns:
            Dictionary with vote counts and summary
        """
        try:
            votes = self.get_proposal_votes(proposal_id)
            
            summary = {
                "total_votes": len(votes),
                "approve_votes": len([v for v in votes if v.vote == 'approve']),
                "reject_votes": len([v for v in votes if v.vote == 'reject']),
                "abstain_votes": len([v for v in votes if v.vote == 'abstain']),
                "voters": [v.user_id for v in votes]
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to get vote summary for proposal {proposal_id}: {e}")
            return {"total_votes": 0, "approve_votes": 0, "reject_votes": 0, "abstain_votes": 0, "voters": []}
    
    def _evaluate_proposal_status(self, proposal_id: str):
        """
        Evaluate whether proposal should change status based on votes.
        
        Args:
            proposal_id: Proposal identifier
        """
        logger.debug(f"Evaluating status for proposal {proposal_id}")
        
        try:
            proposal = self.get_proposal(proposal_id)
            if not proposal or proposal.status != ProposalStatus.OPEN:
                return
            
            votes = self.get_proposal_votes(proposal_id)
            vote_summary = self.get_vote_summary(proposal_id)
            
            approve_votes = vote_summary["approve_votes"]
            reject_votes = vote_summary["reject_votes"]
            
            # Auto-approve if threshold met
            if approve_votes >= proposal.required_approvals:
                logger.info(f"Auto-approving proposal {proposal_id} ({approve_votes}/{proposal.required_approvals})")
                self._update_proposal_status(proposal_id, ProposalStatus.APPROVED)
                # Trigger auto-merge if configured
                self._auto_merge_if_enabled(proposal_id)
                
            # Auto-reject if more rejections than possible approvals
            # (This is a simple policy, could be made configurable)
            elif reject_votes > approve_votes and reject_votes >= proposal.required_approvals:
                logger.info(f"Auto-rejecting proposal {proposal_id} ({reject_votes} rejections)")
                self._update_proposal_status(proposal_id, ProposalStatus.REJECTED)
                
        except Exception as e:
            logger.error(f"Failed to evaluate proposal {proposal_id} status: {e}")
    
    def _update_proposal_status(self, proposal_id: str, new_status: ProposalStatus) -> bool:
        """
        Update proposal status.
        
        Args:
            proposal_id: Proposal identifier
            new_status: New status
            
        Returns:
            True if updated successfully
        """
        logger.info(f"Updating proposal {proposal_id} status to {new_status.value}")
        
        try:
            # If closing proposal, record close timestamp
            if new_status in [ProposalStatus.APPROVED, ProposalStatus.REJECTED, ProposalStatus.MERGED]:
                query = "UPDATE proposals SET status = ?, closed_at = ? WHERE id = ?"
                params = (new_status.value, datetime.now(timezone.utc).isoformat(), proposal_id)
            else:
                query = "UPDATE proposals SET status = ? WHERE id = ?"
                params = (new_status.value, proposal_id)
            
            cursor = self.db.execute(text(query), params)
            self.db.commit()
            
            if cursor.rowcount == 0:
                logger.warning(f"No proposal found with ID {proposal_id}")
                return False
                
            # Update changeset state if proposal approved
            if new_status == ProposalStatus.APPROVED:
                proposal = self.get_proposal(proposal_id)
                if proposal:
                    self.changeset_manager.update_changeset_state(
                        proposal.changeset_id, ChangesetState.APPROVED
                    )
            elif new_status == ProposalStatus.REJECTED:
                proposal = self.get_proposal(proposal_id)
                if proposal:
                    self.changeset_manager.update_changeset_state(
                        proposal.changeset_id, ChangesetState.REJECTED
                    )
                
            logger.info(f"Successfully updated proposal {proposal_id} status to {new_status.value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update proposal {proposal_id} status: {e}")
            self.db.rollback()
            return False
    
    def _auto_merge_if_enabled(self, proposal_id: str):
        """
        Trigger auto-merge for approved proposal if enabled.
        
        Args:
            proposal_id: Proposal identifier
        """
        # For Phase 3, we'll implement this as a placeholder
        # Auto-merge could be handled by CRDTMergeEngine
        logger.info(f"Auto-merge triggered for proposal {proposal_id} (placeholder)")
        # TODO: Integrate with CRDTMergeEngine once implemented
    
    def _store_proposal_locally(self, proposal: Proposal) -> None:
        """
        Store proposal in local SQLite database.
        
        Args:
            proposal: Proposal instance to store
        """
        logger.debug(f"Storing proposal {proposal.id} locally")
        
        query = """
        INSERT INTO proposals (
            id, changeset_id, title, description, status, required_approvals,
            created_by, created_at, closed_at, merge_commit_id, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        params = (
            proposal.id, proposal.changeset_id, proposal.title, proposal.description,
            proposal.status.value, proposal.required_approvals, proposal.created_by,
            proposal.created_at.isoformat(),
            proposal.closed_at.isoformat() if proposal.closed_at else None,
            proposal.merge_commit_id,
            json.dumps(proposal.metadata) if proposal.metadata else None
        )
        
        self.db.execute(text(query), params)
        self.db.commit()
        logger.debug(f"Stored proposal {proposal.id} in database")
    
    def _store_vote_locally(self, vote: ProposalVote, is_update: bool = False) -> None:
        """
        Store vote in local SQLite database.
        
        Args:
            vote: ProposalVote instance to store
            is_update: Whether this is an update to existing vote
        """
        logger.debug(f"Storing vote from {vote.user_id} for proposal {vote.proposal_id}")
        
        query = """
        INSERT OR REPLACE INTO proposal_votes (
            proposal_id, user_id, vote, comment, voted_at
        ) VALUES (?, ?, ?, ?, ?)
        """
        
        params = (
            vote.proposal_id, vote.user_id, vote.vote, vote.comment,
            vote.voted_at.isoformat()
        )
        
        self.db.execute(text(query), params)
        self.db.commit()
        logger.debug("Stored vote in database")
    
    def _push_proposal_to_s3(self, proposal: Proposal):
        """
        Push proposal metadata to S3.
        
        Args:
            proposal: Proposal instance to push
        """
        logger.debug(f"Pushing proposal {proposal.id} to S3")
        
        try:
            proposal_data = proposal.to_dict()
            
            s3_path = f"s3://{self.s3_sync.s3_config['bucket']}/proposals/{proposal.id}/metadata.parquet"
            
            self.s3_sync.parquet_writer.write_metadata(proposal_data, s3_path)
            logger.debug(f"Successfully pushed proposal {proposal.id} to S3")
            
        except Exception as e:
            logger.warning(f"Failed to push proposal {proposal.id} to S3: {e}")
            # Don't fail the operation if S3 push fails
    
    def _push_vote_to_s3(self, vote: ProposalVote):
        """
        Push vote to S3.
        
        Args:
            vote: ProposalVote instance to push
        """
        logger.debug("Pushing vote to S3")
        
        try:
            vote_data = vote.to_dict()
            
            s3_path = f"s3://{self.s3_sync.s3_config['bucket']}/proposals/{vote.proposal_id}/votes/vote_{vote.user_id}.parquet"
            
            self.s3_sync.parquet_writer.write_metadata(vote_data, s3_path)
            logger.debug("Successfully pushed vote to S3")
            
        except Exception as e:
            logger.warning(f"Failed to push vote to S3: {e}")
            # Don't fail the operation if S3 push fails