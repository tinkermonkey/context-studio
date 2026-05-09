import { Folder, ChevronDown, Search } from "lucide-react";
import { useCommandPaletteStore } from "@/stores/commandPalette";

interface TitlebarProps {
  workspaceName?: string;
  workspacePath?: string;
}

export function Titlebar({ workspaceName = "Context Studio", workspacePath = "~/Projects/context-studio" }: TitlebarProps) {
  const openPalette = useCommandPaletteStore((s) => s.openPalette);

  return (
    <div className="titlebar">
      <div className="lights">
        <span className="l-close" title="Close" />
        <span className="l-min" title="Minimize" />
        <span className="l-max" title="Zoom" />
      </div>
      <div className="titlebar-app">
        <span className="titlebar-app-name">{workspaceName}</span>
        <span className="titlebar-app-sep">—</span>
        <button className="titlebar-ws" type="button" title="Switch workspace">
          <Folder size={12} />
          <span>{workspacePath}</span>
          <ChevronDown size={10} />
        </button>
      </div>
      <div className="titlebar-spacer" />
      <div className="titlebar-actions">
        <button className="titlebar-btn" onClick={openPalette} type="button" title="Command palette (⌘K)">
          <Search size={12} />
          <span className="kbd-mini">⌘K</span>
        </button>
      </div>
    </div>
  );
}
