import { useEffect } from "react";
import type { EntitySurfaceHandle } from "@/components/crud/EntitySurface";
import type { EntityType, FormValues } from "@/components/crud/CreateDrawer";

declare global {
  interface Window {
    __CS_PENDING?: {
      type: EntityType;
      ctx: Partial<FormValues>;
      identifierDirty?: boolean;
    };
  }
}

export function usePendingCreate(
  type: EntityType,
  surfaceRef: React.RefObject<EntitySurfaceHandle | null>,
): void {
  useEffect(() => {
    const pending = window.__CS_PENDING;
    if (pending && pending.type === type) {
      requestAnimationFrame(() => {
        if (surfaceRef.current) {
          window.__CS_PENDING = undefined;
          surfaceRef.current.startCreate(pending.ctx, pending.identifierDirty);
        }
      });
    }
    // intentionally runs once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
