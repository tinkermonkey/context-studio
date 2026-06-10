import { useEffect } from "react";
import type { EntitySurfaceHandle } from "@/components/crud/EntitySurface";
import type { FormValues } from "@/components/crud/CreateDrawer";

declare global {
  interface Window {
    __CS_PENDING?: {
      type: string;
      ctx: Partial<FormValues>;
      identifierDirty?: boolean;
    };
  }
}

export function usePendingCreate(
  type: string,
  surfaceRef: React.RefObject<EntitySurfaceHandle | null>,
): void {
  useEffect(() => {
    const pending = window.__CS_PENDING;
    if (pending && pending.type === type) {
      window.__CS_PENDING = undefined;
      requestAnimationFrame(() => {
        surfaceRef.current?.startCreate(pending.ctx);
      });
    }
    // intentionally runs once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
