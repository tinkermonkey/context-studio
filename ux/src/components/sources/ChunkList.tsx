import { Chip } from "@tinkermonkey/heimdall-ui";
import { hasRunStatus } from "@/api/hooks/pipeline/runStatus";
import { sourcesCopy } from "./copy";
import { pageRangeLabel, runChunks, type ChipTone } from "./sourceModel";
import type { components } from "@/api/types";

type PipelineRun = components["schemas"]["PipelineRunResponse"];

const copy = sourcesCopy.chunks;

interface ChunkRow {
  n: number;
  title: string;
  pages: string;
  state: string;
  tone: ChipTone;
}

function chunkRows(run: PipelineRun): ChunkRow[] {
  const finished = runChunks(run);
  if (finished.length > 0) {
    return finished.map((c) => ({
      n: c.index + 1,
      title: c.heading || copy.chunk(c.index + 1),
      pages: pageRangeLabel(c.page_first, c.page_last),
      state: copy.found(c.triples),
      tone: c.triples > 0 ? "emerald" : "neutral",
    }));
  }
  const total = run.items_total ?? 0;
  const done = run.items_done ?? 0;
  const running = hasRunStatus(run.status, "pending", "running");
  return Array.from({ length: total }, (_, i) => {
    const reading = running && i === done;
    return {
      n: i + 1,
      title: copy.chunk(i + 1),
      pages: "",
      state: i < done ? copy.read : reading ? copy.reading : copy.waiting,
      tone: i < done ? "emerald" : reading ? "amber" : "neutral",
    };
  });
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
 * candidate count; a running one shows which chunks are read, which is
 * being read and which wait. Before a run, only the estimated count shows.
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
            <li key={row.n} className="chunk-list__row" data-testid={`extract-chunk-${row.n}`}>
              <span className="chunk-list__n">{row.n}</span>
              <span className="chunk-list__text">
                <span className="chunk-list__title">{row.title}</span>
                {row.pages && <span className="sources-mono-muted">{row.pages}</span>}
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
