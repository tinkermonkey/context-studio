import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Chip } from "@tinkermonkey/heimdall-ui";
import { useChanges } from "@/api/hooks/versioning";
import { formatRelativeTime } from "@/utils/formatters";
import { COPY } from "@/routes/app/versioning/copy";

function getOperationChip(operation: string) {
  const variantMap: Record<string, "cyan" | "violet" | "rose" | "neutral"> = {
    create: "cyan",
    update: "violet",
    delete: "rose",
  };
  const variant = variantMap[operation] ?? "neutral";
  return <Chip variant={variant}>{operation}</Chip>;
}

export function ChangeHistoryList() {
  const { data, isLoading, error, refetch } = useChanges();
  const changes = data?.events ?? [];

  if (isLoading) {
    return (
      <div className="stack-lg" data-testid="change-history-loading" aria-busy="true">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="skeleton change-history-skeleton" />
        ))}
      </div>
    );
  }

  if (error) {
    return <ErrorBanner error={error} onRetry={refetch} message={COPY.couldNotLoadChanges} />;
  }

  if (changes.length === 0) {
    return (
      <div className="change-history-empty" data-testid="change-history-empty" role="status">
        {COPY.noChanges}
      </div>
    );
  }

  return (
    <div
      className="change-history-list"
      data-testid="change-history-list"
      role="list"
      aria-label={COPY.changesHeading}
    >
      <div className="change-history-row change-history-header" aria-hidden="true">
        <div>{COPY.entityHeader}</div>
        <div>{COPY.typeHeader}</div>
        <div className="change-history-align-end">{COPY.timeHeader}</div>
      </div>

      {changes.map((change) => {
        const label =
          typeof change.new_state?.title === "string" ? change.new_state.title : change.entity_id;
        return (
          <div
            key={change.id}
            role="listitem"
            className="change-history-row"
            data-testid={`change-history-row-${change.id}`}
          >
            <div className="change-history-entity">
              {getOperationChip(change.operation)}
              <span className="change-history-label" title={label}>
                {label}
              </span>
            </div>

            <div>
              <Chip variant="neutral">{change.entity_type}</Chip>
            </div>

            <div className="change-history-time change-history-align-end">
              {formatRelativeTime(change.timestamp)}
            </div>
          </div>
        );
      })}
    </div>
  );
}
