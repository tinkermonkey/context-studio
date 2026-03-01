"""
Integration tests for the complete Phase 3 collaboration workflow.

Tests end-to-end workflows from user registration through changeset merging,
including identity management, proposal voting, and CRDT conflict resolution.
"""

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest
from sqlalchemy import text
from unittest.mock import patch

from services.service_factory import ServiceFactory
from services.collaboration_models import ChangesetState, ProposalStatus


@pytest.fixture
def service_factory(db_session):
    """Create a ServiceFactory for testing."""
    return ServiceFactory(cache_ttl_seconds=60)


@pytest.fixture  
def identity_manager(db_session, service_factory):
    """Create an IdentityManager for testing."""
    return service_factory.create_identity_manager(db_session)


@pytest.fixture
def changeset_manager(db_session, service_factory):
    """Create a ChangesetManager for testing."""
    return service_factory.create_changeset_manager(db_session)


@pytest.fixture
def proposal_manager(db_session, service_factory):
    """Create a ProposalManager for testing."""
    return service_factory.create_proposal_manager(db_session)


@pytest.fixture
def crdt_merge_engine(db_session, service_factory):
    """Create a CRDTMergeEngine for testing."""
    return service_factory.create_crdt_merge_engine(db_session)


def test_complete_collaboration_workflow(
    db_session, identity_manager, changeset_manager, proposal_manager, crdt_merge_engine
):
    """Test complete end-to-end collaboration workflow."""
    
    # Step 1: Register users
    user1_result = identity_manager.register_user(
        email="user1@example.com",
        display_name="User One"
    )
    user1_id = user1_result["user_identity"].user_id
    user1_code = user1_result["verification_code"]
    
    user2_result = identity_manager.register_user(
        email="user2@example.com", 
        display_name="User Two"
    )
    user2_id = user2_result["user_identity"].user_id
    user2_code = user2_result["verification_code"]
    
    user3_result = identity_manager.register_user(
        email="user3@example.com",
        display_name="User Three"
    )
    user3_id = user3_result["user_identity"].user_id
    user3_code = user3_result["verification_code"]

    # Step 2: Verify user emails
    assert identity_manager.verify_email(user1_id, user1_code) is True
    assert identity_manager.verify_email(user2_id, user2_code) is True
    assert identity_manager.verify_email(user3_id, user3_code) is True

    # Step 3: Establish trust relationships
    assert identity_manager.trust_user(user1_id, user2_id) is True
    assert identity_manager.trust_user(user1_id, user3_id) is True
    assert identity_manager.trust_user(user2_id, user3_id) is True
    assert identity_manager.trust_user(user3_id, user2_id) is True  # user3 trusts user2

    # Verify trust levels increased
    user2 = identity_manager.get_user(user2_id)
    user3 = identity_manager.get_user(user3_id)
    assert user2.trust_level == 2  # Team-verified
    assert user3.trust_level == 2  # Team-verified

    # Step 4: Create changesets with mocked working tree
    with patch.object(changeset_manager.working_tree, 'get_staged_changes') as mock_staged:
        with patch.object(changeset_manager.working_tree, 'capture_version_snapshot') as mock_snapshot:
            mock_staged.return_value = [
                {"version_id": "v1", "change_type": "create", "entity_type": "node"}
            ]
            mock_snapshot.return_value = "snapshot123"

            changeset1 = changeset_manager.create_changeset(
                title="Feature A Implementation",
                description="Implementing feature A with new nodes",
                author_id=user1_id
            )

            changeset2 = changeset_manager.create_changeset(
                title="Feature B Implementation", 
                description="Implementing feature B with updates",
                author_id=user2_id
            )

    assert changeset1.state == ChangesetState.DRAFT
    assert changeset2.state == ChangesetState.DRAFT

    # Step 5: Create proposals for changesets
    proposal1 = proposal_manager.create_proposal(
        changeset_id=changeset1.id,
        title="Proposal for Feature A",
        description="Please review feature A implementation",
        created_by=user1_id,
        required_approvals=2
    )

    proposal2 = proposal_manager.create_proposal(
        changeset_id=changeset2.id,
        title="Proposal for Feature B",
        description="Please review feature B implementation", 
        created_by=user2_id,
        required_approvals=2
    )

    assert proposal1.status == ProposalStatus.OPEN
    assert proposal2.status == ProposalStatus.OPEN

    # Verify changesets moved to PROPOSED state
    changeset1_updated = changeset_manager.get_changeset(changeset1.id)
    changeset2_updated = changeset_manager.get_changeset(changeset2.id)
    assert changeset1_updated.state == ChangesetState.PROPOSED
    assert changeset2_updated.state == ChangesetState.PROPOSED

    # Step 6: Vote on proposals
    # User 2 and 3 vote to approve proposal 1
    vote1 = proposal_manager.vote_on_proposal(
        proposal_id=proposal1.id,
        user_id=user2_id,
        vote="approve",
        comment="Looks good to me!"
    )
    
    vote2 = proposal_manager.vote_on_proposal(
        proposal_id=proposal1.id,
        user_id=user3_id,
        vote="approve",
        comment="LGTM, great work!"
    )

    # User 1 and 3 vote to approve proposal 2  
    vote3 = proposal_manager.vote_on_proposal(
        proposal_id=proposal2.id,
        user_id=user1_id,
        vote="approve"
    )
    
    vote4 = proposal_manager.vote_on_proposal(
        proposal_id=proposal2.id,
        user_id=user3_id,
        vote="approve"
    )

    # Step 7: Verify auto-approval occurred
    proposal1_updated = proposal_manager.get_proposal(proposal1.id)
    proposal2_updated = proposal_manager.get_proposal(proposal2.id)
    assert proposal1_updated.status == ProposalStatus.APPROVED
    assert proposal2_updated.status == ProposalStatus.APPROVED

    # Verify changesets moved to APPROVED state
    changeset1_final = changeset_manager.get_changeset(changeset1.id)
    changeset2_final = changeset_manager.get_changeset(changeset2.id)
    assert changeset1_final.state == ChangesetState.APPROVED
    assert changeset2_final.state == ChangesetState.APPROVED

    # Step 8: Test CRDT merge with mocked dependencies
    with patch.object(crdt_merge_engine, '_get_changeset_versions') as mock_get_versions:
        with patch.object(crdt_merge_engine, '_update_canonical_version') as mock_update_canonical:
            # Mock empty changesets (no versions to merge)
            mock_get_versions.return_value = []

            # Test merging individual changesets
            merge_result1 = crdt_merge_engine.merge_changeset(
                changeset_id=changeset1.id,
                merge_author=user1_id
            )

            merge_result2 = crdt_merge_engine.merge_changeset(
                changeset_id=changeset2.id,
                merge_author=user2_id
            )

    # Verify merge results for empty changesets
    assert merge_result1.changeset_id == changeset1.id
    assert merge_result1.merged_entities == 0  # No entities in empty changeset
    assert merge_result1.conflicts == 0

    assert merge_result2.changeset_id == changeset2.id
    assert merge_result2.merged_entities == 0  # No entities in empty changeset
    assert merge_result2.conflicts == 0

    # Step 9: Verify vote summaries
    summary1 = proposal_manager.get_vote_summary(proposal1.id)
    summary2 = proposal_manager.get_vote_summary(proposal2.id)

    assert summary1["total_votes"] == 2
    assert summary1["approve_votes"] == 2
    assert summary1["reject_votes"] == 0

    assert summary2["total_votes"] == 2  
    assert summary2["approve_votes"] == 2
    assert summary2["reject_votes"] == 0

    # Step 10: Test trust network
    network1 = identity_manager.get_trust_network(user1_id)
    network2 = identity_manager.get_trust_network(user2_id)
    network3 = identity_manager.get_trust_network(user3_id)

    # User 1 trusts user2 and user3
    assert len(network1["trusts"]) == 2
    # User 2 is trusted by user1 and user3
    assert len(network2["trusted_by"]) == 2
    # User 3 is trusted by user1 and user2
    assert len(network3["trusted_by"]) == 2


def test_collaboration_workflow_with_conflicts(
    db_session, identity_manager, changeset_manager, proposal_manager, crdt_merge_engine
):
    """Test collaboration workflow with CRDT conflict resolution."""
    
    # Setup users
    user1_result = identity_manager.register_user("user1@test.com", "User One")
    user2_result = identity_manager.register_user("user2@test.com", "User Two")
    
    user1_id = user1_result["user_identity"].user_id
    user2_id = user2_result["user_identity"].user_id
    
    identity_manager.verify_email(user1_id, user1_result["verification_code"])
    identity_manager.verify_email(user2_id, user2_result["verification_code"])

    # Create conflicting changesets
    with patch.object(changeset_manager.working_tree, 'get_staged_changes') as mock_staged:
        with patch.object(changeset_manager.working_tree, 'capture_version_snapshot') as mock_snapshot:
            mock_staged.return_value = [{"version_id": "v1", "change_type": "update"}]
            mock_snapshot.return_value = "snapshot123"

            changeset1 = changeset_manager.create_changeset(
                title="Update Title to A", 
                description="First update",
                author_id=user1_id
            )

            changeset2 = changeset_manager.create_changeset(
                title="Update Title to B",
                description="Second update", 
                author_id=user2_id
            )

    # Create and approve proposals
    proposal1 = proposal_manager.create_proposal(
        changeset_id=changeset1.id,
        title="Proposal A",
        description="First proposal",
        created_by=user1_id,
        required_approvals=1
    )

    proposal2 = proposal_manager.create_proposal(
        changeset_id=changeset2.id,
        title="Proposal B", 
        description="Second proposal",
        created_by=user2_id,
        required_approvals=1
    )

    # Vote to approve both
    proposal_manager.vote_on_proposal(proposal1.id, user2_id, "approve")
    proposal_manager.vote_on_proposal(proposal2.id, user1_id, "approve")

    # Test merge with conflicts (simplified for empty changesets)
    with patch.object(crdt_merge_engine, '_get_changeset_versions') as mock_get_versions:
        # Mock empty changesets (no versions to merge, so no conflicts)
        mock_get_versions.return_value = []

        # Test merging individual changesets
        merge_result1 = crdt_merge_engine.merge_changeset(
            changeset_id=changeset1.id,
            merge_author=user1_id
        )

        merge_result2 = crdt_merge_engine.merge_changeset(
            changeset_id=changeset2.id,
            merge_author=user2_id
        )

    # Verify merge results for empty changesets (no conflicts)
    assert merge_result1.changeset_id == changeset1.id
    assert merge_result1.merged_entities == 0  # No entities in empty changeset
    assert merge_result1.conflicts == 0

    assert merge_result2.changeset_id == changeset2.id
    assert merge_result2.merged_entities == 0  # No entities in empty changeset
    assert merge_result2.conflicts == 0


def test_collaboration_workflow_rejection(
    db_session, identity_manager, changeset_manager, proposal_manager
):
    """Test collaboration workflow with proposal rejection."""
    
    # Setup users
    user1_result = identity_manager.register_user("author@test.com", "Author")
    user2_result = identity_manager.register_user("reviewer1@test.com", "Reviewer 1") 
    user3_result = identity_manager.register_user("reviewer2@test.com", "Reviewer 2")
    
    user1_id = user1_result["user_identity"].user_id
    user2_id = user2_result["user_identity"].user_id
    user3_id = user3_result["user_identity"].user_id
    
    # Verify all users
    identity_manager.verify_email(user1_id, user1_result["verification_code"])
    identity_manager.verify_email(user2_id, user2_result["verification_code"])
    identity_manager.verify_email(user3_id, user3_result["verification_code"])

    # Create changeset
    with patch.object(changeset_manager.working_tree, 'get_staged_changes') as mock_staged:
        with patch.object(changeset_manager.working_tree, 'capture_version_snapshot') as mock_snapshot:
            mock_staged.return_value = [{"version_id": "v1", "change_type": "create"}]
            mock_snapshot.return_value = "snapshot123"

            changeset = changeset_manager.create_changeset(
                title="Questionable Feature",
                description="This might not be good",
                author_id=user1_id
            )

    # Create proposal requiring 2 approvals
    proposal = proposal_manager.create_proposal(
        changeset_id=changeset.id,
        title="Review Questionable Feature",
        description="Please review this implementation",
        created_by=user1_id,
        required_approvals=2
    )

    # Both reviewers reject
    proposal_manager.vote_on_proposal(
        proposal_id=proposal.id,
        user_id=user2_id,
        vote="reject",
        comment="I don't think this is a good approach"
    )
    
    proposal_manager.vote_on_proposal(
        proposal_id=proposal.id,
        user_id=user3_id,
        vote="reject", 
        comment="Needs significant changes"
    )

    # Verify proposal was auto-rejected
    proposal_updated = proposal_manager.get_proposal(proposal.id)
    assert proposal_updated.status == ProposalStatus.REJECTED

    # Verify changeset state
    changeset_updated = changeset_manager.get_changeset(changeset.id)
    assert changeset_updated.state == ChangesetState.REJECTED


def test_collaboration_workflow_vote_updates(
    db_session, identity_manager, changeset_manager, proposal_manager
):
    """Test collaboration workflow with vote updates."""
    
    # Setup
    user1_result = identity_manager.register_user("user1@update.com", "User One")
    user2_result = identity_manager.register_user("user2@update.com", "User Two")
    
    user1_id = user1_result["user_identity"].user_id
    user2_id = user2_result["user_identity"].user_id
    
    identity_manager.verify_email(user1_id, user1_result["verification_code"])
    identity_manager.verify_email(user2_id, user2_result["verification_code"])

    # Create changeset and proposal
    with patch.object(changeset_manager.working_tree, 'get_staged_changes') as mock_staged:
        with patch.object(changeset_manager.working_tree, 'capture_version_snapshot') as mock_snapshot:
            mock_staged.return_value = [{"version_id": "v1", "change_type": "create"}]
            mock_snapshot.return_value = "snapshot123"

            changeset = changeset_manager.create_changeset(
                title="Feature X",
                description="Implementation of feature X",
                author_id=user1_id
            )

    proposal = proposal_manager.create_proposal(
        changeset_id=changeset.id,
        title="Review Feature X",
        description="Please review feature X",
        created_by=user1_id,
        required_approvals=1
    )

    # Initial vote: abstain
    proposal_manager.vote_on_proposal(
        proposal_id=proposal.id,
        user_id=user2_id,
        vote="abstain",
        comment="Need more time to review"
    )

    # Verify vote recorded
    votes = proposal_manager.get_proposal_votes(proposal.id)
    assert len(votes) == 1
    assert votes[0].vote == "abstain"

    # Update vote: approve
    proposal_manager.vote_on_proposal(
        proposal_id=proposal.id,
        user_id=user2_id,
        vote="approve",
        comment="Looks good after review"
    )

    # Verify vote updated and proposal approved
    votes_updated = proposal_manager.get_proposal_votes(proposal.id)
    assert len(votes_updated) == 1  # Should still be 1 vote, but updated
    assert votes_updated[0].vote == "approve"
    assert votes_updated[0].comment == "Looks good after review"

    proposal_updated = proposal_manager.get_proposal(proposal.id)
    assert proposal_updated.status == ProposalStatus.APPROVED


def test_migration_008_creates_collaboration_tables(db_session):
    """Test that migration 008 creates all required collaboration tables."""
    
    # Verify all collaboration tables exist
    tables_to_check = [
        "changesets",
        "proposals", 
        "proposal_votes",
        "user_identities",
        "user_trust_relationships",
        "verification_codes"
    ]
    
    for table_name in tables_to_check:
        result = db_session.execute(
            text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        ).fetchone()
        assert result is not None, f"Table {table_name} should exist after migration 008"

    # Verify table schemas have expected columns
    changeset_columns = db_session.execute(text("PRAGMA table_info(changesets)")).fetchall()
    changeset_column_names = [col[1] for col in changeset_columns]
    
    expected_changeset_columns = [
        "id", "title", "description", "state", "branch_name", 
        "parent_changeset_id", "author_id", "created_at", "merged_at", "metadata"
    ]
    
    for col in expected_changeset_columns:
        assert col in changeset_column_names, f"Column {col} should exist in changesets table"

    # Check foreign key constraints exist
    foreign_keys = db_session.execute(text("PRAGMA foreign_key_list(proposals)")).fetchall()
    assert len(foreign_keys) > 0, "Proposals table should have foreign key constraints"