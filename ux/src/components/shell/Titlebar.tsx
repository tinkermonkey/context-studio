import { Folder, ChevronDown, Search } from "lucide-react";
import type { TitlebarProps } from "@tinkermonkey/heimdall-ui";
import { useCommandPaletteStore } from "@/stores/commandPalette";

export function buildTitlebarProps(
  workspaceName = "Context Studio",
  workspacePath = "~/Projects/context-studio"
): TitlebarProps {
  const openPalette = useCommandPaletteStore((s) => s.openPalette);

  const left = (
    <div className="titlebar-app">
      <span className="titlebar-app-name">{workspaceName}</span>
      <span className="titlebar-app-sep">—</span>
      <button className="titlebar-ws" type="button" title="Switch workspace">
        <Folder size={12} />
        <span>{workspacePath}</span>
        <ChevronDown size={10} />
      </button>
    </div>
  );

  const right = (
    <div className="titlebar-actions">
      <button
        className="titlebar-btn"
        onClick={() => openPalette()}
        type="button"
        title="Command palette (⌘K)"
      >
        <Search size={12} />
        <span className="kbd-mini">⌘K</span>
      </button>
    </div>
  );

  return { left, right };
}
