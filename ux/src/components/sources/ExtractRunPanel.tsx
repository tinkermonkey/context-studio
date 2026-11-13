import {
  Button,
  Chip,
  FormCallout,
  Panel,
  ProgressBar,
  StatGrid,
  StatTile,
} from "@tinkermonkey/heimdall-ui";
import { useChangeProposal } from "@/api/hooks/proposals";
import { hasRunStatus } from "@/api/hooks/pipeline/runStatus";
import { ApiError } from "@/api/client/interceptors";
import { isRunActive } from "@/api/hooks/sources/useExtractionRun";
import { sourcesCopy } from "./copy";
import {
  emptyChunksWarning,
  failedChunksWarning,
  noProposalSummary,
  proposalCounts,
  runChunks,
  skippedText,
  type ChipTone,
  type NoProposalSummary,
} from "./sourceModel";
import type { components } from "@/api/types";

type PipelineRun = components["schemas"]["PipelineRunResponse"];

const copy = sourcesCopy.extract;

interface ExtractRunPanelProps {
  run?: PipelineRun;
  /** The schema extraction run, when "Also suggest schema changes" was on. */
  schemaRun?: PipelineRun;
  /** Why the run couldn't be read, if it couldn't. */
  runError?: unknown;
  sourceTitle: string;
  /**
   * The dataset this extraction was for, when known before its proposal
   * loads; the proposal's own dataset wins.
   */
  datasetId?: string;
  /** A dataset's display name from its id. */
  datasetName: (datasetId: string) => string;
  onCancel: () => void;
  cancelling: boolean;
  onReview: (proposalId: string) => void;
  onBack: () => void;
  onRetry: () => void;
}

const RUN_TONE: Record<string, ChipTone> = {
  pending: "neutral",
  running: "amber",
  completed: "emerald",
  failed: "rose",
  cancelled: "neutral",
  interrupted: "amber",
};

/** The schema run's status beside the individual run, with its own proposal link. */
function SchemaRunLine({
  run,
  onReview,
}: {
  run: PipelineRun;
  onReview: (proposalId: string) => void;
}) {
  const status = run.status.toLowerCase();
  return (
    <div className="extract-run__schema" data-testid="extract-schema-run">
      <span className="extract-run__schema-label">{copy.schemaRun}</span>
      <Chip variant={RUN_TONE[status] ?? "neutral"}>{status}</Chip>
      {run.proposal_id && (
        <Button
          variant="link"
          size="sm"
          onClick={() => onReview(run.proposal_id!)}
          data-testid="extract-review-schema-proposal"
        >
          {copy.reviewSchemaProposal}
        </Button>
      )}
    </div>
  );
}

function RunningPanel({
  run,
  schemaRun,
  onCancel,
  cancelling,
  onReview,
}: Pick<ExtractRunPanelProps, "schemaRun" | "onCancel" | "cancelling" | "onReview"> & {
  run?: PipelineRun;
}) {
  const total = run?.items_total ?? 0;
  const done = run?.items_done ?? 0;
  const percent = total > 0 ? Math.round((done / total) * 100) : 0;
  return (
    <Panel
      title={copy.runningTitle}
      subtitle={copy.runningSubtitle}
      data-testid="extract-running-panel"
    >
      <div className="extract-run">
        <div className="extract-run__head">
          <span
            className="extract-run__headline"
            aria-live="polite"
            data-testid="extract-progress-headline"
          >
            {total > 0 ? copy.chunkHeadline(done, total) : copy.starting}
          </span>
          <Button
            variant="secondary"
            size="sm"
            onClick={onCancel}
            disabled={cancelling || !run}
            data-testid="extract-cancel-run"
          >
            {copy.cancelRun}
          </Button>
        </div>
        <ProgressBar
          percent={percent}
          color="amber"
          height={6}
          label={copy.percentLabel(percent)}
          data-testid="extract-progress-bar"
        />
        {run && (
          <span className="sources-mono-muted" data-testid="extract-run-tally">
            {`run ${run.id.slice(0, 8)} · ${run.pipeline_type} · ${run.configuration_ref}`}
          </span>
        )}
        {schemaRun && <SchemaRunLine run={schemaRun} onReview={onReview} />}
      </div>
    </Panel>
  );
}

/** Why a completed run proposed nothing: none found, or found but none could be proposed. */
function NoProposalNote({ summary }: { summary: NoProposalSummary }) {
  const ownWords = summary.candidatesFound
    ? copy.nothingProposedMessage(summary.found)
    : summary.failedNote
      ? copy.nothingInReadChunksMessage
      : copy.noCandidatesMessage;
  // A run with failed chunks leads its reason with them, which the panel has just said.
  const message = summary.failedNote ? ownWords : (summary.reason ?? ownWords);
  const skipped = skippedText(summary.skipped);
  return (
    <>
      <FormCallout
        variant={summary.candidatesFound ? "warn" : "info"}
        icon={summary.candidatesFound ? "alert" : "info"}
        data-testid="extract-no-proposal"
      >
        {message}
      </FormCallout>
      {skipped && (
        <p className="extract-run__skipped" data-testid="extract-skipped">
          <span className="extract-run__skipped-label">{copy.skippedLabel}</span>
          {skipped}
        </p>
      )}
    </>
  );
}

function DonePanel({
  run,
  schemaRun,
  sourceTitle,
  datasetId,
  datasetName,
  onReview,
  onBack,
}: Omit<ExtractRunPanelProps, "run" | "onCancel" | "cancelling" | "onRetry"> & {
  run: PipelineRun;
}) {
  const { data: proposal } = useChangeProposal(run.proposal_id ?? "");
  // The dataset chosen for this extraction, not necessarily the source's.
  const extractionDataset = proposal?.dataset_id ?? datasetId;
  const counts = proposal ? proposalCounts(proposal) : undefined;
  const empty = run.proposal_id ? undefined : noProposalSummary(run);
  const chunks = runChunks(run);
  // Chunks whose extraction failed: what they hold is missing from the result.
  const failed = failedChunksWarning(chunks);
  // When no chunk found anything the panel says so; naming every chunk would repeat it.
  const warning = empty && !empty.candidatesFound ? "" : emptyChunksWarning(chunks);
  // Titled for the whole extraction: a schema proposal alone is still a result.
  // A run that could not read every chunk never says the text holds no candidates.
  const title = !empty
    ? failed
      ? copy.partialDoneTitle
      : copy.doneTitle
    : schemaRun?.proposal_id
      ? copy.schemaDoneTitle
      : empty.candidatesFound || failed
        ? copy.nothingProposedTitle
        : copy.noCandidatesTitle;
  return (
    <Panel
      title={title}
      subtitle={copy.doneSubtitle(
        sourceTitle,
        extractionDataset ? datasetName(extractionDataset) : undefined,
      )}
      data-testid="extract-done-panel"
    >
      <div className="extract-run">
        {failed && (
          <FormCallout variant="error" icon="alert" data-testid="extract-failed-chunks">
            {failed}
          </FormCallout>
        )}
        {empty ? (
          <NoProposalNote summary={empty} />
        ) : (
          <StatGrid columns={4}>
            <StatTile
              label={copy.operations}
              value={counts?.operations ?? "—"}
              color="amber"
              data-testid="extract-count-operations"
            />
            <StatTile
              label={copy.newIndividuals}
              value={counts?.individuals ?? "—"}
              color="emerald"
              data-testid="extract-count-individuals"
            />
            <StatTile
              label={copy.relationships}
              value={counts?.relationships ?? "—"}
              color="cyan"
              data-testid="extract-count-relationships"
            />
            <StatTile
              label={copy.nearMatches}
              value={counts?.nearMatches ?? "—"}
              color="violet"
              data-testid="extract-count-near-matches"
            />
          </StatGrid>
        )}
        {warning && (
          <FormCallout variant="warn" icon="alert" role="note" data-testid="extract-empty-chunks">
            {warning}
          </FormCallout>
        )}
        {schemaRun && <SchemaRunLine run={schemaRun} onReview={onReview} />}
        <div className="extract-actions">
          <Button variant="ghost" size="sm" onClick={onBack} data-testid="extract-back">
            {copy.backToSources}
          </Button>
          {run.proposal_id && (
            <Button
              variant="primary"
              size="sm"
              onClick={() => onReview(run.proposal_id!)}
              data-testid="extract-review-proposal"
            >
              {copy.reviewProposal}
            </Button>
          )}
        </div>
      </div>
    </Panel>
  );
}

/** Why a run stopped without finishing: failed, interrupted by an app restart, or cancelled. */
function stoppedCopy(run: PipelineRun): { title: string; message: string } {
  if (hasRunStatus(run.status, "failed")) {
    return { title: copy.failedTitle, message: run.failure_reason ?? copy.failedTitle };
  }
  if (run.status.toLowerCase() === "interrupted") {
    return { title: copy.interruptedTitle, message: copy.interruptedMessage };
  }
  return { title: copy.cancelledTitle, message: copy.cancelledMessage };
}

/** The run couldn't be read: gone (a stale link) or the server failed. */
function RunErrorPanel({
  error,
  onBack,
  onRetry,
}: Pick<ExtractRunPanelProps, "onBack" | "onRetry"> & { error: unknown }) {
  const missing = error instanceof ApiError && error.status === 404;
  const detail = error instanceof ApiError ? error.detail : undefined;
  return (
    <Panel title={copy.runLoadTitle} data-testid="extract-run-error">
      <div className="extract-run">
        <FormCallout variant="error" icon="alert" data-testid="extract-run-error-reason">
          {missing ? copy.runMissing : (detail ?? copy.runLoadTitle)}
        </FormCallout>
        <div className="extract-actions">
          <Button variant="ghost" size="sm" onClick={onBack} data-testid="extract-back">
            {copy.backToSources}
          </Button>
          <Button variant="primary" size="sm" onClick={onRetry} data-testid="extract-retry">
            {copy.tryAgain}
          </Button>
        </div>
      </div>
    </Panel>
  );
}

function StoppedPanel({
  run,
  schemaRun,
  onReview,
  onBack,
  onRetry,
}: Pick<ExtractRunPanelProps, "schemaRun" | "onReview" | "onBack" | "onRetry"> & {
  run: PipelineRun;
}) {
  const { title, message } = stoppedCopy(run);
  return (
    <Panel title={title} data-testid="extract-stopped-panel">
      <div className="extract-run">
        <FormCallout
          variant={hasRunStatus(run.status, "failed") ? "error" : "info"}
          icon="alert"
          data-testid="extract-stopped-reason"
        >
          {message}
        </FormCallout>
        {schemaRun && <SchemaRunLine run={schemaRun} onReview={onReview} />}
        <div className="extract-actions">
          <Button variant="ghost" size="sm" onClick={onBack} data-testid="extract-back">
            {copy.backToSources}
          </Button>
          <Button variant="primary" size="sm" onClick={onRetry} data-testid="extract-retry">
            {copy.tryAgain}
          </Button>
        </div>
      </div>
    </Panel>
  );
}

/**
 * A started extraction: progress by chunk, then its proposal, or why it
 * stopped. Any state but pending or running is final.
 */
export function ExtractRunPanel(props: ExtractRunPanelProps) {
  const { run, runError } = props;
  if (!run && runError) return <RunErrorPanel {...props} error={runError} />;
  if (!run || isRunActive(run.status)) return <RunningPanel {...props} />;
  if (hasRunStatus(run.status, "completed")) return <DonePanel {...props} run={run} />;
  return <StoppedPanel {...props} run={run} />;
}
