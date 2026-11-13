import { Button } from "@tinkermonkey/heimdall-ui";
import { hasRunStatus } from "@/api/hooks/pipeline/runStatus";
import { isRunActive, useExtractionRun } from "@/api/hooks/sources/useExtractionRun";
import type { LastExtraction, LastExtractionRun } from "@/api/services/sources";
import { formatAge } from "@/components/proposals/proposalModel";
import { sourcesCopy } from "./copy";
import {
  extractionRunIds,
  noProposalSummary,
  skippedText,
  type ExtractionRunIds,
} from "./sourceModel";

const copy = sourcesCopy.table;

interface LastExtractionCellProps {
  sourceId: string;
  extraction?: LastExtraction | null;
  onOpenProposal: (proposalId: string) => void;
  onFollowRun: (runs: ExtractionRunIds) => void;
}

function progressText(run: LastExtractionRun): string {
  const total = run.items_total ?? 0;
  return total > 0 ? copy.runProgress(run.items_done ?? 0, total) : copy.runStarting;
}

/** How a run that stopped before finishing ended: interrupted, failed or cancelled. */
function endedText(run: LastExtractionRun): string {
  if (run.status.toLowerCase() === "interrupted") return copy.interrupted;
  return copy.runEnded(run.status);
}

/**
 * A completed run that made no proposal, read in full for why: nothing found,
 * candidates found that none could be proposed (and why not), or chunks whose
 * extraction failed, after which it cannot say that nothing was there to find.
 */
function NoProposalLink({
  sourceId,
  runId,
  onFollow,
}: {
  sourceId: string;
  runId: string;
  onFollow: () => void;
}) {
  const { data: run } = useExtractionRun(runId);
  const summary = run ? noProposalSummary(run) : undefined;
  const label = !summary
    ? copy.noProposal
    : summary.candidatesFound || summary.failedNote
      ? copy.nothingProposed
      : copy.noCandidates;
  const why =
    summary?.reason ??
    [
      summary?.failedNote ?? "",
      summary && summary.found > 0 ? copy.foundCount(summary.found) : "",
      skippedText(summary?.skipped ?? []),
    ]
      .filter(Boolean)
      .join("; ");
  return (
    <>
      <Button
        variant="link"
        size="sm"
        className="sources-link"
        onClick={onFollow}
        data-testid={`source-follow-run-${sourceId}`}
      >
        {label}
      </Button>
      {why && (
        <span className="sources-note" data-testid={`source-no-proposal-reason-${sourceId}`}>
          {why}
        </span>
      )}
    </>
  );
}

/**
 * A source's last extraction, as the source reports it: its progress while a
 * run is going, then its proposal (and the schema proposal, when there is
 * one), or why it ended without one.
 */
export function LastExtractionCell({
  sourceId,
  extraction,
  onOpenProposal,
  onFollowRun,
}: LastExtractionCellProps) {
  const testId = `source-last-extraction-${sourceId}`;
  if (!extraction || extraction.runs.length === 0) {
    return (
      <span className="sources-muted" data-testid={testId}>
        {copy.notExtracted}
      </span>
    );
  }

  const runs = extraction.runs;
  const main = runs.find((r) => r.pipeline === "individual_extraction") ?? runs[0];
  const schema = runs.find((r) => r.pipeline === "schema_extraction");
  const follow = () => onFollowRun(extractionRunIds(runs));
  const age = formatAge(extraction.started_at);

  if (runs.some((r) => isRunActive(r.status))) {
    const active = isRunActive(main.status) ? main : (schema ?? main);
    return (
      <span className="sources-cell-stack" data-testid={testId}>
        <Button
          variant="link"
          size="sm"
          className="sources-link"
          onClick={follow}
          data-testid={`source-follow-run-${sourceId}`}
        >
          {copy.followRun}
        </Button>
        <span className="sources-mono-muted">{progressText(active)}</span>
      </span>
    );
  }

  const detail = [main.operations != null ? copy.operations(main.operations) : null, age]
    .filter(Boolean)
    .join(" · ");

  return (
    <span className="sources-cell-stack" data-testid={testId}>
      {main.proposal_id ? (
        <Button
          variant="link"
          size="sm"
          className="sources-link"
          onClick={() => onOpenProposal(main.proposal_id!)}
          data-testid={`source-open-proposal-${sourceId}`}
        >
          {copy.openProposal}
        </Button>
      ) : hasRunStatus(main.status, "completed") ? (
        <NoProposalLink sourceId={sourceId} runId={main.run_id} onFollow={follow} />
      ) : (
        <Button
          variant="link"
          size="sm"
          className="sources-link"
          onClick={follow}
          data-testid={`source-follow-run-${sourceId}`}
        >
          {endedText(main)}
        </Button>
      )}
      {schema?.proposal_id && (
        <Button
          variant="link"
          size="sm"
          className="sources-link sources-link--secondary"
          onClick={() => onOpenProposal(schema.proposal_id!)}
          data-testid={`source-open-schema-proposal-${sourceId}`}
        >
          {copy.openSchemaProposal}
        </Button>
      )}
      <span className="sources-mono-muted">{detail}</span>
    </span>
  );
}
