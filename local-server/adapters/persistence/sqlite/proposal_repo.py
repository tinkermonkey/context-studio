"""
SQLite repository for change proposals (ChangeProposalRepository port).

A proposal is stored as a ``batch_runs`` row (run_type ``proposal``) joined to
``change_proposals``, with its operations in ``proposal_operations``. Using the
batch run id as the proposal id is what lets change events of applied
operations be tagged with it and reverted with the run.
"""

from __future__ import annotations

from datetime import timezone
from typing import Optional, Sequence

from sqlalchemy.orm import Session, sessionmaker

from adapters.persistence.sqlite.models import BatchRun, ChangeProposalRun, ProposalOperation
from domain.versioning.proposals import (
    ChangeProposal,
    ChangeScope,
    OperationKind,
    OperationStatus,
    OperationType,
    ProposalSource,
    ProposalStatus,
    ProposedOperation,
)


class SQLiteChangeProposalRepository:
    """ChangeProposalRepository over local.db."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def create(self, proposal: ChangeProposal) -> ChangeProposal:
        with self._session_factory() as session:
            if session.get(BatchRun, proposal.id) is not None:
                raise ValueError(f"Proposal {proposal.id} already exists")
            session.add(
                ChangeProposalRun(
                    id=proposal.id,
                    # SQLite keeps the wall-clock time and drops the offset; store UTC.
                    created_at=proposal.created_at.astimezone(timezone.utc),
                    status=proposal.status.value,
                    affected_entity_ids=[],
                    taxonomy_id=proposal.taxonomy_id,
                    title=proposal.title,
                    rationale=proposal.rationale,
                    source=proposal.source.value,
                    source_detail=proposal.source_detail,
                )
            )
            session.flush()
            for operation in proposal.operations:
                session.add(_operation_to_orm(proposal.id, operation))
            session.commit()
        return self.get(proposal.id)  # type: ignore[return-value]

    def get(self, proposal_id: str) -> Optional[ChangeProposal]:
        with self._session_factory() as session:
            run = session.get(ChangeProposalRun, proposal_id)
            if run is None:
                return None
            return _to_domain(run, _operations(session, [proposal_id]).get(proposal_id, []))

    def list_proposals(
        self,
        taxonomy_id: Optional[str] = None,
        status: Optional[ProposalStatus] = None,
        source: Optional[ProposalSource] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ChangeProposal]:
        with self._session_factory() as session:
            runs = (
                _filtered(session, taxonomy_id, status, source)
                .order_by(ChangeProposalRun.created_at.desc(), ChangeProposalRun.id.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )
            operations = _operations(session, [r.id for r in runs])
            return [_to_domain(run, operations.get(run.id, [])) for run in runs]

    def count_proposals(
        self,
        taxonomy_id: Optional[str] = None,
        status: Optional[ProposalStatus] = None,
        source: Optional[ProposalSource] = None,
    ) -> int:
        with self._session_factory() as session:
            return _filtered(session, taxonomy_id, status, source).count()

    def save_operations(self, proposal_id: str, operations: Sequence[ProposedOperation]) -> None:
        with self._session_factory() as session:
            if session.get(ChangeProposalRun, proposal_id) is None:
                raise ValueError(f"No proposal {proposal_id}")
            rows = {
                row.id: row
                for row in session.query(ProposalOperation).filter(
                    ProposalOperation.proposal_id == proposal_id,
                    ProposalOperation.id.in_([o.id for o in operations]),
                )
            }
            missing = [o.id for o in operations if o.id not in rows]
            if missing:
                raise ValueError(f"Proposal {proposal_id} has no operations {missing}")
            for operation in operations:
                row = rows[operation.id]
                row.status = operation.status.value  # type: ignore[assignment]
                row.result_entity_id = operation.result_entity_id  # type: ignore[assignment]
                row.reason = operation.reason  # type: ignore[assignment]
                row.scope = operation.scope.value  # type: ignore[assignment]
                row.applied_fields = operation.applied_fields  # type: ignore[assignment]
            session.commit()

    def set_status(self, proposal_id: str, status: ProposalStatus) -> None:
        with self._session_factory() as session:
            run = session.get(ChangeProposalRun, proposal_id)
            if run is None:
                raise ValueError(f"No proposal {proposal_id}")
            run.status = status.value  # type: ignore[assignment]
            session.commit()


def _filtered(
    session: Session,
    taxonomy_id: Optional[str],
    status: Optional[ProposalStatus],
    source: Optional[ProposalSource],
):
    query = session.query(ChangeProposalRun)
    if taxonomy_id is not None:
        query = query.filter(ChangeProposalRun.taxonomy_id == taxonomy_id)
    if status is not None:
        query = query.filter(ChangeProposalRun.status == status.value)
    if source is not None:
        query = query.filter(ChangeProposalRun.source == source.value)
    return query


def _operations(session: Session, proposal_ids: list[str]) -> dict[str, list[ProposedOperation]]:
    found: dict[str, list[ProposedOperation]] = {}
    if not proposal_ids:
        return found
    rows = (
        session.query(ProposalOperation)
        .filter(ProposalOperation.proposal_id.in_(proposal_ids))
        .order_by(ProposalOperation.proposal_id, ProposalOperation.seq)
    )
    for row in rows:
        found.setdefault(row.proposal_id, []).append(_operation_to_domain(row))  # type: ignore[arg-type]
    return found


def _operation_to_orm(proposal_id: str, operation: ProposedOperation) -> ProposalOperation:
    return ProposalOperation(
        id=operation.id,
        proposal_id=proposal_id,
        seq=operation.seq,
        op=operation.op.value,
        kind=operation.kind.value,
        target_id=operation.target_id,
        ref=operation.ref,
        fields=dict(operation.fields),
        base=dict(operation.base),
        rationale=operation.rationale,
        evidence=list(operation.evidence),
        probability=operation.probability,
        scope=operation.scope.value,
        status=operation.status.value,
        result_entity_id=operation.result_entity_id,
        reason=operation.reason,
        applied_fields=operation.applied_fields,
    )


def _operation_to_domain(row: ProposalOperation) -> ProposedOperation:
    return ProposedOperation(
        id=row.id,  # type: ignore[arg-type]
        seq=row.seq,  # type: ignore[arg-type]
        op=OperationType(row.op),
        kind=OperationKind(row.kind),
        target_id=row.target_id,  # type: ignore[arg-type]
        ref=row.ref,  # type: ignore[arg-type]
        fields=dict(row.fields or {}),
        base=dict(row.base or {}),
        rationale=row.rationale,  # type: ignore[arg-type]
        evidence=list(row.evidence or []),
        probability=row.probability,  # type: ignore[arg-type]
        scope=ChangeScope(row.scope),
        status=OperationStatus(row.status),
        result_entity_id=row.result_entity_id,  # type: ignore[arg-type]
        reason=row.reason,  # type: ignore[arg-type]
        applied_fields=dict(row.applied_fields) if row.applied_fields is not None else None,
    )


def _to_domain(run: ChangeProposalRun, operations: list[ProposedOperation]) -> ChangeProposal:
    created_at = run.created_at
    if created_at is not None and created_at.tzinfo is None:  # stored as UTC, zone dropped
        created_at = created_at.replace(tzinfo=timezone.utc)
    return ChangeProposal(
        id=run.id,  # type: ignore[arg-type]
        taxonomy_id=run.taxonomy_id,  # type: ignore[arg-type]
        title=run.title,  # type: ignore[arg-type]
        rationale=run.rationale,  # type: ignore[arg-type]
        source=ProposalSource(run.source),
        source_detail=run.source_detail,  # type: ignore[arg-type]
        created_at=created_at,  # type: ignore[arg-type]
        status=ProposalStatus(run.status),
        operations=operations,
    )
