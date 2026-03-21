"""
Phase 3 Collaboration Data Models

Data models for the collaborative change management system including changesets,
proposals, voting, and identity management.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import json


class ChangesetState(Enum):
    """States for changeset lifecycle."""

    DRAFT = "DRAFT"
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    MERGED = "MERGED"
    REJECTED = "REJECTED"


class ProposalStatus(Enum):
    """Status for proposal lifecycle."""

    OPEN = "open"
    APPROVED = "approved"
    REJECTED = "rejected"
    MERGED = "merged"


class CRDTConflictError(Exception):
    """Exception raised when CRDT merge conflicts cannot be automatically resolved."""

    pass


@dataclass
class Changeset:
    """A collection of related changes bundled together for collaboration."""

    id: str
    title: str
    description: str
    state: ChangesetState
    branch_name: Optional[str]
    parent_changeset_id: Optional[str]
    author_id: str
    created_at: datetime
    merged_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert changeset to dictionary for serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "state": self.state.value,
            "branch_name": self.branch_name,
            "parent_changeset_id": self.parent_changeset_id,
            "author_id": self.author_id,
            "created_at": self.created_at.isoformat(),
            "merged_at": self.merged_at.isoformat() if self.merged_at else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Changeset":
        """Create changeset from dictionary."""
        return cls(
            id=data["id"],
            title=data["title"],
            description=data["description"],
            state=ChangesetState(data["state"]),
            branch_name=data.get("branch_name"),
            parent_changeset_id=data.get("parent_changeset_id"),
            author_id=data["author_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            merged_at=(
                datetime.fromisoformat(data["merged_at"])
                if data.get("merged_at")
                else None
            ),
            metadata=data.get("metadata"),
        )


@dataclass
class ChangesetVersion:
    """A specific version of entities included in a changeset."""

    changeset_id: str
    version_ids: List[str]  # List of entity_version IDs included
    summary: Dict[str, Any]  # Summary statistics
    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert changeset version to dictionary."""
        return {
            "changeset_id": self.changeset_id,
            "version_ids": self.version_ids,
            "summary": self.summary,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class Proposal:
    """A proposal for reviewing and approving a changeset."""

    id: str
    changeset_id: str
    title: str
    description: str
    status: ProposalStatus
    required_approvals: int
    created_by: str
    created_at: datetime
    closed_at: Optional[datetime] = None
    merge_commit_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert proposal to dictionary for serialization."""
        return {
            "id": self.id,
            "changeset_id": self.changeset_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "required_approvals": self.required_approvals,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "merge_commit_id": self.merge_commit_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Proposal":
        """Create proposal from dictionary."""
        return cls(
            id=data["id"],
            changeset_id=data["changeset_id"],
            title=data["title"],
            description=data["description"],
            status=ProposalStatus(data["status"]),
            required_approvals=data["required_approvals"],
            created_by=data["created_by"],
            created_at=datetime.fromisoformat(data["created_at"]),
            closed_at=(
                datetime.fromisoformat(data["closed_at"])
                if data.get("closed_at")
                else None
            ),
            merge_commit_id=data.get("merge_commit_id"),
            metadata=data.get("metadata"),
        )


@dataclass
class ProposalVote:
    """A vote cast on a proposal."""

    proposal_id: str
    user_id: str
    vote: str  # 'approve', 'reject', 'abstain'
    comment: Optional[str]
    voted_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert vote to dictionary for serialization."""
        return {
            "proposal_id": self.proposal_id,
            "user_id": self.user_id,
            "vote": self.vote,
            "comment": self.comment,
            "voted_at": self.voted_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProposalVote":
        """Create vote from dictionary."""
        return cls(
            proposal_id=data["proposal_id"],
            user_id=data["user_id"],
            vote=data["vote"],
            comment=data.get("comment"),
            voted_at=datetime.fromisoformat(data["voted_at"]),
        )


@dataclass
class UserIdentity:
    """User identity with trust levels for collaboration."""

    user_id: str
    email: str
    display_name: str
    public_key: Optional[str]
    verified: bool
    trust_level: int  # 0=unverified, 1=email verified, 2=team verified
    created_at: datetime
    verified_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert user identity to dictionary for serialization."""
        return {
            "user_id": self.user_id,
            "email": self.email,
            "display_name": self.display_name,
            "public_key": self.public_key,
            "verified": self.verified,
            "trust_level": self.trust_level,
            "created_at": self.created_at.isoformat(),
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserIdentity":
        """Create user identity from dictionary."""
        return cls(
            user_id=data["user_id"],
            email=data["email"],
            display_name=data["display_name"],
            public_key=data.get("public_key"),
            verified=data["verified"],
            trust_level=data["trust_level"],
            created_at=datetime.fromisoformat(data["created_at"]),
            verified_at=(
                datetime.fromisoformat(data["verified_at"])
                if data.get("verified_at")
                else None
            ),
        )


# Helper functions for database row conversion
def row_to_changeset(row) -> Changeset:
    """Convert database row to Changeset object."""
    return Changeset(
        id=row[0],  # id
        title=row[1],  # title
        description=row[2],  # description
        state=ChangesetState(row[3]),  # state
        branch_name=row[4],  # branch_name
        parent_changeset_id=row[5],  # parent_changeset_id
        author_id=row[6],  # author_id
        created_at=datetime.fromisoformat(row[7]),  # created_at
        merged_at=datetime.fromisoformat(row[8]) if row[8] else None,  # merged_at
        metadata=json.loads(row[9]) if row[9] else None,  # metadata
    )


def row_to_proposal(row) -> Proposal:
    """Convert database row to Proposal object."""
    return Proposal(
        id=row[0],  # id
        changeset_id=row[1],  # changeset_id
        title=row[2],  # title
        description=row[3],  # description
        status=ProposalStatus(row[4]),  # status
        required_approvals=row[5],  # required_approvals
        created_by=row[6],  # created_by
        created_at=datetime.fromisoformat(row[7]),  # created_at
        closed_at=datetime.fromisoformat(row[8]) if row[8] else None,  # closed_at
        merge_commit_id=row[9],  # merge_commit_id
        metadata=json.loads(row[10]) if row[10] else None,  # metadata
    )


def row_to_vote(row) -> ProposalVote:
    """Convert database row to ProposalVote object."""
    return ProposalVote(
        proposal_id=row[0],  # proposal_id
        user_id=row[1],  # user_id
        vote=row[2],  # vote
        comment=row[3],  # comment
        voted_at=datetime.fromisoformat(row[4]),  # voted_at
    )


def row_to_identity(row) -> UserIdentity:
    """Convert database row to UserIdentity object."""
    return UserIdentity(
        user_id=row[0],  # user_id
        email=row[1],  # email
        display_name=row[2],  # display_name
        public_key=row[3],  # public_key
        verified=bool(row[4]),  # verified
        trust_level=row[5],  # trust_level
        created_at=datetime.fromisoformat(row[6]),  # created_at
        verified_at=datetime.fromisoformat(row[7]) if row[7] else None,  # verified_at
    )
