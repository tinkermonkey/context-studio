"""
Score claim triage against people's verdicts (#1522), as DR's triage-bench.ts does.

Runs the claim_triage pipeline in-process on a taxonomy's claims that have a
verdict (recorded in Context Studio, or imported from DR's bench gold with
scripts/import_dr_claims.py), then prints a markdown table comparable with DR's
report-clef@evidence.md, and the claims whose validity it missed.

Usage (from local-server/; calls the decision model unless --score-only):

    python scripts/bench_triage.py                       # the dr_spec taxonomy
    python scripts/bench_triage.py --taxonomy ID --model clef-flash --policy full
    python scripts/bench_triage.py --score-only          # score the saved triage
"""

import argparse
import asyncio
import os
import sys
from typing import Any, Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.decision.registry import build_decision_models
from adapters.interchange.dr_relationships import DR_TAXONOMY_IDENTIFIER, dr_predicate_catalog_for
from adapters.llm.provider_router import LLMProviderRouter
from adapters.persistence.sqlite.claim_repo import SQLiteClaimRepository
from adapters.persistence.sqlite.connection import DatabaseManager
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.proposal_repo import SQLiteChangeProposalRepository
from config import get_config_manager
from domain.decision.ports import DecisionModels
from domain.ontology.ports import OntologyRepository
from domain.pipelines.claim_triage import ClaimTriageOrchestrator, ClaimTriageState
from domain.pipelines.claim_triage.configurations.default import get_default_config
from domain.pipelines.entities import PipelineType
from domain.versioning.claims import Claim, ClaimFilter, ClaimService, TriageScore, score_triage

BENCH_RUN_ID = "bench"


def run_bench(
    repo: OntologyRepository,
    claims: ClaimService,
    taxonomy_id: str,
    decision_models: Optional[DecisionModels] = None,
    proposals: Any = None,
    config: Optional[dict[str, Any]] = None,
) -> tuple[TriageScore, list[Claim]]:
    """
    Triage the taxonomy's judged claims (unless decision_models is None, which
    scores the triage they already have) and score it against their verdicts.

    Args:
        proposals: Open proposals (anything with list_proposals), for the
            definitions pending per subject
        config: Overrides of the pipeline's default configuration
    """
    judged = claims.list_claims(ClaimFilter(taxonomy_id=taxonomy_id, has_verdict=True))
    if decision_models is not None and judged:
        orchestrator = ClaimTriageOrchestrator(
            ontology_repo=repo,
            decision_models=decision_models,
            claim_service=claims,
            proposal_service=proposals,
            predicate_catalog=lambda t: dr_predicate_catalog_for(repo, t),
            config={**get_default_config(), **(config or {})},
        )
        state = ClaimTriageState(
            run_id=BENCH_RUN_ID,
            pipeline_type=PipelineType.CLAIM_TRIAGE,
            input_data={"taxonomy_id": taxonomy_id, "scope": {"keys": [c.key for c in judged]}},
        )
        asyncio.run(orchestrator.execute(state))
        judged = claims.list_claims(ClaimFilter(taxonomy_id=taxonomy_id, has_verdict=True))
    return score_triage(judged), judged


def _pct(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{100 * value:.0f}%"


def _num(value: Optional[float], digits: int = 2) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def render(score: TriageScore, judged: list[Claim], label: str) -> str:
    """The benchmark table and per-claim detail, in triage-bench.ts's layout."""
    lines = [
        f"Benchmark: {score.n} adjudicated claims",
        "",
        "| model | n | validity acc | mean p(gold validity) | category acc | severity MAE"
        " | severity within 1 | fix-scope MAE | median latency | cost / claim |",
        "|---|---|---|---|---|---|---|---|---|---|",
        f"| {label} | {score.n} | {_pct(score.validity_accuracy)}"
        f" | {_num(score.mean_p_gold_validity)} | {_pct(score.category_accuracy)}"
        f" | {_num(score.severity_mae)} | {_pct(score.severity_within_1)}"
        f" | {_num(score.fix_scope_mae)} | {_num(score.median_latency_ms, 0)} ms"
        f" | ${_num(score.mean_cost_usd, 4)} |",
        "",
        "Per-claim detail:",
    ]
    for claim in judged:
        triage, verdict = claim.triage, claim.verdict
        if triage is None or verdict is None:
            continue
        ok = "ok  " if triage.validity == verdict.validity else "MISS"
        p = triage.validity_probabilities.get(triage.validity.value)
        lines.append(
            f"  {ok} {claim.key:<44} gold={verdict.validity.value}/{verdict.category}"
            f"/sev{verdict.severity}  got={triage.validity.value}({_num(p)})"
            f"/{triage.category}/sev{triage.severity}"
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--taxonomy", default=DR_TAXONOMY_IDENTIFIER, help="Taxonomy id or identifier"
    )
    parser.add_argument("--model", help="Decision model instance (default: the configured one)")
    parser.add_argument("--policy", choices=["full", "summary", "none"], help="Context policy")
    parser.add_argument(
        "--score-only", action="store_true", help="Score the saved triage; call no model"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_config_manager().get_settings()
    db_manager = DatabaseManager()
    db_manager.initialize(
        local_db_url=f"sqlite:///{settings.database.local_db_path}",
        operations_db_url=f"sqlite:///{settings.database.operations_db_path}",
    )
    session_factory = db_manager.get_local_session_factory()
    repo = SQLiteOntologyRepository(session_factory)
    taxonomy = repo.get_taxonomy(args.taxonomy) or repo.get_by_identifier(args.taxonomy)
    if taxonomy is None:
        print(f"No taxonomy {args.taxonomy}", file=sys.stderr)
        return 1
    claims = ClaimService(SQLiteClaimRepository(session_factory), repo)
    models = None
    if not args.score_only:
        llm = LLMProviderRouter(
            openai_api_key=settings.llm.openai_api_key,
            anthropic_api_key=settings.llm.anthropic_api_key,
            openrouter_api_key=settings.llm.openrouter_api_key,
        )
        models = build_decision_models(settings.decision_models, llm)
    config = {
        k: v
        for k, v in (("decision_model", args.model), ("context_policy", args.policy))
        if v is not None
    }
    score, judged = run_bench(
        repo,
        claims,
        taxonomy.id,
        models,
        SQLiteChangeProposalRepository(session_factory),
        config,
    )
    if not score.n:
        print("No claim has both a verdict and a triage", file=sys.stderr)
        return 2
    label = args.model or (models.get().name if models else "saved triage")
    print(render(score, judged, label))
    return 0


if __name__ == "__main__":
    sys.exit(main())
