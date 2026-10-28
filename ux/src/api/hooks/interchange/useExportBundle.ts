import { useMutation } from "@tanstack/react-query";
import { interchangeService } from "@/api/services/interchange";
import { downloadJson } from "@/lib/download";

/**
 * Export a taxonomy as a bundle and download it as `<identifier>.bundle.json`.
 * The caller shows the error toast, so the global one is skipped.
 */
export function useExportBundle() {
  return useMutation({
    mutationFn: (taxonomyId: string) => interchangeService.exportBundle(taxonomyId),
    onSuccess: (bundle) => downloadJson(`${bundle.taxonomy.identifier}.bundle.json`, bundle),
    meta: { skipGlobalErrorToast: true },
  });
}
