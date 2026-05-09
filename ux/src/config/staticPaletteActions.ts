import type { PaletteAction } from "@/stores/commandPalette";

export function createStaticPaletteActions(): PaletteAction[] {
  return [
    {
      id: "show-help",
      label: "Show Keyboard Shortcuts",
      description: "View command palette help",
      onSelect: () => {
        window.dispatchEvent(new CustomEvent("show-command-palette-help"));
      },
    },
  ];
}
