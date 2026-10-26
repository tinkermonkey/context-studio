import { useCommandPaletteStore } from "@/stores/commandPalette";

/**
 * Topbar search `onSearch` handler: moves typed text into the command palette.
 *
 * Heimdall's Topbar calls `onSearch` on every change of its search input, which
 * is uncontrolled (no value prop). The text is handed to the palette, which
 * opens with it and takes focus, and the topbar input is cleared so nothing is
 * left behind there. Keystrokes typed before the palette input has focus
 * arrive here one at a time and are appended to the palette query.
 */
export function handTopbarSearchToPalette(value: string) {
  if (!value) return;
  useCommandPaletteStore.getState().typeIntoPalette(value);
  document.querySelectorAll<HTMLInputElement>("input.topbar__search").forEach((input) => {
    input.value = "";
  });
}
