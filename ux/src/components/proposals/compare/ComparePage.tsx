import { useMemo, useState } from "react";
import {
  Button,
  Chip,
  FormCallout,
  PageHeader,
  Panel,
  SegmentedControl,
  StatGrid,
  StatTile,
} from "@tinkermonkey/heimdall-ui";
import { ApiError } from "@/api/client/interceptors";
import {
  useAcceptRest,
  useChangeProposal,
  useDecidePair,
  useProposalComparison,
} from "@/api/hooks/proposals";
import { useSource } from "@/api/hooks/sources/useSource";
import type {
  AcceptRestResponse,
  ChangeProposal,
  ComparedProposal,
  ComparisonPair,
  PairVerdict,
  RejectionReason,
} from "@/api/services/proposals";
import { usePageBreadcrumbs } from "@/hooks/usePageBreadcrumbs";
import { linkPath } from "@/lib/entityPaths";
import { formatDate } from "@/utils/dateFormatting";
import { useHoverOverlay } from "../HoverOverlay";
import { ProposalOriginChip } from "../ProposalOrigin";
import {
  ClassPill,
  IndividualPill,
  ReviewPillsProvider,
  type ReviewPillsValue,
} from "../review/ReviewPills";
import { REJECTION_REASONS } from "../review/reviewModel";
import { useReviewClock } from "../review/useReviewClock";
import { useReviewSchema } from "../review/useReviewSchema";
import {
  GROUPS,
  GROUP_META,
  choicesFor,
  classOf,
  decisionRequest,
  failureOf,
  filterPairs,
  originModel,
  outcomeText,
  pairTitle,
  proposalSize,
  quoteOf,
  takesDecision,
  type PairFilter,
} from "./compareModel";
import "../proposals.css";
import "../review/review.css";
import "./compare.css";

function messageOf(error: unknown): string {
  if (error instanceof ApiError) return error.detail;
  return error instanceof Error ? error.message : "Something went wrong.";
}

/** One proposal's card: its letter, origin, model, size and run date. */
function OriginCard({
  side,
  compared,
  proposal,
}: {
  side: "a" | "b";
  compared: ComparedProposal;
  proposal: ChangeProposal | undefined;
}) {
  const size = proposalSize(proposal);
  const line = [
    originModel(proposal),
    proposal && `${size.individuals} individuals`,
    proposal && `${size.relationships} relationships`,
    proposal && `run ${formatDate(proposal.created_at)}`,
  ]
    .filter(Boolean)
    .join(" · ");
  return (
    <section
      className={`compare-origin compare-origin--${side}`}
      aria-label={`Proposal ${side.toUpperCase()}`}
      data-testid={`compare-origin-${side}`}
    >
      <span className="compare-origin__letter" aria-hidden="true">
        {side.toUpperCase()}
      </span>
      <div className="compare-origin__body">
        {compared.origin ? (
          <ProposalOriginChip
            origin={compared.origin}
            data-testid={`compare-origin-${side}-chip`}
          />
        ) : (
          <span className="review-mono">{proposal?.title ?? compared.proposal_id}</span>
        )}
        {line && <span className="compare-origin__meta">{line}</span>}
      </div>
    </section>
  );
}

const FILTER_LABEL: Record<PairFilter, string> = {
  differences: "Differences",
  agreements: "Agreements",
  sample: "Sample",
  all: "All",
};

/** A pair's decision cell: the choices while it takes one, else how it was decided. */
function DecisionCell({
  pair,
  busy,
  error,
  choosingReason,
  classLabel,
  onChoose,
  onReason,
  onCancelReason,
}: {
  pair: ComparisonPair;
  busy: boolean;
  error?: string;
  choosingReason: boolean;
  classLabel: (id?: string) => string;
  onChoose: (verdict: PairVerdict) => void;
  onReason: (code: RejectionReason) => void;
  onCancelReason: () => void;
}) {
  // A fresh error for this row already says why the landing failed.
  const failure = error ? undefined : failureOf(pair);
  if (!takesDecision(pair)) {
    const landed = [pair.a, pair.b].some((c) => c?.status === "applied");
    return (
      <span
        className={`compare-outcome compare-outcome--${landed ? "landed" : "rejected"}`}
        data-testid={`compare-outcome-${pair.pair_id}`}
      >
        {outcomeText(pair, classLabel)}
      </span>
    );
  }
  return (
    <div className="compare-decision">
      {failure && (
        <span
          className="compare-row-error"
          role="alert"
          data-testid={`compare-failed-${pair.pair_id}`}
        >
          The last landing failed: {failure}
        </span>
      )}
      {choosingReason ? (
        <div
          className="compare-reasons"
          role="group"
          aria-label="Not an element, because"
          data-testid={`compare-reasons-${pair.pair_id}`}
        >
          {REJECTION_REASONS.map((reason) => (
            <button
              key={reason.code}
              type="button"
              className="review-reason"
              disabled={busy}
              onClick={() => onReason(reason.code)}
              data-testid={`compare-reason-${pair.pair_id}-${reason.code}`}
            >
              {reason.label}
            </button>
          ))}
          <Button variant="ghost" size="sm" onClick={onCancelReason}>
            Cancel
          </Button>
        </div>
      ) : (
        <div className="compare-choices" role="group" aria-label={`Decide ${pairTitle(pair)}`}>
          {choicesFor(pair).map((choice) => (
            <Button
              key={choice.verdict}
              variant={choice.verdict === "not_element" ? "ghost" : "secondary"}
              size="sm"
              disabled={busy}
              onClick={() => onChoose(choice.verdict)}
              data-testid={`compare-decide-${pair.pair_id}-${choice.verdict}`}
            >
              {choice.label}
            </Button>
          ))}
        </div>
      )}
      {error && (
        <span
          className="compare-row-error"
          role="alert"
          data-testid={`compare-error-${pair.pair_id}`}
        >
          {error}
        </span>
      )}
    </div>
  );
}

function restSummary(result: AcceptRestResponse): string {
  const parts = [
    `Accepted ${result.landed} ${result.landed === 1 ? "agreement" : "agreements"}.`,
    result.skipped.length > 0 &&
      `${result.skipped.length} left for you (a near match or no passage).`,
    result.failed.length > 0 && `${result.failed.length} failed.`,
  ];
  return parts.filter(Boolean).join(" ");
}

interface ComparePageProps {
  /** Proposal A: the one the comparison was opened from. */
  aId: string;
  bId: string;
  /** Back to proposal A. */
  onFinish: () => void;
}

/**
 * Two pipelines' proposals for the same source, compared: their origins, how
 * their elements pair up, and the differences to decide, each once for both
 * proposals. Agreements are accepted in bulk only after a sample is checked.
 */
export function ComparePage({ aId, bId, onFinish }: ComparePageProps) {
  const { data: comparison, error, refetch } = useProposalComparison(aId, bId);
  const { data: proposalA } = useChangeProposal(aId);
  const { data: proposalB } = useChangeProposal(bId);
  const { data: source } = useSource(comparison?.source_id);
  const schema = useReviewSchema(comparison?.taxonomy_id ?? proposalA?.taxonomy_id ?? "");
  const decide = useDecidePair(aId, bId);
  const acceptRest = useAcceptRest(aId, bId);
  const clock = useReviewClock();
  const overlay = useHoverOverlay("#compare-differences", { lingerMs: 150, width: 320 });
  const pills: ReviewPillsValue = {
    schema,
    overlay,
    link: (operationId) => ({
      href: `${linkPath("proposal", aId)}/review?selected=${encodeURIComponent(operationId)}`,
      onClick: () => {},
    }),
  };

  const [filter, setFilter] = useState<PairFilter>("differences");
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});
  const [choosingReason, setChoosingReason] = useState<string>();
  const [pending, setPending] = useState<string>();
  const [restResult, setRestResult] = useState<AcceptRestResponse>();
  const [restError, setRestError] = useState<string>();

  const shown = useMemo(() => filterPairs(comparison?.pairs ?? [], filter), [comparison, filter]);

  usePageBreadcrumbs(
    `${linkPath("proposal", aId)}/compare/${bId}`,
    proposalA
      ? [
          { label: "Proposals", to: "/app/proposals" },
          { label: proposalA.title, to: linkPath("proposal", aId) },
          { label: "Compare" },
        ]
      : null,
  );

  const setRowError = (pairId: string, message?: string) =>
    setRowErrors((all) => {
      const next = { ...all };
      if (message) next[pairId] = message;
      else delete next[pairId];
      return next;
    });

  const decidePair = async (
    pair: ComparisonPair,
    verdict: PairVerdict,
    reasonCode?: RejectionReason,
  ) => {
    if (pending) return;
    setPending(pair.pair_id);
    setRowError(pair.pair_id);
    try {
      const result = await decide.mutateAsync(
        decisionRequest(pair, verdict, { reasonCode, reviewMs: clock.spentOn(pair.pair_id) }),
      );
      setChoosingReason(undefined);
      if (result.outcome === "failed") {
        setRowError(pair.pair_id, result.failure_reason ?? "The landing failed.");
      }
    } catch (err) {
      setRowError(pair.pair_id, messageOf(err));
    } finally {
      setPending(undefined);
    }
  };

  const runAcceptRest = async () => {
    setRestError(undefined);
    setRestResult(undefined);
    try {
      setRestResult(await acceptRest.mutateAsync());
    } catch (err) {
      setRestError(messageOf(err));
    }
  };

  const header = (
    <PageHeader
      eyebrow={`SOURCE ${source?.title ?? "…"} · TWO OPEN PROPOSALS`}
      title="Compare pipelines"
      subtitle="Two implementations extracted the same source. Where they agree, decide in one step; spend the review where they differ. What you decide lands once and closes the other proposal's copy as a duplicate."
      actions={
        <Button variant="primary" size="sm" onClick={onFinish} data-testid="compare-finish">
          Finish comparison
        </Button>
      }
      data-testid="compare-header"
    />
  );

  if (error) {
    return (
      <div className="compare-page" data-testid="compare-page">
        {header}
        <FormCallout variant="error" icon="alert" data-testid="compare-load-error">
          {messageOf(error)}
        </FormCallout>
        {!(error instanceof ApiError && error.status === 422) && (
          <Button variant="secondary" size="sm" onClick={() => refetch()}>
            Try again
          </Button>
        )}
      </div>
    );
  }

  if (!comparison) {
    return (
      <div className="compare-page" data-testid="compare-page">
        {header}
        <div className="skeleton entity-page__skeleton" aria-busy="true" />
      </div>
    );
  }

  const { counts, sample } = comparison;
  const implementationOf = (side: ComparedProposal) =>
    side.origin?.implementation_id ?? side.proposal_id.slice(0, 8);
  const sampleChecked = sample.size > 0 && sample.checked >= sample.size;
  const restOpen = comparison.pairs.some(
    (p) => p.group === "same_class" && !p.in_sample && takesDecision(p),
  );

  return (
    <div className="compare-page" data-testid="compare-page">
      {header}

      <div className="compare-origins">
        <OriginCard side="a" compared={comparison.a} proposal={proposalA} />
        <OriginCard side="b" compared={comparison.b} proposal={proposalB} />
      </div>

      <StatGrid columns={4} data-testid="compare-counts">
        {GROUPS.map((group) => (
          <StatTile
            key={group}
            label={GROUP_META[group].label}
            value={counts[group]}
            color={GROUP_META[group].color}
            meta={GROUP_META[group].meta}
            data-testid={`compare-count-${group}`}
          />
        ))}
      </StatGrid>

      <ReviewPillsProvider value={pills}>
        <div className="compare-body">
          <Panel
            id="compare-differences"
            className="compare-differences"
            role="region"
            aria-label="Where they differ"
            noPadding
            title="Where they differ"
            headerAction={
              <div data-testid="compare-filter">
                <SegmentedControl
                  value={filter}
                  onChange={(value) => setFilter(value as PairFilter)}
                  aria-label="Show pairs"
                  options={(["differences", "agreements", "sample", "all"] as PairFilter[]).map(
                    (value) => ({
                      value,
                      label: `${FILTER_LABEL[value]} · ${filterPairs(comparison.pairs, value).length}`,
                    }),
                  )}
                />
              </div>
            }
            data-testid="compare-differences"
          >
            <div className="compare-table-wrap">
              <table className="compare-table" data-testid="compare-table">
                <thead>
                  <tr>
                    <th scope="col">Element</th>
                    <th scope="col">A · {implementationOf(comparison.a)}</th>
                    <th scope="col">B · {implementationOf(comparison.b)}</th>
                    <th scope="col">Decision</th>
                  </tr>
                </thead>
                <tbody>
                  {shown.length === 0 && (
                    <tr>
                      <td colSpan={4} className="compare-empty" data-testid="compare-empty">
                        Nothing to show here.
                      </td>
                    </tr>
                  )}
                  {shown.map((pair) => (
                    <tr
                      key={pair.pair_id}
                      className={[
                        "compare-row",
                        `compare-row--${pair.group}`,
                        `compare-row--${pair.state}`,
                        pair.in_sample && "compare-row--sample",
                      ]
                        .filter(Boolean)
                        .join(" ")}
                      data-group={pair.group}
                      data-state={pair.state}
                      // Time on the row runs from when the reviewer reaches it.
                      onPointerEnter={() => clock.startElement(pair.pair_id)}
                      onFocus={() => clock.startElement(pair.pair_id)}
                      data-testid={`compare-row-${pair.pair_id}`}
                    >
                      <td>
                        <IndividualPill
                          title={pairTitle(pair)}
                          classId={classOf(pair.a) ?? classOf(pair.b)}
                          quote={quoteOf(pair)}
                        />
                        <div className="compare-kind">
                          {GROUP_META[pair.group].kind}
                          {pair.in_sample && (
                            <Chip variant="emerald" data-testid={`compare-sample-${pair.pair_id}`}>
                              sample
                            </Chip>
                          )}
                        </div>
                      </td>
                      <td>
                        {pair.a ? (
                          <ClassPill classId={classOf(pair.a)} />
                        ) : (
                          <span className="compare-none">—</span>
                        )}
                      </td>
                      <td>
                        {pair.b ? (
                          <ClassPill classId={classOf(pair.b)} />
                        ) : (
                          <span className="compare-none">—</span>
                        )}
                      </td>
                      <td>
                        <DecisionCell
                          pair={pair}
                          busy={!!pending}
                          error={rowErrors[pair.pair_id]}
                          choosingReason={choosingReason === pair.pair_id}
                          classLabel={schema.classLabel}
                          onChoose={(verdict) =>
                            verdict === "not_element"
                              ? setChoosingReason(pair.pair_id)
                              : void decidePair(pair, verdict)
                          }
                          onReason={(code) => void decidePair(pair, "not_element", code)}
                          onCancelReason={() => setChoosingReason(undefined)}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>

          <aside className="compare-side" aria-label="Agreements" data-testid="compare-agreements">
            <Panel title="Agreements">
              <div className="compare-side__body">
                <p className="compare-text" data-testid="compare-agreements-count">
                  {counts.same_class} {counts.same_class === 1 ? "element" : "elements"} both
                  pipelines found with the same class.
                </p>
                <p className="compare-muted">
                  Agreement is not proof: two pipelines share the same schema and similar prompts,
                  so they can be wrong together. Check a random sample before accepting the rest.
                </p>
                <div className="review-chips">
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={sample.size === 0}
                    aria-controls="compare-differences"
                    onClick={() => setFilter("sample")}
                    data-testid="compare-check-sample"
                  >
                    Check a sample of {sample.size}
                  </Button>
                  <Button
                    variant={sampleChecked ? "primary" : "ghost"}
                    size="sm"
                    disabled={!sampleChecked || !restOpen || acceptRest.isPending}
                    title={
                      sampleChecked ? undefined : "Offered once every pair of the sample is decided"
                    }
                    aria-busy={acceptRest.isPending ? true : undefined}
                    onClick={() => void runAcceptRest()}
                    data-testid="compare-accept-rest"
                  >
                    Accept the rest
                  </Button>
                </div>
                <span className="compare-muted" data-testid="compare-sample-progress">
                  Sample: {sample.checked} / {sample.size} checked · {sample.changed} changed
                </span>
                {restResult && (
                  <span className="compare-text" role="status" data-testid="compare-rest-result">
                    {restSummary(restResult)}
                  </span>
                )}
                {restError && (
                  <span className="compare-row-error" role="alert" data-testid="compare-rest-error">
                    {restError}
                  </span>
                )}
              </div>
            </Panel>
            <Panel title="What this feeds">
              <p className="compare-muted" data-testid="compare-feeds">
                Every decision here counts for both pipelines: an element kept from B only is a miss
                for A, a class you pick is a class error for the other. The Review value page reads
                these.
              </p>
            </Panel>
          </aside>
        </div>
        {overlay.overlay}
      </ReviewPillsProvider>
    </div>
  );
}
