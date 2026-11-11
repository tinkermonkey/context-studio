import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { ExtractSourcePage } from "@/components/sources/ExtractSourcePage";
import { extractionRunIds } from "@/components/sources/sourceModel";

interface ExtractSearchParams {
  /** The individual extraction run to follow. */
  run?: string;
  /** The schema extraction run started with it. */
  schemaRun?: string;
}

const asId = (value: unknown) => (typeof value === "string" && value ? value : undefined);

function ExtractRoute() {
  const { sourceId } = Route.useParams();
  const { run, schemaRun } = Route.useSearch();
  const navigate = useNavigate();
  // The runs live in the URL, so leaving and coming back finds them again.
  const followRuns = (next: ExtractSearchParams) =>
    navigate({
      to: "/app/data/sources/$sourceId/extract",
      params: { sourceId },
      search: (prev) => ({ ...prev, ...next }),
      replace: true,
    });
  return (
    <ExtractSourcePage
      sourceId={sourceId}
      runId={run}
      schemaRunId={schemaRun}
      onRunsStarted={(runs) => followRuns(extractionRunIds(runs))}
      onReset={() => followRuns({ run: undefined, schemaRun: undefined })}
      onBack={() =>
        navigate({
          to: "/app/data/sources",
          search: (prev) => ({ ...prev, run: undefined, schemaRun: undefined }),
        })
      }
      onReview={(proposalId) =>
        navigate({ to: "/app/proposals/$proposalId", params: { proposalId } })
      }
    />
  );
}

export const Route = createFileRoute("/app/data/sources_/$sourceId/extract")({
  validateSearch: (search: Record<string, unknown>): ExtractSearchParams => ({
    run: asId(search.run),
    schemaRun: asId(search.schemaRun),
  }),
  component: ExtractRoute,
});
