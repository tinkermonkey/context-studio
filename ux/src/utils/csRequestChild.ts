import type { EntityType, FormValues } from "@/components/crud/CreateDrawer";

/**
 * Sets a pending create context that the target route will consume on mount via usePendingCreate.
 * Call this from a row-menu "Add child" action before navigating to the child-entity page.
 */
export function csRequestChild(
  onNav: () => void,
  type: EntityType,
  ctx: Partial<FormValues>,
  identifierDirty?: boolean,
): void {
  window.__CS_PENDING = { type, ctx, identifierDirty };
  onNav();
}
