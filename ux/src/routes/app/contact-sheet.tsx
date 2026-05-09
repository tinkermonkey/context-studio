import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Plus, Trash2, Edit2, ExternalLink, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { Input, Textarea, Select } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { Drawer } from "@/components/ui/Drawer";
import { Tabs } from "@/components/ui/Tabs";
import { StatTile } from "@/components/ui/StatTile";
import { Panel } from "@/components/ui/Panel";
import { ToastViewport, useToasts } from "@/components/ui/Toast";
import { useCanvasStore } from "@/stores/canvas";

export const Route = createFileRoute("/app/contact-sheet")({
  component: ContactSheet,
});

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={{ marginBottom: "var(--space-12)" }}>
      <h2 style={{
        fontFamily: "var(--mono)",
        fontSize: "var(--text-xs)",
        letterSpacing: "0.14em",
        textTransform: "uppercase",
        color: "var(--canvas-fg-3)",
        marginBottom: "var(--space-4)",
        paddingBottom: "var(--space-2)",
        borderBottom: "1px solid var(--canvas-bd)",
      }}>
        {title}
      </h2>
      {children}
    </section>
  );
}

function Row({ gap = 8, wrap = false, children }: { gap?: number; wrap?: boolean; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap, flexWrap: wrap ? "wrap" : undefined, marginBottom: "var(--space-4)" }}>
      {children}
    </div>
  );
}

export default function ContactSheet() {
  const [modalOpen, setModalOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("overview");
  const { darkCanvas, toggleDarkCanvas } = useCanvasStore();
  const { toasts, dismiss, toast } = useToasts();

  return (
    <div>
      <div className="page-head" style={{ marginBottom: "var(--space-8)" }}>
        <div>
          <h1 style={{ fontSize: "var(--text-2xl)", fontWeight: 700, color: "var(--canvas-fg)", margin: 0 }}>
            Contact Sheet
          </h1>
          <p style={{ fontSize: "var(--text-sm)", color: "var(--canvas-fg-3)", marginTop: 4 }}>
            Design system component gallery — for visual validation only
          </p>
        </div>
        <div className="page-actions">
          <Button variant="ghost" onClick={toggleDarkCanvas}>
            {darkCanvas ? "Light canvas" : "Dark canvas"}
          </Button>
        </div>
      </div>

      {/* ── Buttons ── */}
      <Section title="Buttons">
        <Row>
          <Button variant="primary">Primary</Button>
          <Button variant="accent">Accent</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="danger">Danger</Button>
        </Row>
        <Row>
          <Button variant="primary" size="sm">Primary sm</Button>
          <Button variant="accent" size="sm">Accent sm</Button>
          <Button variant="ghost" size="sm">Ghost sm</Button>
          <Button variant="danger" size="sm">Danger sm</Button>
        </Row>
        <Row>
          <Button variant="primary" disabled>Disabled</Button>
          <Button variant="ghost" size="sm">
            <Plus size={13} style={{ marginRight: 4 }} />
            With icon
          </Button>
          <Button variant="icon" size="sm" title="Edit">
            <Edit2 size={14} />
          </Button>
          <Button variant="icon" size="sm" title="Delete">
            <Trash2 size={14} />
          </Button>
        </Row>
      </Section>

      {/* ── Chips ── */}
      <Section title="Chips">
        <Row wrap>
          <Chip color="cyan">cyan</Chip>
          <Chip color="amber">amber</Chip>
          <Chip color="violet">violet</Chip>
          <Chip color="emerald">emerald</Chip>
          <Chip color="rose">rose</Chip>
          <Chip color="gray">gray</Chip>
          <Chip>default</Chip>
        </Row>
      </Section>

      {/* ── Stat Grid ── */}
      <Section title="Stat Tiles">
        <div className="stat-grid">
          <StatTile label="Classes" value="22" color="cyan" sub="4 taxonomies" />
          <StatTile label="Individuals" value="267" color="violet" sub="indexed" />
          <StatTile label="Relationships" value="1,204" color="amber" sub="typed edges" />
          <StatTile label="Pipelines" value="11" color="emerald" sub="1 running" />
        </div>
      </Section>

      {/* ── Tabs ── */}
      <Section title="Tabs">
        <Tabs
          tabs={[
            { id: "overview", label: "Overview" },
            { id: "properties", label: "Properties" },
            { id: "relationships", label: "Relationships" },
            { id: "history", label: "History" },
          ]}
          active={activeTab}
          onChange={setActiveTab}
        />
        <div style={{ padding: "var(--space-4) 0", color: "var(--canvas-fg-2)", fontSize: "var(--text-sm)" }}>
          Active tab: <strong>{activeTab}</strong>
        </div>
      </Section>

      {/* ── Inputs ── */}
      <Section title="Form Inputs">
        <div style={{ maxWidth: 480, display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          <div className="field">
            <div className="field-label">
              Label <span className="req">*</span>
              <span className="field-hint">Hint text here</span>
            </div>
            <Input placeholder="Placeholder text" />
          </div>
          <div className="field">
            <div className="field-label">Mono input</div>
            <Input mono placeholder="taxonomy:class:individual" />
          </div>
          <div className="field">
            <div className="field-label">Textarea</div>
            <Textarea placeholder="Description…" rows={3} />
          </div>
          <div className="field">
            <div className="field-label">Select</div>
            <Select>
              <option>Option A</option>
              <option>Option B</option>
              <option>Option C</option>
            </Select>
          </div>
          <div className="field">
            <div className="field-label">With error</div>
            <Input placeholder="Invalid value" style={{ borderColor: "var(--accent-rose)" }} />
            <div className="field-error">This field is required.</div>
          </div>
        </div>
      </Section>

      {/* ── Panel ── */}
      <Section title="Panel">
        <div style={{ maxWidth: 480 }}>
          <Panel title="Panel Title" actions={<Button variant="ghost" size="sm"><Plus size={12} /></Button>}>
            <p style={{ fontSize: "var(--text-sm)", color: "var(--canvas-fg-2)" }}>
              Panel content. This card has a header with an action button and body padding.
            </p>
          </Panel>
        </div>
      </Section>

      {/* ── Table ── */}
      <Section title="Table">
        <div className="table-wrap">
          <table className="t">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Status</th>
                <th>Count</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {[
                { name: "PhotosyntheticOrganism", type: "Class", status: "active", count: "42" },
                { name: "Arabidopsis thaliana", type: "Individual", status: "active", count: "—" },
                { name: "hasSubclass", type: "Relation", status: "draft", count: "18" },
              ].map((row) => (
                <tr key={row.name} className="row-link">
                  <td style={{ fontFamily: "var(--mono)", fontSize: "var(--text-xs)" }}>{row.name}</td>
                  <td><Chip color={row.type === "Class" ? "violet" : row.type === "Individual" ? "cyan" : "amber"}>{row.type}</Chip></td>
                  <td><Chip color={row.status === "active" ? "emerald" : "gray"}>{row.status}</Chip></td>
                  <td style={{ fontFamily: "var(--mono)" }}>{row.count}</td>
                  <td>
                    <Button variant="icon" size="sm" title="Open">
                      <ExternalLink size={12} />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {/* ── Hierarchy Tree ── */}
      <Section title="Hierarchy Tree (kg-tree)">
        <div className="panel" style={{ maxWidth: 360 }}>
          <div className="kg-tree">
            {[
              { label: "Life Sciences", kind: "TAX", depth: 0, domain: "life" },
              { label: "PlantOntology", kind: "SCH", depth: 1, domain: "life" },
              { label: "PhotosyntheticOrganism", kind: "CLS", depth: 2, domain: "life" },
              { label: "VascularPlant", kind: "CLS", depth: 3, domain: "life" },
              { label: "Climate Science", kind: "TAX", depth: 0, domain: "climate" },
              { label: "AtmosphericCO2", kind: "CLS", depth: 1, domain: "climate" },
            ].map((node, i) => (
              <div key={i} className="kg-row" data-depth={node.depth}>
                <span className="kg-node" data-domain={node.domain}>
                  <span className="kg-swatch" />
                  {node.label}
                </span>
                <span className="kg-kind">{node.kind}</span>
                <ChevronRight size={10} style={{ marginLeft: "auto", color: "var(--canvas-fg-4)" }} />
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* ── Pipeline Card ── */}
      <Section title="Pipeline Card">
        <div style={{ maxWidth: 480 }}>
          <div className="pipeline-card">
            <div className="pipeline-card-head">
              <span style={{ fontWeight: 600, color: "var(--canvas-fg)" }}>pubmed_genes</span>
              <Chip color="amber">running</Chip>
            </div>
            <div className="pipeline-card-flow">
              {[
                { label: "Fetch", kind: "fetch" },
                { label: "Extract", kind: "extract" },
                { label: "Embed", kind: "embed" },
                { label: "Graph", kind: "graph" },
              ].map((node, i, arr) => (
                <span key={node.label} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <span className="flow-node" data-kind={node.kind}>{node.label}</span>
                  {i < arr.length - 1 && <span className="flow-arrow">→</span>}
                </span>
              ))}
            </div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--canvas-fg-3)", fontFamily: "var(--mono)", marginTop: "var(--space-2)" }}>
              38% · ~4m remaining
            </div>
          </div>
        </div>
      </Section>

      {/* ── Toasts ── */}
      <Section title="Toasts">
        <Row>
          <Button variant="ghost" onClick={() => toast("success", "Saved successfully", "Class created and indexed.")}>
            Success toast
          </Button>
          <Button variant="ghost" onClick={() => toast("error", "EntityValidationError", "required field 'label' is missing")}>
            Error toast
          </Button>
        </Row>
      </Section>

      {/* ── Modal ── */}
      <Section title="Modal">
        <Row>
          <Button variant="ghost" onClick={() => setModalOpen(true)}>Open modal</Button>
        </Row>
        <Modal
          open={modalOpen}
          onClose={() => setModalOpen(false)}
          title="Create Class"
          subtitle="Define a new ontology class"
          footer={
            <>
              <span className="modal-foot-hint">⏎ to save · esc to cancel</span>
              <span style={{ flex: 1 }} />
              <Button variant="ghost" onClick={() => setModalOpen(false)}>Cancel</Button>
              <Button variant="primary">Create</Button>
            </>
          }
        >
          <div className="field">
            <div className="field-label">Label <span className="req">*</span></div>
            <Input placeholder="e.g. PhotosyntheticOrganism" />
          </div>
          <div className="field">
            <div className="field-label">Description</div>
            <Textarea placeholder="A brief definition…" rows={3} />
          </div>
        </Modal>
      </Section>

      {/* ── Drawer ── */}
      <Section title="Drawer">
        <Row>
          <Button variant="ghost" onClick={() => setDrawerOpen(true)}>Open drawer</Button>
        </Row>
        <Drawer
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          title="Arabidopsis thaliana"
        >
          <dl className="kv">
            <dt>Type</dt><dd><Chip color="violet">Individual</Chip></dd>
            <dt>ID</dt><dd style={{ fontFamily: "var(--mono)", fontSize: "11px" }}>ind_0042</dd>
            <dt>Class</dt><dd>VascularPlant</dd>
            <dt>Taxonomy</dt><dd>PlantOntology</dd>
          </dl>
        </Drawer>
      </Section>

      {/* ── Intent banners ── */}
      <Section title="Intent States">
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", maxWidth: 480 }}>
          {(["success", "warning", "failure", "info"] as const).map((intent) => (
            <div key={intent} style={{
              display: "flex", alignItems: "center", gap: "var(--space-3)",
              padding: "10px 14px", borderRadius: "var(--radius-md)",
              background: `var(--intent-${intent}-bg)`,
              border: `1px solid var(--intent-${intent}-bd)`,
              color: `var(--intent-${intent}-fg)`,
              fontSize: "var(--text-sm)",
            }}>
              <strong style={{ textTransform: "capitalize" }}>{intent}</strong>
              — intent state banner
            </div>
          ))}
        </div>
      </Section>

      <ToastViewport toasts={toasts} onDismiss={dismiss} />
    </div>
  );
}
