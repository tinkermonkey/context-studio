/**
 * Case-insensitive pipeline run status check. The API reports status in lower
 * case ("completed"); callers historically compared against upper case.
 */
export function hasRunStatus(
  status: string | null | undefined,
  ...wanted: Array<"pending" | "running" | "completed" | "failed" | "cancelled">
): boolean {
  const normalized = (status ?? "").toLowerCase();
  return wanted.some((w) => w === normalized);
}
