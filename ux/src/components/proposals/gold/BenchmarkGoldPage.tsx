import { useMemo } from "react";
import { Button, Chip, PageHeader, Panel, ProgressBar, Table } from "@tinkermonkey/heimdall-ui";
import { useChangeProposals } from "@/api/hooks/proposals";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { useToasts } from "@/components/ui/Toast";
import {
  GOLD_COMMANDS,
  GOLD_STATUS_CHIP,
  GOLD_WRITES,
  SPLIT_CHIP,
  goldRows,
  type GoldRow,
} from "../review/goldModel";
import "./gold.css";

/** Gold checks are pipeline proposals; one page of them covers every document. */
const LIST_PARAMS = { source: "pipeline" as const, limit: 500 };

/** A shell command with a Copy button. */
function CommandLine({
  command,
  "data-testid": testId,
}: {
  command: string;
  "data-testid"?: string;
}) {
  const { toast } = useToasts();
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(command);
      toast("success", "Command copied");
    } catch {
      toast("error", "Couldn't copy the command");
    }
  };
  return (
    <div className="gold-command" data-testid={testId}>
      <code className="gold-command__text">{command}</code>
      <Button variant="ghost" size="sm" aria-label={`Copy: ${command}`} onClick={() => void copy()}>
        Copy
      </Button>
    </div>
  );
}

interface BenchmarkGoldPageProps {
  /** Open a gold check's proposal on the Review page. */
  onOpenReview: (proposalId: string) => void;
}

/**
 * The benchmark's gold files loaded for a person to check: each document's
 * split, size, how far its check is, and the Review page to check it on;
 * then what a check writes back to gold.json and the commands that load a
 * check, write it back and re-score the saved takes.
 */
export function BenchmarkGoldPage({ onOpenReview }: BenchmarkGoldPageProps) {
  const { data, error, isLoading, refetch } = useChangeProposals(LIST_PARAMS);
  const rows = useMemo(() => goldRows(data?.items ?? []), [data]);

  const header = (
    <PageHeader
      eyebrow="PIPELINES · BENCHMARK"
      title="Benchmark gold"
      subtitle="The extractions every pipeline is scored against, drafted and reviewed by models until a person checks them. Checking one opens the Review page on the gold itself; written back, it re-scores every saved take at no cost."
      data-testid="gold-header"
    />
  );

  if (error) {
    return (
      <div className="gold-page" data-testid="gold-page">
        {header}
        <ErrorBanner error={error} onRetry={() => refetch()} message="Failed to load gold checks" />
      </div>
    );
  }

  return (
    <div className="gold-page" data-testid="gold-page">
      {header}

      {isLoading ? (
        <div className="skeleton entity-page__skeleton" aria-busy="true" />
      ) : rows.length === 0 ? (
        <div className="gold-empty" data-testid="gold-empty">
          <EmptyState
            title="No gold check is loaded"
            description="Load a document's gold file as a proposal to check, from local-server/:"
          />
          <CommandLine
            command={GOLD_COMMANDS.check("<document>")}
            data-testid="gold-empty-command"
          />
        </div>
      ) : (
        <Panel noPadding role="region" aria-label="Documents" data-testid="gold-documents">
          <Table<GoldRow>
            rowKey="proposalId"
            data={rows}
            columns={[
              {
                key: "document",
                label: "Document",
                render: (_, row) => (
                  <span className="gold-mono" data-testid={`gold-row-${row.document}`}>
                    {row.document}
                  </span>
                ),
              },
              {
                key: "split",
                label: "Split",
                render: (_, row) => <Chip variant={SPLIT_CHIP[row.split]}>{row.split}</Chip>,
              },
              {
                key: "individuals",
                label: "Individuals",
                render: (_, row) => <span className="gold-number">{row.individuals}</span>,
              },
              {
                key: "relationships",
                label: "Relationships",
                render: (_, row) => <span className="gold-number">{row.relationships}</span>,
              },
              {
                key: "percent",
                label: "Checked",
                width: "220px",
                render: (_, row) => (
                  <div className="gold-progress">
                    <ProgressBar
                      percent={row.percent}
                      color="emerald"
                      height={6}
                      label={`${row.document}: ${row.decided} of ${row.total} decided`}
                    />
                    <span className="gold-progress__count">
                      {row.decided} / {row.total} decided
                    </span>
                  </div>
                ),
              },
              {
                key: "status",
                label: "Status",
                render: (_, row) => (
                  <Chip
                    variant={GOLD_STATUS_CHIP[row.status]}
                    data-testid={`gold-status-${row.document}`}
                  >
                    {row.status}
                  </Chip>
                ),
              },
              {
                key: "action",
                label: "",
                render: (_, row) => (
                  <Button
                    variant={row.action === "Check gold" ? "primary" : "secondary"}
                    size="sm"
                    aria-label={`${row.action}: ${row.document}`}
                    onClick={() => onOpenReview(row.proposalId)}
                    data-testid={`gold-open-${row.document}`}
                  >
                    {row.action}
                  </Button>
                ),
              },
            ]}
          />
        </Panel>
      )}

      <div className="gold-panels">
        <Panel
          title="What a check writes to gold.json"
          role="region"
          aria-label="What a check writes"
          data-testid="gold-writes"
        >
          <ul className="gold-writes">
            {GOLD_WRITES.map((write) => (
              <li key={write.verdict} className="gold-writes__item">
                <span className="gold-writes__verdict">{write.verdict}</span>
                <span className="gold-writes__effect">{write.effect}</span>
              </li>
            ))}
          </ul>
          <p className="gold-muted">
            Only a person&apos;s decision is a verdict: anything left undecided stays as it was, so
            a check can be written back in parts. Each element records who checked it and when.
          </p>
        </Panel>

        <Panel
          title="What is different from a normal review"
          role="region"
          aria-label="What is different from a normal review"
          data-testid="gold-differences"
        >
          <ul className="gold-list">
            <li>Every element shows its tier, core or supporting, and the reviewer can flip it.</li>
            <li>
              A class can be marked also defensible instead of replacing the chosen one; it goes to
              acceptable_classes.
            </li>
            <li>Rejecting needs a note: it becomes the excluded entry&apos;s reason.</li>
            <li>Relationships are decided after both their ends.</li>
            <li>
              Decisions apply only into the check&apos;s own dataset; the result is the gold file.
            </li>
          </ul>
        </Panel>

        <Panel
          title="Write back and re-score"
          role="region"
          aria-label="Write back and re-score"
          data-testid="gold-commands"
        >
          <p className="gold-muted">From local-server/, once a check is done (or in parts):</p>
          {rows.map((row) => (
            <div key={row.proposalId} className="gold-commands__document">
              <span className="gold-mono">{row.document}</span>
              <CommandLine
                command={GOLD_COMMANDS.writeGold(row.document, row.proposalId)}
                data-testid={`gold-write-${row.document}`}
              />
              <CommandLine command={GOLD_COMMANDS.validate(row.document)} />
            </div>
          ))}
          <span className="gold-muted">Then re-score the saved takes, free:</span>
          <CommandLine command={GOLD_COMMANDS.replay} data-testid="gold-replay" />
          <CommandLine command={GOLD_COMMANDS.replayExternal} data-testid="gold-replay-external" />
          <span className="gold-muted">Check another document:</span>
          <CommandLine
            command={GOLD_COMMANDS.check("<document>")}
            data-testid="gold-check-command"
          />
        </Panel>

        <Panel
          title="Holdout and scores"
          role="region"
          aria-label="Holdout and scores"
          data-testid="gold-holdout"
        >
          <p className="gold-text">
            wikimedia_enterprise is the holdout. Check it like the others, but its element-level
            errors are never shown on a page anyone tuning a pipeline reads; only its scores are.
          </p>
          <p className="gold-muted">
            When a document&apos;s check is written back, every saved take of every experiment
            re-scores against it. Experiment pages whose numbers move are listed for update.
          </p>
        </Panel>
      </div>
    </div>
  );
}
