import { Command } from "lucide-react";
import { useCommandPaletteStore } from "@/stores/commandPalette";

interface TitlebarProps {
  workspaceName?: string;
}

export function Titlebar({ workspaceName = "Context Studio" }: TitlebarProps) {
  const openPalette = useCommandPaletteStore((s) => s.openPalette);

  return (
    <div className="titlebar">
      <div className="lights">
        <span className="l-close" title="Close" />
        <span className="l-min" title="Minimize" />
        <span className="l-max" title="Zoom" />
      </div>
      <button className="titlebar-ws" type="button">
        <span>{workspaceName}</span>
      </button>
      <div className="titlebar-spacer" />
      <button className="titlebar-btn" onClick={openPalette} type="button" title="Command palette (⌘K)">
        <Command size={12} strokeWidth={2} />
        <span className="kbd-mini">⌘K</span>
      </button>
    </div>
  );
}
