import { useMutation } from "@tanstack/react-query";
import { ApiError } from "@/api/client/interceptors";
import { interchangeService } from "@/api/services/interchange";
import { useToasts } from "@/components/ui/Toast";
import { downloadJson } from "@/lib/download";

export const EXPORT_BUNDLE_FAILED = "Bundle export failed";

/**
 * Export a taxonomy as a bundle and download it as `<identifier>.bundle.json`.
 * The hook shows its own titled error toast (it runs even if the page unmounts
 * mid-export), so the global one is skipped.
 */
export function useExportBundle() {
  const { toast } = useToasts();
  return useMutation({
    mutationFn: (taxonomyId: string) => interchangeService.exportBundle(taxonomyId),
    onSuccess: (bundle) => downloadJson(`${bundle.taxonomy.identifier}.bundle.json`, bundle),
    onError: (err) =>
      toast("error", EXPORT_BUNDLE_FAILED, err instanceof ApiError ? err.detail : err.message),
    meta: { skipGlobalErrorToast: true },
  });
}
