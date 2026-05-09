import { useState } from "react";
import { createFileRoute, Outlet } from "@tanstack/react-router";
import { Titlebar } from "@/components/shell/Titlebar";
import { Sidebar } from "@/components/shell/Sidebar";
import { Topbar } from "@/components/shell/Topbar";
import { Statusbar } from "@/components/shell/Statusbar";

export const Route = createFileRoute("/app")({
  component: AppShell,
});

function AppShell() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="desktop-frame">
      <Titlebar />
      <div className={`app-shell${collapsed ? " collapsed" : ""}`}>
        <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((v) => !v)} />
        <div className="workspace">
          <Topbar />
          <div className="canvas-area">
            <div className="canvas-scroll">
              <div className="canvas-inner">
                <Outlet />
              </div>
            </div>
          </div>
          <Statusbar />
        </div>
      </div>
    </div>
  );
}
