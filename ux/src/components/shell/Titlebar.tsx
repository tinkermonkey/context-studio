import { Command } from "lucide-react";
import { useCommandPaletteStore } from "@/stores/commandPalette";

interface TitlebarProps {
  workspaceName?: string;
}

export function Titlebar({ workspaceName = "Context Studio" }: TitlebarProps) {
  const openPalette = useCommandPaletteStore((s) => s.openPalette);

  return (
    <div className="titlebar">
      <div className="titlebar-lights">
        <span className="tl-dot tl-close" />
        <span className="tl-dot tl-min" />
        <span className="tl-dot tl-max" />
      </div>
      <button className="ws-btn" type="button">
        <span className="ws-name">{workspaceName}</span>
        <span className="ws-chevron">⌄</span>
      </button>
      <div className="titlebar-drag" />
      <button className="cmd-chip" onClick={openPalette} type="button">
        <Command size={10} strokeWidth={2} />
        <span>K</span>
      </button>
    </div>
  );
}
