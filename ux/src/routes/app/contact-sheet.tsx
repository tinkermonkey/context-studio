/**
 * Contact Sheet: Visual Regression Reference
 *
 * This component is the canonical visual reference for the design system.
 * All component variants and states must be represented here.
 * Changes to component styling should be validated against this sheet first.
 */

import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Plus, Trash2, Edit2, ExternalLink, Globe, Cpu, GitMerge, Database } from "lucide-react";
import {
  Button,
  TextInput as Input,
  TextArea as Textarea,
  Select,
  TabBar,
  StatGrid,
  Table,
  Chip,
  Modal,
  PageHeader,
  StatTile,
  Panel,
  FilterBar,
} from "@tinkermonkey/heimdall-ui";
import { Drawer } from "@/components/ui/Drawer";
import { useToasts } from "@/components/ui/Toast";
import { useCanvasStore } from "@/stores/canvas";
import { SchemaTable, type Column } from "@/components/schema/SchemaTable";
import "./contact-sheet.css";

export const Route = createFileRoute("/app/contact-sheet")({
  component: ContactSheet,
});

function Section({
  title,
  testid,
  children,
}: {
  title: string;
  testid?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="contact-sheet-section" data-testid={testid}>
      <h2>{title}</h2>
      {children}
    </section>
  );
}

function Row({ wrap = false, children }: { wrap?: boolean; children: React.ReactNode }) {
  const className = `contact-sheet-row${wrap ? " wrap" : ""}`;
  return <div className={className}>{children}</div>;
}

interface MockEntity {
  id: string;
  title: string;
  description?: string;
}

export default function ContactSheet() {
  const [modalOpen, setModalOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedSchemaId, setSelectedSchemaId] = useState<string | undefined>();
  const [searchFilter, setSearchFilter] = useState("");
  const [activeTab, setActiveTab] = useState("overview");
  const { darkCanvas, toggleDarkCanvas } = useCanvasStore();
  const { toast } = useToasts();

  const mockSchemaData: MockEntity[] = [
    { id: "1", title: "Organism", description: "All living entities" },
    { id: "2", title: "Plant", description: "Photosynthetic organisms" },
    { id: "3", title: "Animal", description: "Heterotrophic organisms" },
  ];

  const schemaColumns: Column<MockEntity>[] = [
    {
      key: "id",
      label: "ID",
      render: (value) => <span className="mono">{value as string}</span>,
    },
    {
      key: "title",
      label: "Title",
      render: (value) => <span className="row-link">{value as string}</span>,
    },
    {
      key: "description",
      label: "Description",
      render: (value) => (
        <span className="contact-sheet-description-text">{value as string}</span>
      ),
    },
  ];

  const filteredSchemaData = mockSchemaData.filter(
    (item) =>
      item.title.toLowerCase().includes(searchFilter.toLowerCase()) ||
      item.description?.toLowerCase().includes(searchFilter.toLowerCase()),
  );

  const selectedEntity = mockSchemaData.find((item) => item.id === selectedSchemaId);

  return (
    <div>
      <PageHeader
        eyebrow="Design System"
        title="Contact Sheet"
        subtitle="Design system component gallery — for visual validation only"
        actions={
          <Button
            variant="ghost"
            onClick={toggleDarkCanvas}
            data-testid="contact-sheet-canvas-toggle"
          >
            {darkCanvas ? "Light canvas" : "Dark canvas"}
          </Button>
        }
      />

      {/* ── Buttons ── */}
      <Section title="Buttons" testid="contact-sheet-buttons">
        <Row>
          <Button variant="primary">Primary</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="danger">Danger</Button>
        </Row>
        <Row>
          <Button variant="primary">
            Primary sm
          </Button>
          <Button variant="secondary">
            Secondary sm
          </Button>
          <Button variant="ghost">
            Ghost sm
          </Button>
          <Button variant="danger">
            Danger sm
          </Button>
        </Row>
        <Row>
          <Button variant="primary" disabled>
            Disabled
          </Button>
          <Button variant="ghost">
            <Plus size={13} className="contact-sheet-icon-spacing" />
            With icon
          </Button>
          <Button variant="ghost" title="Edit">
            <Edit2 size={14} />
          </Button>
          <Button variant="ghost" title="Delete">
            <Trash2 size={14} />
          </Button>
        </Row>
      </Section>

      {/* ── Chips ── */}
      <Section title="Chips" testid="contact-sheet-chips">
        <Row wrap>
          <Chip variant="cyan">cyan</Chip>
          <Chip variant="amber">amber</Chip>
          <Chip variant="violet">violet</Chip>
          <Chip variant="emerald">emerald</Chip>
          <Chip variant="rose">rose</Chip>
          <Chip variant="neutral">gray</Chip>
          <Chip>default</Chip>
        </Row>
      </Section>

      {/* ── Stat Grid ── */}
      <Section title="Stat Tiles" testid="contact-sheet-stat-tiles">
        <StatGrid>
          <StatTile label="Classes" value="22" color="cyan" />
          <StatTile label="Individuals" value="267" color="violet" />
          <StatTile label="Relationships" value="1,204" color="amber" />
          <StatTile label="Pipelines" value="11" color="emerald" />
        </StatGrid>
      </Section>

      {/* ── Tabs ── */}
      <Section title="Tabs" testid="contact-sheet-tabs">
        <TabBar
          tabs={[
            { id: "overview", label: "Overview" },
            { id: "properties", label: "Properties" },
            { id: "relationships", label: "Relationships" },
            { id: "history", label: "History" },
          ]}
          activeTabId={activeTab}
          onSelectTab={setActiveTab}
        />
        <div className="contact-sheet-tab-content">
          Active tab: <strong>{activeTab}</strong>
        </div>
      </Section>

      {/* ── Inputs ── */}
      <Section title="Form Inputs" testid="contact-sheet-form-inputs">
        <div className="contact-sheet-form-container">
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
            <Input placeholder="Invalid value" className="contact-sheet-input-error" />
            <div className="field-error">This field is required.</div>
          </div>
        </div>
      </Section>

      {/* ── Panel ── */}
      <Section title="Panel" testid="contact-sheet-panel">
        <div className="contact-sheet-panel-container">
          <Panel title="Panel Title">
            <p className="contact-sheet-description-text">
              Panel content. This card has a header with an action button and body padding.
            </p>
          </Panel>
        </div>
      </Section>

      {/* ── Table ── */}
      <Section title="Table" testid="contact-sheet-table">
        <div className="table-wrap">
          <Table
            columns={[
              {
                key: "name",
                label: "Name",
                render: (value) => <span className="contact-sheet-table-mono">{value}</span>,
              },
              {
                key: "type",
                label: "Type",
                render: (value) => (
                  <Chip variant={value === "Class" ? "violet" : value === "Individual" ? "cyan" : "amber"}
                  >
                    {value}
                  </Chip>
                ),
              },
              {
                key: "status",
                label: "Status",
                render: (value) => (
                  <Chip variant={value === "active" ? "emerald" : "neutral"}>{value}</Chip>
                ),
              },
              {
                key: "count",
                label: "Count",
                render: (value) => <span className="contact-sheet-table-mono-col">{value}</span>,
              },
              {
                key: "action",
                label: "",
                render: () => (
                  <Button variant="ghost" title="Open">
                    <ExternalLink size={12} />
                  </Button>
                ),
              },
            ]}
            data={[
              {
                id: "1",
                name: "PhotosyntheticOrganism",
                type: "Class",
                status: "active",
                count: "42",
                action: null,
              },
              {
                id: "2",
                name: "Arabidopsis thaliana",
                type: "Individual",
                status: "active",
                count: "—",
                action: null,
              },
              {
                id: "3",
                name: "hasSubclass",
                type: "Relation",
                status: "draft",
                count: "18",
                action: null,
              },
            ]}
            rowKey="id"
            className="t"
          />
        </div>
      </Section>

      {/* ── Hierarchy Tree ── */}
      <Section title="Hierarchy Tree (kg-tree)" testid="contact-sheet-hierarchy-tree">
        <div className="panel contact-sheet-hierarchy-container">
          <div className="kg-tree">
            {[
              {
                label: "life.thing",
                badge: "root",
                depth: 0,
                domain: "life",
                desc: "All biological entities",
              },
              {
                label: "life.organism",
                badge: "1,247",
                depth: 1,
                domain: "life",
                desc: "Any living organism",
              },
              {
                label: "life.organism.mammal",
                badge: "312",
                depth: 2,
                domain: "life",
                desc: "Warm-blooded vertebrates",
                selected: true,
              },
              {
                label: "climate.station",
                badge: "89",
                depth: 0,
                domain: "climate",
                desc: "Weather monitoring stations",
              },
            ].map((node, i) => (
              <div key={i} className="kg-row">
                <div className="kg-cell kg-cell-l" data-depth={node.depth}>
                  <span
                    className={`kg-node${node.selected ? "selected" : ""}`}
                    data-domain={node.domain}
                  >
                    <span className="swatch" />
                    {node.label}
                    <span className="badge-tiny">{node.badge}</span>
                  </span>
                </div>
                <div className="kg-desc">{node.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* ── Pipeline Card ── */}
      <Section title="Pipeline Card" testid="contact-sheet-pipeline-card">
        <div className="contact-sheet-pipeline-container">
          <div className="pipeline-card">
            <div className="pipeline-card-head">
              <div>
                <div className="name">Ingest organisms · GBIF</div>
                <div className="desc">
                  Pull species records, normalize names, write to life.organism
                </div>
              </div>
              <Chip variant="amber">running</Chip>
            </div>
            <div className="pipeline-card-flow">
              {[
                { label: "GBIF API", sub: "source", kind: "source", icon: <Globe size={11} /> },
                { label: "Extract", sub: "12 fields", kind: "extract", icon: <Cpu size={11} /> },
                {
                  label: "Resolve",
                  sub: "match by name",
                  kind: "resolve",
                  icon: <GitMerge size={11} />,
                },
                {
                  label: "Write",
                  sub: "life.organism",
                  kind: "write",
                  icon: <Database size={11} />,
                },
              ].map((node, i, arr) => (
                <span key={node.kind} className="contact-sheet-pipeline-flow-wrapper">
                  <div className="flow-node" data-kind={node.kind}>
                    <div className="ic">{node.icon}</div>
                    <div>
                      <div className="name">{node.label}</div>
                      <div className="sub">{node.sub}</div>
                    </div>
                  </div>
                  {i < arr.length - 1 && <div className="flow-arrow" />}
                </span>
              ))}
            </div>
            <div className="pipeline-card-foot">
              <div className="stat-item">
                <div className="l">Last run</div>
                <div className="v">2m ago</div>
              </div>
              <div className="stat-item">
                <div className="l">Records</div>
                <div className="v">12,480</div>
              </div>
              <div className="stat-item">
                <div className="l">Status</div>
                <div className="v contact-sheet-pipeline-status">38% running</div>
              </div>
            </div>
          </div>
        </div>
      </Section>

      {/* ── Toasts ── */}
      <Section title="Toasts" testid="contact-sheet-toasts">
        <Row>
          <Button
            variant="ghost"
            onClick={() => toast("success", "Saved successfully", "Class created and indexed.")}
          >
            Success toast
          </Button>
          <Button
            variant="ghost"
            onClick={() =>
              toast("error", "EntityValidationError", "required field 'label' is missing")
            }
          >
            Error toast
          </Button>
        </Row>
      </Section>

      {/* ── Modal ── */}
      <Section title="Modal" testid="contact-sheet-modal">
        <Row>
          <Button variant="ghost" onClick={() => setModalOpen(true)}>
            Open modal
          </Button>
        </Row>
        <Modal isOpen={modalOpen}
          onClose={() => setModalOpen(false)}
          title="Create Class"
          subtitle="Define a new ontology class"
          footer={
            <>
              <span className="modal-foot-hint">⏎ to save · esc to cancel</span>
              <span className="grow" />
              <Button variant="ghost" onClick={() => setModalOpen(false)}>
                Cancel
              </Button>
              <Button variant="primary">Create</Button>
            </>
          }
        >
          <div className="field">
            <div className="field-label">
              Label <span className="req">*</span>
            </div>
            <Input placeholder="e.g. PhotosyntheticOrganism" />
          </div>
          <div className="field">
            <div className="field-label">Description</div>
            <Textarea placeholder="A brief definition…" rows={3} />
          </div>
        </Modal>
      </Section>

      {/* ── Drawer ── */}
      <Section title="Drawer" testid="contact-sheet-drawer">
        <Row>
          <Button variant="ghost" onClick={() => setDrawerOpen(true)}>
            Open drawer
          </Button>
        </Row>
        <Drawer open={drawerOpen} onClose={() => setDrawerOpen(false)} title="Arabidopsis thaliana">
          <dl className="kv contact-sheet-kv-list">
            <dt className="contact-sheet-kv-label">Type</dt>
            <dd className="contact-sheet-kv-value">
              <Chip variant="violet">Individual</Chip>
            </dd>
            <dt className="contact-sheet-kv-label">ID</dt>
            <dd className="contact-sheet-kv-value contact-sheet-kv-value-mono">ind_0042</dd>
            <dt className="contact-sheet-kv-label">Class</dt>
            <dd className="contact-sheet-kv-value">VascularPlant</dd>
            <dt className="contact-sheet-kv-label">Taxonomy</dt>
            <dd className="contact-sheet-kv-value">PlantOntology</dd>
          </dl>
        </Drawer>
      </Section>

      {/* ── Schema Components ── */}
      <Section title="Schema Components" testid="contact-sheet-schema-components">
        <div className="contact-sheet-schema-intro">
          <h3>Filter Bar + Table + Drawer Layout</h3>
          <div className="contact-sheet-schema-table-container">
            <FilterBar
              onSearchChange={setSearchFilter}
              searchPlaceholder="Search by title or description…"
              showingCount={filteredSchemaData.length}
              totalCount={mockSchemaData.length}
            />
            <div className="contact-sheet-schema-table-wrapper">
              <SchemaTable
                columns={schemaColumns}
                data={filteredSchemaData}
                onRowSelect={(id) => setSelectedSchemaId(id)}
                selectedId={selectedSchemaId}
              />
            </div>
          </div>
        </div>
        {selectedEntity && (
          <div className="contact-sheet-schema-drawer-demo">
            <h4>SchemaDrawer (selected: {selectedEntity.title})</h4>
            <Drawer
              open={!!selectedEntity}
              onClose={() => setSelectedSchemaId(undefined)}
              title={selectedEntity.title}
              autosaveState="idle"
              isDirty={false}
            >
              <dl className="kv contact-sheet-kv-list">
                <dt className="contact-sheet-kv-label">Title</dt>
                <dd className="contact-sheet-kv-value">{selectedEntity.title}</dd>
                <dt className="contact-sheet-kv-label">ID</dt>
                <dd className="contact-sheet-kv-value contact-sheet-kv-value-mono">
                  {selectedEntity.id}
                </dd>
                <dt className="contact-sheet-kv-label">Description</dt>
                <dd className="contact-sheet-kv-value">{selectedEntity.description}</dd>
              </dl>
            </Drawer>
          </div>
        )}
      </Section>

      {/* ── Intent banners ── */}
      <Section title="Intent States" testid="contact-sheet-intent-states">
        <div className="contact-sheet-intent-states-container">
          {(["success", "warning", "failure", "info"] as const).map((intent) => (
            <div
              key={intent}
              className={`contact-sheet-intent-state-item contact-sheet-intent-${intent}`}
            >
              <strong>{intent}</strong>— intent state banner
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}
