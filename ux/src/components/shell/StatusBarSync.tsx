import { Icon } from "@tinkermonkey/heimdall-ui";
import { useSyncStatus } from "@/api/hooks/versioning";
import { formatRelativeTime } from "@/utils/formatters";
import type { components } from "@/api/types";

type SyncStatusResponse = components["schemas"]["SyncStatusResponse"];

export interface StatusBarSyncState {
  label: string;
  /** True only when nothing is waiting to be pushed and a sync has happened. */
  inSync: boolean;
}

function latestSyncTime(status: SyncStatusResponse): string | null {
  const times = [status.last_pushed_at, status.last_pulled_at].filter((t): t is string =>
    Boolean(t),
  );
  if (times.length === 0) return null;
  return times.reduce((latest, t) => (Date.parse(t) > Date.parse(latest) ? t : latest));
}

/** What the status bar says about remote sync, from the sync status response. */
export function describeSyncState(status: SyncStatusResponse): StatusBarSyncState {
  if (!status.is_configured) return { label: "sync off", inSync: false };
  if (status.is_degraded) return { label: "sync degraded", inSync: false };
  if (status.unprocessed_count > 0) {
    return { label: `${status.unprocessed_count} unsynced`, inSync: false };
  }
  const lastSync = latestSyncTime(status);
  if (lastSync) return { label: `synced ${formatRelativeTime(lastSync)}`, inSync: true };
  return { label: "never synced", inSync: false };
}

/**
 * The status bar's sync item. It shows nothing until the sync status loads,
 * and nothing when the request fails: the bar only says what the app knows.
 */
export function StatusBarSync() {
  const { data: status } = useSyncStatus();
  if (!status) return null;

  const { label, inSync } = describeSyncState(status);
  return (
    <div className="statusbar__item" data-testid="statusbar-sync">
      {inSync && <Icon name="check" size={12} />}
      <span className="statusbar__label--mono">{label}</span>
    </div>
  );
}
