"""
SQLite repository for change proposals (ChangeProposalRepository port).

A proposal is stored as a ``batch_runs`` row (run_type ``proposal``) joined to
``change_proposals``, with its operations in ``proposal_operations``. Using the
batch run id as the proposal id is what lets change events of applied
operations be tagged with it and reverted with the run.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import and_, func, not_, or_
from sqlalchemy.orm import Session, sessionmaker

from adapters.persistence.sqlite.models import (
    BatchRun,
    ChangeEvent,
    ChangeProposalRun,
    ProposalDecisionRecord,
    ProposalOperation,
)
from domain.ontology.value_objects import SourceRevision
from domain.versioning.bundle_import import MATCHED_PREFIX, SUPERSEDED_PREFIX
from domain.versioning.gold import (
    DECIDED_BY_UNKNOWN,
    DecisionFilter,
    DecisionKind,
    ProposalDecision,
    decision_of,
)
from domain.versioning.proposal_service import REVERTED_REASON
from domain.versioning.proposals import (
    ChangeProposal,
    ChangeScope,
    InUseResolution,
    Landing,
    OperationKind,
    OperationStatus,
    OperationType,
    ProposalSource,
    ProposalStatus,
    ProposedOperation,
    TypeChange,
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
                    source_revision=(
                        proposal.source_revision.to_dict() if proposal.source_revision else None
                    ),
                    landed=proposal.landed.to_dict() if proposal.landed else None,
                    client_metadata=proposal.client_metadata,
                    dataset_id=proposal.dataset_id,
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
        landed: Optional[bool] = None,
    ) -> list[ChangeProposal]:
        with self._session_factory() as session:
            runs = (
                _filtered(session, taxonomy_id, status, source, landed)
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
        landed: Optional[bool] = None,
    ) -> int:
        with self._session_factory() as session:
            return _filtered(session, taxonomy_id, status, source, landed).count()

    def operation_counts(self, proposal_ids: Sequence[str]) -> dict[str, int]:
        if not proposal_ids:
            return {}
        with self._session_factory() as session:
            rows = (
                session.query(ProposalOperation.proposal_id, func.count(ProposalOperation.id))
                .filter(ProposalOperation.proposal_id.in_(list(proposal_ids)))
                .group_by(ProposalOperation.proposal_id)
                .all()
            )
            return {proposal_id: count for proposal_id, count in rows}

    def set_landed(self, proposal_id: str, landed: Optional[Landing]) -> None:
        with self._session_factory() as session:
            proposal = session.get(ChangeProposalRun, proposal_id)
            if proposal is None:
                raise ValueError(f"No proposal {proposal_id}")
            proposal.landed = landed.to_dict() if landed else None  # type: ignore[assignment]
            session.commit()

    def save_operations(
        self,
        proposal_id: str,
        operations: Sequence[ProposedOperation],
        decisions: Sequence[ProposalDecision] = (),
    ) -> None:
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
                row.resolution = _resolution_json(operation)  # type: ignore[assignment]
                row.type_change = _type_change_json(operation)  # type: ignore[assignment]
                row.base = dict(operation.base)  # type: ignore[assignment]
            session.flush()
            for decision in decisions:
                session.add(_decision_to_orm(decision))
            session.commit()

    def supersede_decisions(self, proposal_id: str, superseded_at: datetime, by: str) -> int:
        with self._session_factory() as session:
            count = (
                session.query(ProposalDecisionRecord)
                .filter(
                    ProposalDecisionRecord.proposal_id == proposal_id,
                    ProposalDecisionRecord.superseded_at.is_(None),
                    ProposalDecisionRecord.decision != DecisionKind.REJECTED.value,
                )
                .update(
                    {
                        ProposalDecisionRecord.superseded_at: superseded_at.astimezone(
                            timezone.utc
                        ),
                        ProposalDecisionRecord.superseded_by: by,
                    },
                    synchronize_session=False,
                )
            )
            session.commit()
            return count

    def list_decisions(
        self, filters: DecisionFilter, limit: Optional[int] = None, offset: int = 0
    ) -> list[ProposalDecision]:
        with self._session_factory() as session:
            query = _filtered_decisions(session, filters).order_by(
                ProposalDecisionRecord.decided_at,
                ProposalDecisionRecord.proposal_id,
                ProposalDecisionRecord.seq,
            )
            if offset:
                query = query.offset(offset)
            if limit is not None:
                query = query.limit(limit)
            return [_decision_to_domain(row) for row in query]

    def count_decisions(self, filters: DecisionFilter) -> int:
        with self._session_factory() as session:
            return _filtered_decisions(session, filters).count()

    def backfill_decisions(self) -> int:
        """
        Record a decision for every applied or rejected operation without one:
        those decided before decisions were recorded. Idempotent.

        decided_by is "unknown"; decided_at is when the operation's change was
        made (the first change event of the proposal's run for its entity), else
        when it was proposed. A reverted proposal's applied decisions are
        superseded at its run's last change event (the revert's), else at
        decided_at; its rejections still stand. Rejections nobody judged (by a
        revert, or a bundle import superseding an older plan) are left out, as
        they are when made now; that filter runs in SQL, so the rows it skips
        for good are never loaded.

        Returns:
            How many decisions were recorded
        """
        with self._session_factory() as session:
            decided = session.query(ProposalDecisionRecord.operation_id)
            rows = (
                session.query(ProposalOperation)
                .join(ChangeProposalRun, ChangeProposalRun.id == ProposalOperation.proposal_id)
                .filter(
                    ProposalOperation.status.in_(
                        [OperationStatus.APPLIED.value, OperationStatus.REJECTED.value]
                    ),
                    ProposalOperation.id.not_in(decided),
                    not_(_unjudged_rejection()),
                )
                .order_by(ProposalOperation.proposal_id, ProposalOperation.seq)
                .all()
            )
            proposals: dict[str, ChangeProposal] = {}
            for row in rows:
                proposal_id: str = row.proposal_id  # type: ignore[assignment]
                if proposal_id not in proposals:
                    run = session.get(ChangeProposalRun, proposal_id)
                    proposals[proposal_id] = _to_domain(run, [])  # type: ignore[arg-type]
                proposal = proposals[proposal_id]
                operation = _operation_to_domain(row)
                decided_at = proposal.created_at
                if operation.status is OperationStatus.APPLIED and operation.result_entity_id:
                    first = (
                        session.query(func.min(ChangeEvent.timestamp))
                        .filter(
                            ChangeEvent.batch_run_id == proposal_id,
                            ChangeEvent.entity_id == operation.result_entity_id,
                        )
                        .scalar()
                    )
                    decided_at = _utc(first) or decided_at
                decision = decision_of(proposal, operation, DECIDED_BY_UNKNOWN, decided_at)
                if (
                    proposal.status is ProposalStatus.REVERTED
                    and decision.decision is not DecisionKind.REJECTED
                ):
                    last = (
                        session.query(func.max(ChangeEvent.timestamp))
                        .filter(ChangeEvent.batch_run_id == proposal_id)
                        .scalar()
                    )
                    decision.superseded_at = max(_utc(last) or decided_at, decided_at)
                    decision.superseded_by = DECIDED_BY_UNKNOWN
                session.add(_decision_to_orm(decision))
            session.commit()
            return len(rows)

    def set_status(self, proposal_id: str, status: ProposalStatus) -> None:
        with self._session_factory() as session:
            run = session.get(ChangeProposalRun, proposal_id)
            if run is None:
                raise ValueError(f"No proposal {proposal_id}")
            run.status = status.value  # type: ignore[assignment]
            session.commit()


def _unjudged_rejection():
    """
    SQL for a rejection nobody judged: a revert's of what was undecided (a
    reverted proposal, rejected as "proposal reverted"), or a new bundle
    import's of an earlier import's (a bundle proposal, rejected as superseded).
    Needs ProposalOperation joined to ChangeProposalRun.
    """
    reason = func.coalesce(ProposalOperation.reason, "")
    return and_(
        ProposalOperation.status == OperationStatus.REJECTED.value,
        or_(
            and_(
                ChangeProposalRun.status == ProposalStatus.REVERTED.value,
                reason == REVERTED_REASON,
            ),
            and_(
                ChangeProposalRun.source == ProposalSource.BUNDLE.value,
                or_(
                    reason.startswith(SUPERSEDED_PREFIX, autoescape=True),
                    reason.startswith(MATCHED_PREFIX, autoescape=True),
                ),
            ),
        ),
    )


def _utc(value: Optional[datetime]) -> Optional[datetime]:
    """A stored datetime as UTC (SQLite keeps the wall-clock time and drops the zone)."""
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _filtered_decisions(session: Session, filters: DecisionFilter):
    model = ProposalDecisionRecord
    query = session.query(model)
    for column, value in (
        (model.taxonomy_id, filters.taxonomy_id),
        (model.proposal_id, filters.proposal_id),
        (model.kind, filters.kind.value if filters.kind else None),
        (model.op, filters.op.value if filters.op else None),
        (model.decision, filters.decision.value if filters.decision else None),
        (model.decided_by, filters.decided_by),
    ):
        if value is not None:
            query = query.filter(column == value)
    if filters.decided_from is not None:
        query = query.filter(model.decided_at >= _stored(filters.decided_from))
    if filters.decided_to is not None:
        query = query.filter(model.decided_at < _stored(filters.decided_to))
    if not filters.include_superseded:
        query = query.filter(model.superseded_at.is_(None))
    return query


def _stored(value: datetime) -> datetime:
    """A datetime as stored: UTC (a naive one is taken as UTC already)."""
    return value.astimezone(timezone.utc) if value.tzinfo is not None else value


def _decision_to_orm(decision: ProposalDecision) -> ProposalDecisionRecord:
    return ProposalDecisionRecord(
        id=decision.id,
        operation_id=decision.operation_id,
        proposal_id=decision.proposal_id,
        taxonomy_id=decision.taxonomy_id,
        seq=decision.seq,
        kind=decision.kind.value,
        op=decision.op.value,
        decision=decision.decision.value,
        decided_at=_stored(decision.decided_at),
        decided_by=decision.decided_by,
        proposed=dict(decision.proposed),
        applied_fields=(
            dict(decision.applied_fields) if decision.applied_fields is not None else None
        ),
        result_entity_id=decision.result_entity_id,
        reason=decision.reason,
        resolution=dict(decision.resolution) if decision.resolution is not None else None,
        chosen_alternative=(
            dict(decision.chosen_alternative) if decision.chosen_alternative is not None else None
        ),
        probability=decision.probability,
        model=decision.model,
        superseded_at=_stored(decision.superseded_at) if decision.superseded_at else None,
        superseded_by=decision.superseded_by,
    )


def _decision_to_domain(row: ProposalDecisionRecord) -> ProposalDecision:
    return ProposalDecision(
        id=row.id,  # type: ignore[arg-type]
        operation_id=row.operation_id,  # type: ignore[arg-type]
        proposal_id=row.proposal_id,  # type: ignore[arg-type]
        taxonomy_id=row.taxonomy_id,  # type: ignore[arg-type]
        seq=row.seq,  # type: ignore[arg-type]
        kind=OperationKind(row.kind),
        op=OperationType(row.op),
        decision=DecisionKind(row.decision),
        decided_at=_utc(row.decided_at),  # type: ignore[arg-type]
        decided_by=row.decided_by,  # type: ignore[arg-type]
        proposed=dict(row.proposed or {}),  # type: ignore[arg-type]
        applied_fields=dict(row.applied_fields) if row.applied_fields is not None else None,  # type: ignore[arg-type]
        result_entity_id=row.result_entity_id,  # type: ignore[arg-type]
        reason=row.reason,  # type: ignore[arg-type]
        resolution=dict(row.resolution) if row.resolution is not None else None,  # type: ignore[arg-type]
        chosen_alternative=(
            dict(row.chosen_alternative)  # type: ignore[arg-type]
            if row.chosen_alternative is not None
            else None
        ),
        probability=row.probability,  # type: ignore[arg-type]
        model=row.model,  # type: ignore[arg-type]
        superseded_at=_utc(row.superseded_at),  # type: ignore[arg-type]
        superseded_by=row.superseded_by,  # type: ignore[arg-type]
    )


def _filtered(
    session: Session,
    taxonomy_id: Optional[str],
    status: Optional[ProposalStatus],
    source: Optional[ProposalSource],
    landed: Optional[bool] = None,
):
    query = session.query(ChangeProposalRun)
    if landed is not None:
        column = ChangeProposalRun.landed
        query = query.filter(column.isnot(None) if landed else column.is_(None))
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
        notes=operation.notes,
        evidence=list(operation.evidence),
        probability=operation.probability,
        scope=operation.scope.value,
        status=operation.status.value,
        result_entity_id=operation.result_entity_id,
        reason=operation.reason,
        applied_fields=operation.applied_fields,
        resolution=_resolution_json(operation),
        proposed_replacement_id=operation.proposed_replacement_id,
        type_change=_type_change_json(operation),
        alternatives=[dict(a) for a in operation.alternatives],
    )


def _resolution_json(operation: ProposedOperation) -> Optional[dict]:
    return operation.resolution.to_json() if operation.resolution is not None else None


def _type_change_json(operation: ProposedOperation) -> Optional[dict]:
    return operation.type_change.to_json() if operation.type_change is not None else None


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
        notes=row.notes,  # type: ignore[arg-type]
        evidence=list(row.evidence or []),
        probability=row.probability,  # type: ignore[arg-type]
        scope=ChangeScope(row.scope),
        status=OperationStatus(row.status),
        result_entity_id=row.result_entity_id,  # type: ignore[arg-type]
        reason=row.reason,  # type: ignore[arg-type]
        applied_fields=dict(row.applied_fields) if row.applied_fields is not None else None,
        resolution=(
            InUseResolution.from_json(dict(row.resolution))  # type: ignore[arg-type]
            if row.resolution is not None
            else None
        ),
        proposed_replacement_id=row.proposed_replacement_id,  # type: ignore[arg-type]
        type_change=(
            TypeChange.from_json(dict(row.type_change))  # type: ignore[arg-type]
            if row.type_change is not None
            else None
        ),
        alternatives=[dict(a) for a in row.alternatives or []],  # type: ignore[union-attr]
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
        source_revision=(
            SourceRevision.from_dict(run.source_revision)  # type: ignore[arg-type]
            if run.source_revision
            else None
        ),
        landed=Landing.from_dict(run.landed) if run.landed else None,  # type: ignore[arg-type]
        client_metadata=dict(run.client_metadata or {}),  # type: ignore[arg-type]
        dataset_id=run.dataset_id,  # type: ignore[arg-type]
    )
