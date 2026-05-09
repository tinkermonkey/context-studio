import { createFileRoute } from "@tanstack/react-router";
import { Network, Database, Cpu, GitBranch } from "lucide-react";
import { StatTile } from "@/components/ui/StatTile";
import { Panel } from "@/components/ui/Panel";

export const Route = createFileRoute("/app/")({
  component: Dashboard,
});

function Dashboard() {
  return (
    <div>
      <div className="page-head">
        <div>
          <h1 style={{ fontSize: "var(--text-2xl)", fontWeight: 700, color: "var(--canvas-fg)", margin: 0 }}>
            Dashboard
          </h1>
          <p style={{ fontSize: "var(--text-sm)", color: "var(--canvas-fg-3)", marginTop: 4 }}>
            Knowledge graph overview
          </p>
        </div>
      </div>

      <div className="stat-grid" style={{ marginBottom: "var(--space-6)" }}>
        <StatTile label="Classes" value="22" color="cyan" sub="across 4 taxonomies" />
        <StatTile label="Individuals" value="267" color="violet" sub="indexed" />
        <StatTile label="Relationships" value="1,204" color="amber" sub="typed edges" />
        <StatTile label="Pipelines" value="11" color="emerald" sub="1 running" />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-6)" }}>
        <Panel title="Recent Activity">
          <div className="activity-list">
            {[
              { color: "#22D3EE", label: "New class added", sub: "PhotosyntheticOrganism · 2m ago" },
              { color: "#10B981", label: "Pipeline completed", sub: "pubmed_genes · 12m ago" },
              { color: "#A78BFA", label: "Relationship created", sub: "hasSubclass · 1h ago" },
              { color: "#F59E0B", label: "Individual updated", sub: "Arabidopsis thaliana · 2h ago" },
            ].map((item, i) => (
              <div key={i} className="activity-item">
                <span className="activity-dot" style={{ background: item.color }} />
                <div>
                  <div style={{ fontSize: "var(--text-sm)", color: "var(--canvas-fg)" }}>{item.label}</div>
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--canvas-fg-3)", fontFamily: "var(--mono)" }}>{item.sub}</div>
                </div>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Graph Health">
          <div className="kv" style={{ display: "grid", gridTemplateColumns: "120px 1fr", gap: "8px 16px" }}>
            {[
              ["Nodes", "289"],
              ["Edges", "1,204"],
              ["Orphans", "3"],
              ["Max depth", "6"],
              ["Avg degree", "4.2"],
            ].map(([k, v]) => (
              <>
                <dt key={k + "-k"} style={{ fontFamily: "var(--mono)", fontSize: "11px", color: "var(--canvas-fg-3)", textTransform: "uppercase", letterSpacing: "0.07em" }}>{k}</dt>
                <dd key={k + "-v"} style={{ margin: 0, fontFamily: "var(--mono)", fontSize: "13px", color: "var(--canvas-fg)" }}>{v}</dd>
              </>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}
