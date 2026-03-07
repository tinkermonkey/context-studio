# mypy: ignore-errors
"""
Proposal Management API Endpoints

This module implements the proposal management API endpoints for collaborative
review and voting workflows on changesets.

Endpoints:
- POST /api/proposals - Create proposal for changeset review
- GET /api/proposals - List proposals with optional filtering
- GET /api/proposals/{proposal_id} - Get proposal details
- POST /api/proposals/{proposal_id}/vote - Vote on proposal
- GET /api/proposals/{proposal_id}/votes - Get proposal votes
- GET /api/proposals/{proposal_id}/summary - Get vote summary
"""

from fastapi import APIRouter, HTTPException, Query, Depends, Path
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from services.proposal_manager import ProposalManager
from services.collaboration_models import ProposalStatus
from services.service_factory import ServiceFactory
from database.utils import get_db
from sqlalchemy.orm import Session
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/proposals", tags=["proposal_management"])


# Request/Response Models
class CreateProposalRequest(BaseModel):
    """Request model for creating a proposal."""
    changeset_id: str
    title: str
    description: str
    created_by: str
    required_approvals: int = 1


class VoteRequest(BaseModel):
    """Request model for voting on a proposal."""
    vote: str  # 'approve', 'reject', 'abstain'
    comment: Optional[str] = None


class ProposalVoteResponse(BaseModel):
    """Response model for proposal vote data."""
    proposal_id: str
    user_id: str
    vote: str
    comment: Optional[str]
    voted_at: datetime


class ProposalResponse(BaseModel):
    """Response model for proposal data."""
    id: str
    changeset_id: str
    title: str
    description: str
    status: str
    required_approvals: int
    created_by: str
    created_at: datetime
    closed_at: Optional[datetime]
    merge_commit_id: Optional[str]
    metadata: Optional[dict]


class ProposalListResponse(BaseModel):
    """Response model for proposal list."""
    proposals: List[ProposalResponse]
    total_count: int


class VoteSummaryResponse(BaseModel):
    """Response model for vote summary."""
    proposal_id: str
    total_votes: int
    approve_votes: int
    reject_votes: int
    abstain_votes: int
    voters: List[str]


class ProposalVotesResponse(BaseModel):
    """Response model for proposal votes list."""
    proposal_id: str
    votes: List[ProposalVoteResponse]
    total_votes: int


# Dependency injection
def get_proposal_manager(
    db: Session = Depends(get_db),
    service_factory: ServiceFactory = Depends()
) -> ProposalManager:
    """Get ProposalManager instance via service factory."""
    return service_factory.create_proposal_manager(db)


# API Endpoints
@router.post("", response_model=ProposalResponse)
def create_proposal(
    request: CreateProposalRequest,
    proposal_manager: ProposalManager = Depends(get_proposal_manager)
):
    """
    Create a new proposal for changeset review.

    Args:
        request: Proposal creation request
        proposal_manager: ProposalManager dependency

    Returns:
        Created proposal details

    Raises:
        HTTPException: If validation fails or creation fails
    """
    logger.info(f"Creating proposal for changeset {request.changeset_id} by {request.created_by}")  # noqa: E501

    try:
        proposal = proposal_manager.create_proposal(
            changeset_id=request.changeset_id,
            title=request.title,
            description=request.description,
            created_by=request.created_by,
            required_approvals=request.required_approvals
        )

        return ProposalResponse(
            id=proposal.id,
            changeset_id=proposal.changeset_id,
            title=proposal.title,
            description=proposal.description,
            status=proposal.status.value,
            required_approvals=proposal.required_approvals,
            created_by=proposal.created_by,
            created_at=proposal.created_at,
            closed_at=proposal.closed_at,
            merge_commit_id=proposal.merge_commit_id,
            metadata=proposal.metadata
        )

    except ValueError as e:
        logger.warning(f"Invalid proposal creation request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error(f"Failed to create proposal: {e}")
        raise HTTPException(status_code=500, detail="Failed to create proposal")  # noqa: E501


@router.get("", response_model=ProposalListResponse)
def list_proposals(
    status: Optional[str] = Query(None, description="Filter by proposal status"),  # noqa: E501
    created_by: Optional[str] = Query(None, description="Filter by creator ID"),  # noqa: E501
    changeset_id: Optional[str] = Query(None, description="Filter by changeset ID"),  # noqa: E501
    limit: int = Query(100, description="Maximum number of results", le=1000),
    proposal_manager: ProposalManager = Depends(get_proposal_manager)
):
    """
    List proposals with optional filtering.

    Args:
        status: Optional proposal status filter
        created_by: Optional creator ID filter
        changeset_id: Optional changeset ID filter
        limit: Maximum number of results
        proposal_manager: ProposalManager dependency

    Returns:
        List of proposals matching filters

    Raises:
        HTTPException: If invalid status provided
    """
    logger.debug(f"Listing proposals (status={status}, created_by={created_by}, changeset_id={changeset_id}, limit={limit})")  # noqa: E501

    try:
        # Validate status if provided
        proposal_status = None
        if status:
            try:
                proposal_status = ProposalStatus(status)
            except ValueError:
                valid_statuses = [s.value for s in ProposalStatus]
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status '{status}'. Valid statuses: {valid_statuses}"  # noqa: E501
                )

        proposals = proposal_manager.list_proposals(
            status=proposal_status,
            created_by=created_by,
            changeset_id=changeset_id,
            limit=limit
        )

        proposal_responses = []
        for proposal in proposals:
            proposal_responses.append(ProposalResponse(
                id=proposal.id,
                changeset_id=proposal.changeset_id,
                title=proposal.title,
                description=proposal.description,
                status=proposal.status.value,
                required_approvals=proposal.required_approvals,
                created_by=proposal.created_by,
                created_at=proposal.created_at,
                closed_at=proposal.closed_at,
                merge_commit_id=proposal.merge_commit_id,
                metadata=proposal.metadata
            ))

        return ProposalListResponse(
            proposals=proposal_responses,
            total_count=len(proposal_responses)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list proposals: {e}")
        raise HTTPException(status_code=500, detail="Failed to list proposals")


@router.get("/{proposal_id}", response_model=ProposalResponse)
def get_proposal(
    proposal_id: str = Path(..., description="Proposal ID"),
    proposal_manager: ProposalManager = Depends(get_proposal_manager)
):
    """
    Get proposal details by ID.

    Args:
        proposal_id: Proposal identifier
        proposal_manager: ProposalManager dependency

    Returns:
        Proposal details

    Raises:
        HTTPException: If proposal not found
    """
    logger.debug(f"Getting proposal {proposal_id}")

    try:
        proposal = proposal_manager.get_proposal(proposal_id)
        if not proposal:
            raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")  # noqa: E501

        return ProposalResponse(
            id=proposal.id,
            changeset_id=proposal.changeset_id,
            title=proposal.title,
            description=proposal.description,
            status=proposal.status.value,
            required_approvals=proposal.required_approvals,
            created_by=proposal.created_by,
            created_at=proposal.created_at,
            closed_at=proposal.closed_at,
            merge_commit_id=proposal.merge_commit_id,
            metadata=proposal.metadata
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get proposal {proposal_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get proposal")


@router.post("/{proposal_id}/vote", response_model=ProposalVoteResponse)
def vote_on_proposal(
    proposal_id: str = Path(..., description="Proposal ID"),
    request: VoteRequest = ...,
    user_id: str = Query(..., description="User ID of the voter"),
    proposal_manager: ProposalManager = Depends(get_proposal_manager)
):
    """
    Cast vote on a proposal.

    Args:
        proposal_id: Proposal identifier
        request: Vote request with vote and optional comment
        user_id: User ID of the voter
        proposal_manager: ProposalManager dependency

    Returns:
        Vote details

    Raises:
        HTTPException: If proposal not found or vote invalid
    """
    logger.info(f"User {user_id} voting '{request.vote}' on proposal {proposal_id}")  # noqa: E501

    try:
        vote = proposal_manager.vote_on_proposal(
            proposal_id=proposal_id,
            user_id=user_id,
            vote=request.vote,
            comment=request.comment
        )

        return ProposalVoteResponse(
            proposal_id=vote.proposal_id,
            user_id=vote.user_id,
            vote=vote.vote,
            comment=vote.comment,
            voted_at=vote.voted_at
        )

    except ValueError as e:
        logger.warning(f"Invalid vote request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error(f"Failed to record vote: {e}")
        raise HTTPException(status_code=500, detail="Failed to record vote")


@router.get("/{proposal_id}/votes", response_model=ProposalVotesResponse)
def get_proposal_votes(
    proposal_id: str = Path(..., description="Proposal ID"),
    proposal_manager: ProposalManager = Depends(get_proposal_manager)
):
    """
    Get all votes for a proposal.

    Args:
        proposal_id: Proposal identifier
        proposal_manager: ProposalManager dependency

    Returns:
        List of votes for the proposal

    Raises:
        HTTPException: If proposal not found
    """
    logger.debug(f"Getting votes for proposal {proposal_id}")

    try:
        # Check if proposal exists
        proposal = proposal_manager.get_proposal(proposal_id)
        if not proposal:
            raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")  # noqa: E501

        votes = proposal_manager.get_proposal_votes(proposal_id)

        vote_responses = []
        for vote in votes:
            vote_responses.append(ProposalVoteResponse(
                proposal_id=vote.proposal_id,
                user_id=vote.user_id,
                vote=vote.vote,
                comment=vote.comment,
                voted_at=vote.voted_at
            ))

        return ProposalVotesResponse(
            proposal_id=proposal_id,
            votes=vote_responses,
            total_votes=len(vote_responses)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get votes for proposal {proposal_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get proposal votes")  # noqa: E501


@router.get("/{proposal_id}/summary", response_model=VoteSummaryResponse)
def get_vote_summary(
    proposal_id: str = Path(..., description="Proposal ID"),
    proposal_manager: ProposalManager = Depends(get_proposal_manager)
):
    """
    Get vote summary for a proposal.

    Args:
        proposal_id: Proposal identifier
        proposal_manager: ProposalManager dependency

    Returns:
        Vote summary with counts

    Raises:
        HTTPException: If proposal not found
    """
    logger.debug(f"Getting vote summary for proposal {proposal_id}")

    try:
        # Check if proposal exists
        proposal = proposal_manager.get_proposal(proposal_id)
        if not proposal:
            raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")  # noqa: E501

        summary = proposal_manager.get_vote_summary(proposal_id)

        return VoteSummaryResponse(
            proposal_id=proposal_id,
            total_votes=summary["total_votes"],
            approve_votes=summary["approve_votes"],
            reject_votes=summary["reject_votes"],
            abstain_votes=summary["abstain_votes"],
            voters=summary["voters"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get vote summary for proposal {proposal_id}: {e}")  # noqa: E501
        raise HTTPException(status_code=500, detail="Failed to get vote summary")  # noqa: E501
