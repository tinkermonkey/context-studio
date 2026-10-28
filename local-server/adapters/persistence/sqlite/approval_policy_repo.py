"""SQLite repository for approval policies (ApprovalPolicyRepository port)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.models import ApprovalPolicyRecord
from domain.versioning.approval_policy import ApprovalPolicy


class SQLiteApprovalPolicyRepository:
    """ApprovalPolicyRepository over local.db; one row per taxonomy."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def get(self, taxonomy_id: str) -> Optional[ApprovalPolicy]:
        with self._session_factory() as session:
            row = session.get(ApprovalPolicyRecord, str(taxonomy_id))
            if row is None:
                return None
            return ApprovalPolicy.from_rules(row.taxonomy_id, dict(row.rules or {}))  # type: ignore[arg-type]

    def save(self, policy: ApprovalPolicy) -> ApprovalPolicy:
        with self._session_factory() as session:
            row = session.get(ApprovalPolicyRecord, str(policy.taxonomy_id))
            if row is None:
                session.add(
                    ApprovalPolicyRecord(taxonomy_id=policy.taxonomy_id, rules=policy.to_rules())
                )
            else:
                row.rules = policy.to_rules()  # type: ignore[assignment]
            session.commit()
        return self.get(policy.taxonomy_id)  # type: ignore[return-value]
