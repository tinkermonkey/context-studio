import { useEffect, useState } from "react";
import { Network, CheckCircle } from "lucide-react";

export function Statusbar() {
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setTick((v) => v + 1), 2200);
    return () => clearInterval(t);
  }, []);

  const cpu = 12 + (tick % 5) * 3;
  const mem = 412 + (tick % 7) * 11;

  return (
    <div className="statusbar">
      <div className="statusbar-group">
        <span className="sb-item">
          <span className="status-pulse" />
          <span>api server</span>
          <span className="sb-mono">:8100</span>
        </span>
        <span className="sb-divider" />
        <span className="sb-item">
          <Network size={11} />
          <span>knowledge graph ready</span>
        </span>
      </div>
      <div className="statusbar-group">
        <span className="sb-item">
          <span className="sb-mono">cpu {cpu}%</span>
        </span>
        <span className="sb-divider" />
        <span className="sb-item">
          <span className="sb-mono">mem {mem} MB</span>
        </span>
        <span className="sb-divider" />
        <span className="sb-item">
          <span className="sb-mono">UTF-8 · LF</span>
        </span>
        <span className="sb-divider" />
        <span className="sb-item">
          <CheckCircle size={11} />
          <span className="sb-mono">synced 2m ago</span>
        </span>
      </div>
    </div>
  );
}
