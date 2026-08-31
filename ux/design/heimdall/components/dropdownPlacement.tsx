/**
 * Shared placement vocabulary for floating dropdown panels
 * (Select, FilterDropdown, EntityPicker, RowMenu).
 *
 * `start` / `end` refer to the trigger's edge the panel aligns with on the
 * horizontal axis. `top` / `bottom` is the vertical side the panel opens to.
 *
 *  bottom-start (default) → panel hangs below, left edge aligned with trigger
 *  bottom-end             → panel hangs below, right edge aligned with trigger
 *  top-start              → panel rises above, left edge aligned with trigger
 *  top-end                → panel rises above, right edge aligned with trigger
 */
type DropdownPlacement = "bottom-start" | "bottom-end" | "top-start" | "top-end";

const dropdownPlacementClass = (placement: DropdownPlacement = "bottom-start"): string =>
  `dropdown-panel--placement-${placement}`;

// --- Babel-standalone: expose runtime values to window ---
window.dropdownPlacementClass = dropdownPlacementClass;
