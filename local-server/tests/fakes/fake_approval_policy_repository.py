"""In-memory ApprovalPolicyRepository for domain tests."""

from __future__ import annotations

from typing import Optional

from domain.versioning.approval_policy import ApprovalPolicy


class FakeApprovalPolicyRepository:
    """Stores policies in a dict keyed by taxonomy id."""

    def __init__(self) -> None:
        self.policies: dict[str, ApprovalPolicy] = {}

    def get(self, taxonomy_id: str) -> Optional[ApprovalPolicy]:
        return self.policies.get(taxonomy_id)

    def save(self, policy: ApprovalPolicy) -> ApprovalPolicy:
        self.policies[policy.taxonomy_id] = policy
        return policy
