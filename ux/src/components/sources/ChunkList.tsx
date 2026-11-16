import { Chip } from "@tinkermonkey/heimdall-ui";
import { hasRunStatus } from "@/api/hooks/pipeline/runStatus";
import { sourcesCopy } from "./copy";
import {
  chunkStates,
  isPartlyRead,
  pageRangeLabel,
  runChunks,
  runProgress,
  type ChipTone,
  type ChunkState,
} from "./sourceModel";
import type { components } from "@/api/types";

type PipelineRun = components["schemas"]["PipelineRunResponse"];

const copy = sourcesCopy.chunks;

interface ChunkRow {
  n: number;
  title: string;
  pages: string;
  state: string;
  tone: ChipTone;
  /** Why the chunk's extraction failed, when it did. */
  failure?: string;
}

const STATE_TONE: Record<ChunkState, ChipTone> = {
  waiting: "neutral",
  finding: "amber",
  searched: "cyan",
  reading: "amber",
  read: "emerald",
};

function chunkRows(run: PipelineRun): ChunkRow[] {
  const finished = runChunks(run);
  if (finished.length > 0) {
    return finished.map((c) => ({
      n: c.index + 1,
      title: c.heading || copy.chunk(c.index + 1),
      pages: pageRangeLabel(c.page_first, c.page_last),
      // A failed chunk was not read, or not all of it: it is not one that held nothing (more).
      ...(c.failure_reason
        ? {
            state: isPartlyRead(c) ? copy.partlyRead(c.triples) : copy.failed,
            tone: isPartlyRead(c) ? ("amber" as const) : ("rose" as const),
            failure: c.failure_reason,
          }
        : {
            state: copy.found(c.triples),
            tone: c.triples > 0 ? ("emerald" as const) : ("neutral" as const),
          }),
    }));
  }
  const progress = runProgress(run);
  const running = hasRunStatus(run.status, "pending", "running");
  // A staged run reads a chunk in two parts: only its relationships are left.
  const reading = progress.stage ? copy.readingRelationships : copy.reading;
  return chunkStates(progress, running).map((state, i) => ({
    n: i + 1,
    title: copy.chunk(i + 1),
    pages: "",
    state: state === "reading" ? reading : copy[state],
    tone: STATE_TONE[state],
  }));
}

interface ChunkListProps {
  /** The individual extraction run, once started. */
  run?: PipelineRun;
  /** Chunks expected before the run reports its own count: a count or a range ("3–6"). */
  estimatedChunks: string;
  pages: number;
}

/**
 * The run's chunks. A finished run lists each chunk's heading, pages and
 * candidate count, or that its extraction failed (whole, or in part with the
 * candidates it still gave) and why; a running one shows
 * which chunks are read, which is being read and which wait (for a run that
 * says which stage it is in: which are searched for mentions, and which have
 * their relationships read). Before a run, only the estimated count shows.
 */
export function ChunkList({ run, estimatedChunks, pages }: ChunkListProps) {
  const rows = run ? chunkRows(run) : [];
  const count = rows.length > 0 ? copy.count(rows.length, pages) : copy.estimated(estimatedChunks);
  return (
    <aside className="chunk-list" aria-label="Chunks" data-testid="extract-chunk-list">
      <div className="chunk-list__head">
        <span className="sources-eyebrow">{copy.heading}</span>
        <span className="sources-mono-muted" data-testid="extract-chunk-count">
          {count}
        </span>
      </div>
      {rows.length > 0 && (
        <ol className="chunk-list__rows">
          {rows.map((row) => (
            <li
              key={row.n}
              className={
                row.failure ? "chunk-list__row chunk-list__row--failed" : "chunk-list__row"
              }
              data-testid={`extract-chunk-${row.n}`}
            >
              <span className="chunk-list__n">{row.n}</span>
              <span className="chunk-list__text">
                <span className="chunk-list__title">{row.title}</span>
                {row.pages && <span className="sources-mono-muted">{row.pages}</span>}
                {row.failure && (
                  <span
                    className="chunk-list__reason"
                    data-testid={`extract-chunk-${row.n}-reason`}
                  >
                    {row.failure}
                  </span>
                )}
              </span>
              <Chip variant={row.tone}>{row.state}</Chip>
            </li>
          ))}
        </ol>
      )}
      <p className="sources-note">{copy.note}</p>
    </aside>
  );
}
