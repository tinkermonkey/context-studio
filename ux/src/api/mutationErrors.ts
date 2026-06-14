import { ApiError } from "@/api/client/interceptors";

/** Pull the human-readable reason from the first rejected settled result. */
export function firstRejectionDetail(results: PromiseSettledResult<unknown>[]): string {
  const rejected = results.find((r): r is PromiseRejectedResult => r.status === "rejected");
  const reason = rejected?.reason;
  if (reason instanceof ApiError) return reason.detail;
  if (reason instanceof Error) return reason.message;
  return "An unexpected error occurred.";
}

/**
 * Build a delete-failure message that includes the backend's reason — e.g. the
 * cascade-block "Cannot delete X: it has N subclass(es)". Returned as the thrown
 * Error message; the calling surface renders it in a single error toast.
 */
export function deleteFailureMessage(
  results: PromiseSettledResult<unknown>[],
  totalCount: number,
): string {
  const failed = results.filter((r) => r.status === "rejected").length;
  const succeeded = totalCount - failed;
  const detail = firstRejectionDetail(results);
  return succeeded > 0 ? `${succeeded} deleted, ${failed} could not be removed. ${detail}` : detail;
}
