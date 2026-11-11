import { Button } from "@tinkermonkey/heimdall-ui";
import { hasRunStatus } from "@/api/hooks/pipeline/runStatus";
import { isRunActive } from "@/api/hooks/sources/useExtractionRun";
import type { LastExtraction, LastExtractionRun } from "@/api/services/sources";
import { formatAge } from "@/components/proposals/proposalModel";
import { sourcesCopy } from "./copy";
import { extractionRunIds, type ExtractionRunIds } from "./sourceModel";

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

/** Why a finished run made no proposal: no candidates, or how it stopped. */
function endedText(run: LastExtractionRun): string {
  if (hasRunStatus(run.status, "completed")) return copy.noCandidates;
  if (run.status.toLowerCase() === "interrupted") return copy.interrupted;
  return copy.runEnded(run.status);
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
