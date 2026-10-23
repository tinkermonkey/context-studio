// =========================================================================
// Context Studio v2 — pages composed from REAL @tinkermonkey/heimdall-ui React
// components (Sidebar, Topbar, StatGrid, StatTile, Panel, HierarchyRow,
// HierarchyTree, ActivityTimeline, PipelineCard, Table, Chip, Button, Icon,
// Modal, CommandPalette, InspectorPanel, KVGrid, VersionPill, PageHeader,
// FilterDropdown, TabBar, FormCallout, Field, TextInput, Select).
// Every JSX tag here maps 1:1 to the import the dev team would write:
//     import { StatGrid, StatTile } from '@tinkermonkey/heimdall-ui'
// =========================================================================

// ---- shared helpers -----------------------------------------------------
const D = () => window.CS_DATA;

function asHierarchyDomain(d) {
  // Heimdall HierarchyRow knows 'life' | 'climate' | 'software' | 'default'
  return d || "default";
}

// =========================================================================
// Dashboard page
// =========================================================================
function CSDashboard({ onNav }) {
  const data = D();
  const totalClasses = data.classes.length;
  const totalIndividuals = data.individuals.length + 251;
  const running = data.pipelines.filter((p) => p.status === "running").length;
  const failed = data.pipelines.filter((p) => p.status === "failed").length;

  // Hierarchy panel state — fold/unfold taxonomies and schemes
  const [open, setOpen] = useState(() => ({
    [data.taxonomies[0]?.id]: true,
    [data.concept_schemes[0]?.id]: true,
  }));
  const [selClass, setSelClass] = useState("cls_gene");
  const toggle = (id) => setOpen((o) => ({ ...o, [id]: !o[id] }));

  // ActivityTimeline events — adapt CS_DATA.activity (which has relative "when" strings)
  // to the Heimdall API (which takes Date timestamps and computes the relative).
  const tsFor = (when) => {
    const now = Date.now();
    const m = when && when.match(/(\d+)\s*(m|h|d)/i);
    if (!m) return new Date(now);
    const n = parseInt(m[1], 10);
    const unit = m[2].toLowerCase();
    return new Date(now - n * (unit === "m" ? 60_000 : unit === "h" ? 3_600_000 : 86_400_000));
  };
  const activityEvents = data.activity.slice(0, 7).map((a, i) => ({
    id: `act-${i}`,
    type:
      a.kind === "create"
        ? "create"
        : a.kind === "update"
          ? "update"
          : a.kind === "delete"
            ? "delete"
            : "run",
    kind: a.kind,
    kindLabel: a.kind,
    subject: `${a.what} ${a.subject}`,
    meta: `${a.meta} · by ${a.who}`,
    timestamp: tsFor(a.when),
  }));

  // Map CS_DATA pipelines → Heimdall Pipeline shape
  const ICON_REMAP = { reference: "link", sparkle: "zap", doc: "file", database: "hardDrive" };
  const toHeimdallPipeline = (p) => ({
    id: p.id,
    name: p.name,
    description: p.description,
    status: p.status,
    target: p.target,
    tags: p.tags,
    lastRun: p.lastRun,
    flow: p.flow.map((s, i) => ({
      id: `${p.id}-${i}`,
      name: s.name,
      label: s.kind,
      icon: ICON_REMAP[s.ic] || s.ic,
    })),
    recent: p.recent || { ingested: 0, created: 0, updated: 0, errors: 0 },
  });

  return (
    <div data-screen-label="01 Dashboard">
      {/* Page meta row — workspace chip + sync time + daemon health.
          Renders ABOVE <PageHeader>; eyebrow prop intentionally omitted.
          Library fix: widen PageHeader.eyebrow to ReactNode so this row
          can live inside the primitive. See HEIMDALL_DESIGN_SYSTEM_FEEDBACK.md §3. */}
      <div className="cs-page-meta">
        <Chip variant="amber">workspace · {data.workspace.name}</Chip>
        <span>last sync {data.workspace.last_sync}</span>
        <span className="cs-page-meta__sep">·</span>
        <span className="cs-page-meta__health">graph daemon healthy</span>
      </div>

      <PageHeader
        title="Dashboard"
        idChip={`/workspace/${data.workspace.name}`}
        subtitle="Curate knowledge graphs for retrieval-augmented generation and agents. Taxonomies group concept schemes; concept schemes hold classes; classes hold individuals."
        actions={
          <>
            <Button variant="ghost" onClick={() => {}}>
              <Icon name="reload" size={13} /> Refresh
            </Button>
            <Button variant="primary" onClick={() => onNav("pipelines/all")}>
              <Icon name="plus" size={13} /> New pipeline run
            </Button>
          </>
        }
      />

      <div style={{ height: 18 }} />

      <StatGrid columns={4}>
        <StatTile
          label="TAXONOMIES"
          value={data.taxonomies.length}
          color="cyan"
          icon="schema"
          meta="3 active · 0 archived"
          sparkData={data.sparks.taxonomies}
        />
        <StatTile
          label="CLASSES"
          value={totalClasses}
          color="violet"
          icon="schema"
          delta={{ value: 4, label: "this week", direction: "up" }}
          sparkData={data.sparks.classes}
        />
        <StatTile
          label="INDIVIDUALS"
          value={totalIndividuals.toLocaleString()}
          color="emerald"
          icon="data"
          delta={{ value: 38, label: "last run · 412 ingested", direction: "up" }}
          sparkData={data.sparks.individuals}
        />
        <StatTile
          label="PIPELINES"
          value={`${running}/${data.pipelines.length}`}
          color="amber"
          icon="pipeline"
          meta={`${running} running · ${failed} failed`}
          sparkData={data.sparks.ingestRate}
        />
      </StatGrid>

      <div style={{ height: 18 }} />

      {/* Hierarchy + Activity */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 380px", gap: 14 }}>
        <Panel
          title="Knowledge graph structure"
          headerAction={
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  color: "rgb(var(--canvas-fg-3))",
                  whiteSpace: "nowrap",
                }}
              >
                {data.taxonomies.length} tax · {data.concept_schemes.length} sch · {totalClasses}{" "}
                cls
              </span>
              <Button variant="ghost" size="sm" onClick={() => onNav("schema/classes")}>
                Open <Icon name="arrowRight" size={11} />
              </Button>
            </div>
          }
          noPadding
        >
          <div style={{ maxHeight: 460, overflow: "auto", padding: "6px 0" }}>
            <HierarchyTree>
              {data.taxonomies.map((tax) => {
                const schemes = data.concept_schemes.filter((s) => s.taxonomy_id === tax.id);
                const taxOpen = open[tax.id];
                return (
                  <React.Fragment key={tax.id}>
                    <HierarchyRow
                      depth={0}
                      domain={asHierarchyDomain(tax.domain)}
                      kind="taxonomy"
                      label={tax.title}
                      meta={tax.id}
                      description={tax.description}
                      onSelect={() => toggle(tax.id)}
                    />
                    {taxOpen &&
                      schemes.map((sch) => {
                        const cls = data.classes.filter((c) => c.concept_scheme_id === sch.id);
                        const schOpen = open[sch.id];
                        return (
                          <React.Fragment key={sch.id}>
                            <HierarchyRow
                              depth={1}
                              domain={asHierarchyDomain(sch.domain)}
                              kind="scheme"
                              label={sch.title}
                              meta={sch.id}
                              description={sch.description}
                              onSelect={() => toggle(sch.id)}
                            />
                            {schOpen &&
                              cls.map((c) => (
                                <HierarchyRow
                                  key={c.id}
                                  depth={2}
                                  domain={asHierarchyDomain(c.domain)}
                                  kind="class"
                                  label={c.title}
                                  meta={c.id}
                                  description={c.description}
                                  selected={selClass === c.id}
                                  onSelect={() => setSelClass(c.id)}
                                />
                              ))}
                          </React.Fragment>
                        );
                      })}
                  </React.Fragment>
                );
              })}
            </HierarchyTree>
          </div>
        </Panel>

        <Panel
          title="Recent activity"
          headerAction={
            <Button variant="ghost" size="sm">
              View all
            </Button>
          }
          noPadding
        >
          <div style={{ padding: "4px 4px 8px" }}>
            <ActivityTimeline events={activityEvents} />
          </div>
        </Panel>
      </div>

      <div style={{ height: 18 }} />

      {/* Active pipelines */}
      <Panel
        title="Active pipelines"
        headerAction={
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 11,
                color: "rgb(var(--canvas-fg-3))",
              }}
            >
              {running} running · {data.pipelines.length - running} idle
            </span>
            <Button variant="ghost" size="sm" onClick={() => onNav("pipelines/all")}>
              All pipelines <Icon name="arrowRight" size={11} />
            </Button>
          </div>
        }
      >
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
          {data.pipelines.slice(0, 2).map((p) => (
            <PipelineCard
              key={p.id}
              pipeline={toHeimdallPipeline(p)}
              compact
              onOptions={() => {}}
              onRun={() => {}}
            />
          ))}
        </div>
      </Panel>

      <div style={{ height: 24 }} />

      {/* Quick access */}
      <div className="cs-between" style={{ marginBottom: 12 }}>
        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: "rgb(var(--canvas-fg-1))" }}>
          Quick access
        </h3>
        <span style={{ color: "rgb(var(--canvas-fg-3))", fontSize: 12 }}>
          Jump to common workflows
        </span>
      </div>
      <QuickAccessGrid
        tiles={[
          {
            id: "tax",
            icon: "schema",
            title: "Taxonomies",
            description: "Manage top-level domains and concept schemes",
          },
          {
            id: "cls",
            icon: "graph",
            title: "Classes",
            description: "Define the structure of your knowledge",
          },
          {
            id: "prop",
            icon: "component",
            title: "Properties",
            description: "Object and literal property definitions",
          },
          {
            id: "ind",
            icon: "data",
            title: "Individuals",
            description: "Browse instances populated from sources",
          },
          {
            id: "pipe",
            icon: "pipeline",
            title: "Pipelines",
            description: "Configure and run Graph-RAG pipelines",
          },
          {
            id: "ref",
            icon: "link",
            title: "Reference sources",
            description: "External APIs and document corpora",
          },
        ]}
        onAction={(id) =>
          onNav(
            {
              tax: "schema/taxonomies",
              cls: "schema/classes",
              prop: "schema/properties",
              ind: "data/individuals",
              pipe: "pipelines/all",
              ref: "reference/sources",
            }[id],
          )
        }
      />
    </div>
  );
}
window.CSDashboard = CSDashboard;

// =========================================================================
// Schema tabs — used by all schema/* pages
// =========================================================================
function SchemaTabs({ route, onNav }) {
  const data = D();
  const tabs = [
    { id: "schema/taxonomies", label: "Taxonomies", count: data.taxonomies.length },
    { id: "schema/schemes", label: "Concept schemes", count: data.concept_schemes.length },
    { id: "schema/classes", label: "Classes", count: data.classes.length },
    { id: "schema/properties", label: "Properties", count: data.property_definitions.length },
    { id: "schema/relationships", label: "Relationships", count: data.relationships.length },
  ];
  return (
    <div style={{ marginBottom: 16 }}>
      <TabBar tabs={tabs} activeTabId={route} onSelectTab={(id) => onNav(id)} />
    </div>
  );
}

// =========================================================================
// Schema · Classes  — keystone page (table + inspector)
// =========================================================================
function CSSchemaClasses({ route, onNav, onOpenNewClass }) {
  const data = D();
  const [q, setQ] = useState("");
  const [domain, setDomain] = useState("all");
  const [selectedId, setSelectedId] = useState("cls_gene");

  const filtered = useMemo(
    () =>
      data.classes.filter((c) => {
        if (domain !== "all" && c.domain !== domain) return false;
        if (!q) return true;
        const Q = q.toLowerCase();
        return (
          c.title.toLowerCase().includes(Q) ||
          c.id.toLowerCase().includes(Q) ||
          c.description.toLowerCase().includes(Q)
        );
      }),
    [q, domain],
  );

  const selected = data.classes.find((c) => c.id === selectedId);

  return (
    <div data-screen-label="03 Schema · Classes">
      <PageHeader
        eyebrow={`SCHEMA · node_type · class`}
        title="Classes"
        idChip="/schema/classes"
        subtitle="Classes are the structural nodes of the graph. Each belongs to a concept scheme, inherits from a parent class, and carries data-property definitions populated by pipelines or curators."
        actions={
          <>
            <Button variant="ghost">
              <Icon name="download" size={13} /> Export
            </Button>
            <Button variant="primary" onClick={onOpenNewClass}>
              <Icon name="plus" size={13} /> New class
            </Button>
          </>
        }
      />

      <div style={{ height: 14 }} />
      <SchemaTabs route={route} onNav={onNav} />

      {/* filter bar */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
        <div style={{ flex: "0 1 340px", position: "relative" }}>
          <div
            style={{
              position: "absolute",
              left: 10,
              top: "50%",
              transform: "translateY(-50%)",
              color: "rgb(var(--canvas-fg-3))",
              pointerEvents: "none",
            }}
          >
            <Icon name="search" size={13} />
          </div>
          <TextInput
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search classes, descriptions, ids…"
            style={{ paddingLeft: 30, width: "100%" }}
          />
        </div>
        <SegmentedControl
          options={[
            { value: "all", label: "All domains" },
            { value: "life", label: "life" },
            { value: "climate", label: "climate" },
            { value: "software", label: "software" },
          ]}
          value={domain}
          onChange={setDomain}
        />
        <span
          style={{
            marginLeft: "auto",
            fontFamily: "var(--font-mono)",
            fontSize: 11,
            color: "rgb(var(--canvas-fg-3))",
          }}
        >
          showing {filtered.length} of {data.classes.length}
        </span>
      </div>

      <div
        style={{ display: "grid", gridTemplateColumns: "1fr 380px", gap: 14, alignItems: "start" }}
      >
        <Panel noPadding>
          <div style={{ maxHeight: 600, overflow: "auto" }}>
            <Table
              columns={[
                {
                  key: "swatch",
                  label: "",
                  width: "36px",
                  render: (_, c) => (
                    <span
                      className="cs-domain-dot"
                      style={{ background: `var(--dom-${c.domain})` }}
                    />
                  ),
                },
                {
                  key: "id",
                  label: "Identifier",
                  width: "160px",
                  render: (v) => (
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: 12.5 }}>{v}</span>
                  ),
                },
                {
                  key: "title",
                  label: "Title",
                  render: (v) => <span style={{ fontWeight: 500 }}>{v}</span>,
                },
                {
                  key: "description",
                  label: "Description",
                  render: (v) => (
                    <span style={{ color: "rgb(var(--canvas-fg-3))", fontSize: 12.5 }}>{v}</span>
                  ),
                },
                {
                  key: "concept_scheme_id",
                  label: "Scheme",
                  width: "140px",
                  render: (v) => {
                    const sch = data.concept_schemes.find((s) => s.id === v);
                    return <Chip variant="neutral">{sch?.title}</Chip>;
                  },
                },
                {
                  key: "individuals",
                  label: "Ind",
                  width: "70px",
                  render: (v) => (
                    <span
                      style={{
                        fontFamily: "var(--font-mono)",
                        textAlign: "right",
                        display: "block",
                      }}
                    >
                      {v}
                    </span>
                  ),
                },
                {
                  key: "version",
                  label: "Ver",
                  width: "60px",
                  render: (v) => <VersionPill>{v}</VersionPill>,
                },
              ]}
              data={filtered}
              rowKey="id"
              selectedRows={[selectedId]}
              onRowClick={(row) => setSelectedId(row.id)}
              emptyState={
                <div style={{ padding: 40, textAlign: "center", color: "rgb(var(--canvas-fg-3))" }}>
                  No classes match these filters.
                </div>
              }
            />
          </div>
        </Panel>

        {selected && <CSClassInspector cls={selected} />}
      </div>
    </div>
  );
}
window.CSSchemaClasses = CSSchemaClasses;

function CSClassInspector({ cls }) {
  const data = D();
  const sch = data.concept_schemes.find((s) => s.id === cls.concept_scheme_id);
  const tax = data.taxonomies.find((t) => t.id === cls.taxonomy_id);
  const parent = cls.parent_class_id
    ? data.classes.find((c) => c.id === cls.parent_class_id)
    : null;
  const children = data.classes.filter((c) => c.parent_class_id === cls.id);
  const indSample = data.individuals.filter((i) => i.class_ids.includes(cls.id)).slice(0, 5);
  const rels = data.relationships.filter((r) => r.source_id === cls.id || r.target_id === cls.id);
  const props = data.property_definitions.slice(0, 4);

  const domainPill = (d, label) => (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        fontFamily: "var(--font-mono)",
        fontSize: 11.5,
      }}
    >
      <span className="cs-domain-dot" style={{ background: `var(--dom-${d})` }} />
      <span>{label}</span>
    </span>
  );

  return (
    <InspectorPanel
      eyebrow={`CLASS · ${tax?.domain ?? ""}`}
      title={cls.title}
      id={cls.id}
      version={cls.version}
      actions={
        <>
          <Button variant="ghost" size="sm" icon>
            <Icon name="edit" size={13} />
          </Button>
          <Button variant="ghost" size="sm" icon>
            <Icon name="moreVertical" size={13} />
          </Button>
        </>
      }
    >
      <InspectorPanel.Section title="Identity">
        <KVGrid
          keyWidth={130}
          rows={[
            {
              key: "DESCRIPTION",
              value: <span style={{ color: "rgb(var(--canvas-fg-2))" }}>{cls.description}</span>,
            },
            { key: "DOMAIN", value: domainPill(cls.domain, cls.domain) },
            {
              key: "SCHEME",
              value: (
                <span>
                  {domainPill(sch?.domain, sch?.title)}{" "}
                  <span
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 11,
                      color: "rgb(var(--canvas-fg-3))",
                      marginLeft: 6,
                    }}
                  >
                    {sch?.id}
                  </span>
                </span>
              ),
            },
            {
              key: "TAXONOMY",
              value: (
                <span>
                  {domainPill(tax?.domain, tax?.title)}{" "}
                  <span
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 11,
                      color: "rgb(var(--canvas-fg-3))",
                      marginLeft: 6,
                    }}
                  >
                    {tax?.id}
                  </span>
                </span>
              ),
            },
            {
              key: "PARENT CLASS",
              value: parent ? (
                domainPill(parent.domain, parent.title)
              ) : (
                <em style={{ color: "rgb(var(--canvas-fg-3))" }}>— root —</em>
              ),
            },
            {
              key: "CHILDREN",
              value:
                children.length === 0 ? (
                  <em style={{ color: "rgb(var(--canvas-fg-3))" }}>— none —</em>
                ) : (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {children.map((c) => (
                      <span
                        key={c.id}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 6,
                          fontFamily: "var(--font-mono)",
                          fontSize: 11.5,
                        }}
                      >
                        <span
                          className="cs-domain-dot"
                          style={{ background: `var(--dom-${c.domain})` }}
                        />
                        <span>{c.title}</span>
                      </span>
                    ))}
                  </div>
                ),
            },
          ]}
        />
      </InspectorPanel.Section>

      <InspectorPanel.PropertySection
        title="Property definitions"
        count={props.length}
        actionIcon={<Icon name="plus" size={11} />}
        actionLabel="Add property"
        onAction={() => {}}
        rows={props.map((p) => ({ key: p.identifier, value: p.title, usageCount: p.used_by }))}
      />

      <InspectorPanel.Section
        title="Sample individuals"
        count={cls.individuals}
        actions={
          <Button variant="link" size="sm">
            Show all →
          </Button>
        }
      >
        {indSample.length === 0 ? (
          <em style={{ fontSize: 12, color: "rgb(var(--canvas-fg-3))" }}>— no individuals yet —</em>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {indSample.map((i) => (
              <div
                key={i.id}
                style={{ display: "flex", alignItems: "center", gap: 12, padding: "4px 0" }}
              >
                <span style={{ flex: 1, fontSize: 12.5 }}>{i.title}</span>
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    color: "rgb(var(--canvas-fg-3))",
                  }}
                >
                  {i.id}
                </span>
                <VersionPill>{i.version}</VersionPill>
              </div>
            ))}
          </div>
        )}
      </InspectorPanel.Section>

      <InspectorPanel.Section title="Relationships" count={rels.length}>
        {rels.length === 0 ? (
          <em style={{ fontSize: 12, color: "rgb(var(--canvas-fg-3))" }}>
            — not used in any relationships —
          </em>
        ) : (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 8,
              fontFamily: "var(--font-mono)",
              fontSize: 11.5,
            }}
          >
            {rels.map((r) => {
              const prop = data.property_definitions.find((p) => p.id === r.property_definition_id);
              const isSource = r.source_id === cls.id;
              const other = isSource
                ? data.classes.find((c) => c.id === r.target_id) ||
                  data.individuals.find((i) => i.id === r.target_id)
                : data.classes.find((c) => c.id === r.source_id) ||
                  data.individuals.find((i) => i.id === r.source_id);
              return (
                <div key={r.id} style={{ display: "flex", gap: 12 }}>
                  <span style={{ flex: 1 }}>
                    {isSource ? cls.title : other?.title || "?"}
                    <span style={{ color: "rgb(var(--canvas-fg-3))" }}>
                      {" "}
                      — {prop?.identifier} →{" "}
                    </span>
                    {isSource ? other?.title || "?" : cls.title}
                  </span>
                  <span style={{ color: "rgb(var(--canvas-fg-3))" }}>{r.id}</span>
                </div>
              );
            })}
          </div>
        )}
      </InspectorPanel.Section>
    </InspectorPanel>
  );
}

// =========================================================================
// Schema · simple table pages (Taxonomies, Schemes, Properties, Relationships)
// =========================================================================
function CSSchemaTaxonomies({ route, onNav }) {
  const data = D();
  return (
    <div data-screen-label="02 Schema · Taxonomies">
      <PageHeader
        eyebrow="SCHEMA · node_type · taxonomy"
        title="Taxonomies"
        idChip="/schema/taxonomies"
        subtitle="A taxonomy is the top-level domain. It groups concept schemes — each scheme is a focused area of knowledge."
        actions={
          <>
            <Button variant="ghost">
              <Icon name="download" size={13} /> Export
            </Button>
            <Button variant="primary">
              <Icon name="plus" size={13} /> New taxonomy
            </Button>
          </>
        }
      />
      <div style={{ height: 14 }} />
      <SchemaTabs route={route} onNav={onNav} />
      <Panel noPadding>
        <Table
          rowKey="id"
          columns={[
            {
              key: "swatch",
              label: "",
              width: "36px",
              render: (_, t) => (
                <span className="cs-domain-dot" style={{ background: `var(--dom-${t.domain})` }} />
              ),
            },
            {
              key: "id",
              label: "Identifier",
              width: "120px",
              render: (v) => (
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 12.5 }}>{v}</span>
              ),
            },
            {
              key: "title",
              label: "Title",
              render: (v) => <span style={{ fontWeight: 500 }}>{v}</span>,
            },
            {
              key: "description",
              label: "Description",
              render: (v) => (
                <span style={{ color: "rgb(var(--canvas-fg-3))", fontSize: 12.5 }}>{v}</span>
              ),
            },
            {
              key: "classes",
              label: "Classes",
              width: "90px",
              render: (v) => (
                <span
                  style={{ fontFamily: "var(--font-mono)", textAlign: "right", display: "block" }}
                >
                  {v}
                </span>
              ),
            },
            {
              key: "individuals",
              label: "Individuals",
              width: "100px",
              render: (v) => (
                <span
                  style={{ fontFamily: "var(--font-mono)", textAlign: "right", display: "block" }}
                >
                  {v}
                </span>
              ),
            },
            {
              key: "updated",
              label: "Updated",
              width: "120px",
              render: (v) => (
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 11.5,
                    color: "rgb(var(--canvas-fg-3))",
                  }}
                >
                  {v}
                </span>
              ),
            },
            {
              key: "version",
              label: "Ver",
              width: "60px",
              render: (v) => <VersionPill>{v}</VersionPill>,
            },
          ]}
          data={data.taxonomies}
        />
      </Panel>
    </div>
  );
}
window.CSSchemaTaxonomies = CSSchemaTaxonomies;

function CSSchemaSchemes({ route, onNav }) {
  const data = D();
  return (
    <div data-screen-label="03 Schema · Concept schemes">
      <PageHeader
        eyebrow="SCHEMA · node_type · concept_scheme"
        title="Concept schemes"
        idChip="/schema/schemes"
        subtitle="A concept scheme is a focused vocabulary inside a taxonomy. Classes belong to exactly one scheme."
        actions={
          <>
            <Button variant="ghost">
              <Icon name="download" size={13} /> Export
            </Button>
            <Button variant="primary">
              <Icon name="plus" size={13} /> New scheme
            </Button>
          </>
        }
      />
      <div style={{ height: 14 }} />
      <SchemaTabs route={route} onNav={onNav} />
      <Panel noPadding>
        <Table
          rowKey="id"
          columns={[
            {
              key: "swatch",
              label: "",
              width: "36px",
              render: (_, s) => (
                <span className="cs-domain-dot" style={{ background: `var(--dom-${s.domain})` }} />
              ),
            },
            {
              key: "id",
              label: "Identifier",
              width: "160px",
              render: (v) => (
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 12.5 }}>{v}</span>
              ),
            },
            {
              key: "title",
              label: "Title",
              render: (v) => <span style={{ fontWeight: 500 }}>{v}</span>,
            },
            {
              key: "description",
              label: "Description",
              render: (v) => (
                <span style={{ color: "rgb(var(--canvas-fg-3))", fontSize: 12.5 }}>{v}</span>
              ),
            },
            {
              key: "taxonomy_id",
              label: "Taxonomy",
              width: "160px",
              render: (v) => {
                const t = data.taxonomies.find((x) => x.id === v);
                return <Chip variant="neutral">{t?.title}</Chip>;
              },
            },
            {
              key: "classes",
              label: "Classes",
              width: "80px",
              render: (v) => <span style={{ fontFamily: "var(--font-mono)" }}>{v}</span>,
            },
            {
              key: "version",
              label: "Ver",
              width: "60px",
              render: (v) => <VersionPill>{v}</VersionPill>,
            },
          ]}
          data={data.concept_schemes}
        />
      </Panel>
    </div>
  );
}
window.CSSchemaSchemes = CSSchemaSchemes;

function CSSchemaProperties({ route, onNav }) {
  const data = D();
  const relChip = (r) =>
    r === true ? (
      <Chip variant="emerald">relevant</Chip>
    ) : r === false ? (
      <Chip variant="rose">irrelevant</Chip>
    ) : (
      <Chip variant="neutral">unevaluated</Chip>
    );
  return (
    <div data-screen-label="04 Schema · Properties">
      <PageHeader
        eyebrow="SCHEMA · node_type · property_definition"
        title="Properties"
        idChip="/schema/properties"
        subtitle="Property definitions are the named predicates used by relationships. A tri-state relevance flag drives which appear in the inferred graph."
        actions={
          <>
            <Button variant="ghost">
              <Icon name="filter" size={13} /> Filter
            </Button>
            <Button variant="primary">
              <Icon name="plus" size={13} /> New property
            </Button>
          </>
        }
      />
      <div style={{ height: 14 }} />
      <SchemaTabs route={route} onNav={onNav} />
      <Panel noPadding>
        <Table
          rowKey="id"
          columns={[
            {
              key: "identifier",
              label: "Identifier",
              width: "180px",
              render: (v) => (
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 12.5, fontWeight: 500 }}>
                  {v}
                </span>
              ),
            },
            { key: "title", label: "Title" },
            {
              key: "description",
              label: "Description",
              render: (v) => (
                <span style={{ color: "rgb(var(--canvas-fg-3))", fontSize: 12.5 }}>{v}</span>
              ),
            },
            { key: "is_relevant", label: "Relevance", width: "140px", render: relChip },
            {
              key: "origin",
              label: "Origin",
              width: "160px",
              render: (v) => (
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 11.5,
                    color: "rgb(var(--canvas-fg-3))",
                  }}
                >
                  {v}
                </span>
              ),
            },
            {
              key: "used_by",
              label: "Used by",
              width: "80px",
              render: (v) => <span style={{ fontFamily: "var(--font-mono)" }}>{v}</span>,
            },
            {
              key: "version",
              label: "Ver",
              width: "60px",
              render: (v) => <VersionPill>{v}</VersionPill>,
            },
          ]}
          data={data.property_definitions}
        />
      </Panel>
    </div>
  );
}
window.CSSchemaProperties = CSSchemaProperties;

function CSSchemaRelationships({ route, onNav }) {
  const data = D();
  const lookup = (id) =>
    data.classes.find((c) => c.id === id) || data.individuals.find((i) => i.id === id);
  return (
    <div data-screen-label="05 Schema · Relationships">
      <PageHeader
        eyebrow="SCHEMA · node_type · relationship"
        title="Relationships"
        idChip="/schema/relationships"
        subtitle="A relationship is a typed triple (s, p, o) between two graph nodes. Source and confidence are tracked separately from the data."
        actions={
          <>
            <Button variant="ghost">
              <Icon name="download" size={13} /> Export
            </Button>
            <Button variant="primary">
              <Icon name="plus" size={13} /> New relationship
            </Button>
          </>
        }
      />
      <div style={{ height: 14 }} />
      <SchemaTabs route={route} onNav={onNav} />
      <Panel noPadding>
        <Table
          rowKey="id"
          columns={[
            {
              key: "id",
              label: "Identifier",
              width: "120px",
              render: (v) => (
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 12.5 }}>{v}</span>
              ),
            },
            {
              key: "source_id",
              label: "Source",
              render: (v) => {
                const s = lookup(v);
                return (
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                    <span
                      className="cs-domain-dot"
                      style={{ background: `var(--dom-${s?.domain || "default"})` }}
                    />
                    {s?.title}
                  </span>
                );
              },
            },
            {
              key: "property_definition_id",
              label: "Predicate",
              width: "180px",
              render: (v) => {
                const p = data.property_definitions.find((pd) => pd.id === v);
                return (
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: 11.5 }}>
                    — {p?.identifier} →
                  </span>
                );
              },
            },
            {
              key: "target_id",
              label: "Target",
              render: (v) => {
                const t = lookup(v);
                return (
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                    <span
                      className="cs-domain-dot"
                      style={{ background: `var(--dom-${t?.domain || "default"})` }}
                    />
                    {t?.title}
                  </span>
                );
              },
            },
            {
              key: "confidence",
              label: "Conf.",
              width: "80px",
              render: (v) => <span style={{ fontFamily: "var(--font-mono)" }}>{v.toFixed(2)}</span>,
            },
            {
              key: "created",
              label: "Created",
              width: "120px",
              render: (v) => (
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 11.5,
                    color: "rgb(var(--canvas-fg-3))",
                  }}
                >
                  {v}
                </span>
              ),
            },
          ]}
          data={data.relationships}
        />
      </Panel>
    </div>
  );
}
window.CSSchemaRelationships = CSSchemaRelationships;

// =========================================================================
// Data · Individuals — table
// =========================================================================
function CSIndividuals({ onNav }) {
  const data = D();
  return (
    <div data-screen-label="06 Data · Individuals">
      <PageHeader
        eyebrow="DATA · node_type · individual"
        title="Individuals"
        idChip="/data/individuals"
        subtitle="Concrete instances populated from pipelines or curators. Each individual belongs to one or more classes."
        actions={
          <>
            <Button variant="ghost">
              <Icon name="filter" size={13} /> Filter
            </Button>
            <Button variant="primary">
              <Icon name="plus" size={13} /> New individual
            </Button>
          </>
        }
      />
      <div style={{ height: 18 }} />
      <Panel noPadding>
        <Table
          rowKey="id"
          columns={[
            {
              key: "id",
              label: "Identifier",
              width: "180px",
              render: (v) => (
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 12.5 }}>{v}</span>
              ),
            },
            {
              key: "title",
              label: "Title",
              render: (v) => <span style={{ fontWeight: 500 }}>{v}</span>,
            },
            {
              key: "description",
              label: "Description",
              render: (v) => (
                <span style={{ color: "rgb(var(--canvas-fg-3))", fontSize: 12.5 }}>{v}</span>
              ),
            },
            {
              key: "class_ids",
              label: "Classes",
              width: "200px",
              render: (v) => (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                  {v.map((cid) => {
                    const c = data.classes.find((x) => x.id === cid);
                    return (
                      c && (
                        <Chip key={cid} variant="neutral">
                          {c.title}
                        </Chip>
                      )
                    );
                  })}
                </div>
              ),
            },
            {
              key: "source",
              label: "Source",
              width: "100px",
              render: (v) => (
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 11.5,
                    color: "rgb(var(--canvas-fg-3))",
                  }}
                >
                  {v}
                </span>
              ),
            },
            {
              key: "confidence",
              label: "Conf.",
              width: "80px",
              render: (v) => <span style={{ fontFamily: "var(--font-mono)" }}>{v.toFixed(2)}</span>,
            },
            {
              key: "version",
              label: "Ver",
              width: "60px",
              render: (v) => <VersionPill>{v}</VersionPill>,
            },
          ]}
          data={data.individuals}
        />
      </Panel>
    </div>
  );
}
window.CSIndividuals = CSIndividuals;

// =========================================================================
// Pipelines — full list as PipelineCard stack
// =========================================================================
function CSPipelines({ onNav }) {
  const data = D();
  const ICON_REMAP = { reference: "link", sparkle: "zap", doc: "file", database: "hardDrive" };
  // Per-stage tone now ships natively via FlowNode.color (source→extract→resolve→write).
  const STAGE_TONES = ["cyan", "violet", "amber", "emerald"];
  const toHeimdallPipeline = (p) => ({
    id: p.id,
    name: p.name,
    description: p.description,
    status: p.status,
    target: p.target,
    tags: p.tags,
    lastRun: p.lastRun,
    flow: p.flow.map((s, i) => ({
      id: `${p.id}-${i}`,
      name: s.name,
      label: s.kind,
      icon: ICON_REMAP[s.ic] || s.ic,
      color: STAGE_TONES[i % STAGE_TONES.length],
    })),
    recent: p.recent || { ingested: 0, created: 0, updated: 0, errors: 0 },
  });
  return (
    <div data-screen-label="07 Pipelines">
      <PageHeader
        eyebrow="PIPELINES · workflow"
        title="Pipelines"
        idChip="/pipelines/all"
        subtitle="Graph-RAG ingest pipelines. Each pipeline pulls from a source, extracts structure, and writes to the knowledge graph."
        actions={
          <>
            <Button variant="ghost">
              <Icon name="reload" size={13} /> Refresh
            </Button>
            <Button variant="primary">
              <Icon name="plus" size={13} /> New pipeline
            </Button>
          </>
        }
      />
      <div style={{ height: 18 }} />
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {data.pipelines.map((p) => (
          <PipelineCard
            key={p.id}
            pipeline={toHeimdallPipeline(p)}
            onRun={() => {}}
            onCancel={() => {}}
            onOptions={() => {}}
          />
        ))}
      </div>
    </div>
  );
}
window.CSPipelines = CSPipelines;

// =========================================================================
// Stub page — for routes not yet fully built
// =========================================================================
function CSStub({ route }) {
  return (
    <div data-screen-label={`Stub · ${route}`}>
      <PageHeader
        title={route
          .split("/")
          .map((s) => s[0].toUpperCase() + s.slice(1))
          .join(" · ")}
        idChip={`/${route}`}
        subtitle={`This route renders a basic stub. The v2 rebuild prioritises Dashboard, Schema, Individuals, and Pipelines — other surfaces compose from the same Heimdall primitives.`}
      />
      <div style={{ height: 18 }} />
      <Panel
        title="Coming next"
        subtitle="This screen composes Heimdall components like the others — placeholder shown to demonstrate routing."
      >
        <p style={{ margin: 0, color: "rgb(var(--canvas-fg-2))", fontSize: 13.5, lineHeight: 1.7 }}>
          The shell, sidebar, topbar, and statusbar around this canvas are all real{" "}
          <code>@tinkermonkey/heimdall-ui</code> components. So is every chip, button, table, and
          panel on the other pages. The dev team can take the JSX from any rendered page and paste
          it into the production codebase with only the imports to add at the top of the file.
        </p>
      </Panel>
    </div>
  );
}
window.CSStub = CSStub;

// =========================================================================
// Pipelines · Extraction review  (issue #1230 — design for #1231)
//
// One paragraph input → two independent runs (schema_extraction and
// individual_extraction) → two review tabs, each with its own accept/apply.
//
// Every mocked field below is a real API contract field (openapi.json):
//   POST /pipelines/{type}/run                         → PipelineRunResponse
//   GET  /pipelines/runs/{id}/schema-extraction-candidates
//        → SchemaClassCandidate | SchemaPropertyCandidate | SchemaConnectionCandidate
//   GET  /pipelines/runs/{id}/individual-extraction-candidates → TripleCandidate
//   POST /pipelines/runs/{id}/recognition-preview      → RecognitionPreviewResponse
//   POST /pipelines/runs/{id}/apply                    → ApplyRunResponse
// Candidates carry no id, so rows are keyed by list index (sc-0, t-3, hit-2).
// Demo dataset: Documentation Robotics 12-layer model (taxonomy dr_spec).
// =========================================================================

const DR_LAYERS = {
  motivation: "01",
  business: "02",
  security: "03",
  application: "04",
  technology: "05",
  api: "06",
  "data-model": "07",
  "data-store": "08",
  ux: "09",
  navigation: "10",
  apm: "11",
  testing: "12",
};

// "motivation.stakeholder" → { layer: "motivation", num: "01", type: "stakeholder" }
function drLayerOf(classId) {
  if (!classId) return null;
  const [layer, ...rest] = classId.split(".");
  return { layer, num: DR_LAYERS[layer] || "??", type: rest.join(".") };
}

const XR_TEXT =
  "The Customer Portal lets policyholders submit insurance claims online. Each claim is reviewed by a Claims Adjuster, a key stakeholder, through the Claims Review Service, which exposes the POST /claims operation and persists records to the Claims Database. The goal Reduce Claim Turnaround influences the Claims Review Service, which must resolve claims within 48 hours.";

// SourceSpanSchema {quote, start, end} — mock helper locates the quote in XR_TEXT.
function xrSpan(quote) {
  const at = XR_TEXT.indexOf(quote);
  return at < 0 ? { quote, start: null, end: null } : { quote, start: at, end: at + quote.length };
}

const XR_MOCK = {
  scope: { taxonomy_id: "dr_spec", concept_scheme_id: "dr_spec.extracted" },
  schemaRun: {
    id: "run_5b0e91",
    pipeline_type: "schema_extraction",
    configuration_slug: "default",
    configuration_version: 3,
    status: "COMPLETED",
    duration: "11.4s",
    failure_reason: "LLM provider timeout after 60s",
  },
  individualRun: {
    id: "run_5b0e92",
    pipeline_type: "individual_extraction",
    configuration_slug: "default",
    configuration_version: 3,
    status: "COMPLETED",
    duration: "14.9s",
    failure_reason: "LLM provider timeout after 60s",
  },
  schemaCandidates: [
    {
      candidate_type: "schema_class",
      label: "Policyholder",
      confidence: 0.91,
      proposed_definition:
        "A person or organization holding an insurance policy who interacts with the business through its channels.",
      provenance: [xrSpan("policyholders")],
    },
    {
      candidate_type: "schema_class",
      label: "Insurance Claim",
      confidence: 0.88,
      proposed_definition: "A request by a policyholder for compensation under the terms of a policy.",
      provenance: [xrSpan("insurance claims"), xrSpan("Each claim")],
    },
    {
      candidate_type: "schema_class",
      label: "Claims Adjuster",
      confidence: 0.74,
      proposed_definition: "A role that assesses the validity and value of submitted claims.",
      provenance: [xrSpan("Claims Adjuster")],
    },
    {
      candidate_type: "schema_class",
      label: "Online Channel",
      confidence: 0.41,
      proposed_definition: "A digital channel through which customers reach a business service.",
      provenance: [xrSpan("online")],
    },
    {
      candidate_type: "schema_class",
      label: "Turnaround SLA",
      confidence: 0.38,
      proposed_definition: null,
      provenance: [{ quote: "turnaround SLA", start: null, end: null }],
    },
    {
      candidate_type: "schema_property",
      label: "submits",
      confidence: 0.86,
      proposed_definition: "The actor initiates a business object.",
      proposed_domain: "business.business-actor",
      proposed_range: "business.business-object",
      provenance: [xrSpan("submit")],
    },
    {
      candidate_type: "schema_property",
      label: "reviewed-by",
      confidence: 0.79,
      proposed_definition: "The object is assessed by a stakeholder or role.",
      proposed_domain: "business.business-object",
      proposed_range: "motivation.stakeholder",
      provenance: [xrSpan("reviewed by")],
    },
    {
      candidate_type: "schema_property",
      label: "persists-to",
      confidence: 0.72,
      proposed_definition: "A service writes records to a data store.",
      proposed_domain: "application.application-service",
      proposed_range: "data-store.database",
      provenance: [xrSpan("persists records to")],
    },
    {
      candidate_type: "schema_property",
      label: "resolution-window",
      confidence: 0.55,
      proposed_definition: "Maximum time allowed to resolve the object.",
      proposed_domain: "application.application-service",
      proposed_range: "xsd:duration",
      provenance: [xrSpan("within 48 hours")],
    },
    {
      candidate_type: "schema_connection",
      subject_ref: "application.application-service",
      predicate: "exposes",
      object_ref: "api.operation",
      confidence: 0.83,
      provenance: [xrSpan("exposes the POST /claims operation")],
    },
    {
      candidate_type: "schema_connection",
      subject_ref: "motivation.goal",
      predicate: "influences",
      object_ref: "application.application-service",
      confidence: 0.77,
      provenance: [xrSpan("Reduce Claim Turnaround influences the Claims Review Service")],
    },
    {
      candidate_type: "schema_connection",
      subject_ref: "Policyholder",
      predicate: "submits",
      object_ref: "Insurance Claim",
      confidence: 0.81,
      provenance: [xrSpan("policyholders submit insurance claims")],
    },
  ],
};

// NodeReference {kind, label, id (null = new), class_ids, value, datatype}
const XR_N = {
  portal: { kind: "individual", label: "Customer Portal", id: "ind_7c21", class_ids: ["application.application-component"] },
  holder: { kind: "individual", label: "Policyholder", id: null, class_ids: ["business.business-actor"] },
  claim: { kind: "individual", label: "Insurance Claim", id: null, class_ids: ["business.business-object"] },
  adjuster: { kind: "individual", label: "Claims Adjuster", id: "ind_3a90", class_ids: ["motivation.stakeholder"] },
  crs: { kind: "individual", label: "Claims Review Service", id: "ind_5e12", class_ids: ["application.application-service"] },
  op: { kind: "individual", label: "POST /claims", id: "ind_0b44", class_ids: ["api.operation"] },
  db: { kind: "individual", label: "Claims Database", id: null, class_ids: ["data-store.database"] },
  goal: { kind: "individual", label: "Reduce Claim Turnaround", id: "ind_9f07", class_ids: ["motivation.goal"] },
  window: { kind: "literal", label: "48 hours", id: null, class_ids: null, value: "PT48H", datatype: "xsd:duration" },
};
// PredicateReference {kind, label, property_definition_id (null = new)}
const xrP = (label, pdId) => ({ kind: "property", label, property_definition_id: pdId });

XR_MOCK.triples = [
  { subject: XR_N.portal, predicate: xrP("serves", "pd_serves"), object: XR_N.holder, confidence: 0.9,
    provenance: [xrSpan("Customer Portal lets policyholders")] },
  { subject: XR_N.holder, predicate: xrP("submits", null), object: XR_N.claim, confidence: 0.87,
    provenance: [xrSpan("policyholders submit insurance claims")] },
  { subject: XR_N.adjuster, predicate: xrP("reviews", null), object: XR_N.claim, confidence: 0.82,
    provenance: [xrSpan("Each claim is reviewed by a Claims Adjuster")] },
  { subject: XR_N.adjuster, predicate: xrP("uses", "pd_uses"), object: XR_N.crs, confidence: 0.69,
    provenance: [xrSpan("through the Claims Review Service")] },
  { subject: XR_N.crs, predicate: xrP("exposes", "pd_exposes"), object: XR_N.op, confidence: 0.93,
    provenance: [xrSpan("exposes the POST /claims operation")] },
  { subject: XR_N.crs, predicate: xrP("persists-to", "pd_accesses"), object: XR_N.db, confidence: 0.8,
    provenance: [xrSpan("persists records to the Claims Database")] },
  { subject: XR_N.goal, predicate: xrP("influences", "pd_influences"), object: XR_N.crs, confidence: 0.76,
    provenance: [xrSpan("Reduce Claim Turnaround influences the Claims Review Service")] },
  { subject: XR_N.crs, predicate: xrP("resolution-window", null), object: XR_N.window, confidence: 0.58,
    provenance: [xrSpan("within 48 hours")] },
];

// RecognitionPreviewResponse
XR_MOCK.recognition = {
  total_mentions: 8,
  matched_count: 5,
  unmatched_count: 3,
  skipped_count: 0,
  hits: [
    { mention_label: "Customer Portal", resolved_individual_id: "ind_7c21", resolved_individual_title: "Customer Self-Service Portal",
      match_method: "vector", match_score: 0.92, will_match_existing: true, candidate_class_ids: ["application.application-component"] },
    { mention_label: "Claims Adjuster", resolved_individual_id: "ind_3a90", resolved_individual_title: "Claims Adjuster",
      match_method: "exact", match_score: 1.0, will_match_existing: true, candidate_class_ids: ["motivation.stakeholder"] },
    { mention_label: "Claims Review Service", resolved_individual_id: "ind_5e12", resolved_individual_title: "Claim Review Service",
      match_method: "vector", match_score: 0.95, will_match_existing: true, candidate_class_ids: ["application.application-service"] },
    { mention_label: "POST /claims", resolved_individual_id: "ind_0b44", resolved_individual_title: "POST /claims",
      match_method: "exact", match_score: 1.0, will_match_existing: true, candidate_class_ids: ["api.operation"] },
    { mention_label: "Reduce Claim Turnaround", resolved_individual_id: "ind_9f07", resolved_individual_title: "Reduce claim turnaround time",
      match_method: "llm", match_score: 0.91, will_match_existing: true, candidate_class_ids: ["motivation.goal"] },
    { mention_label: "Policyholder", resolved_individual_id: null, resolved_individual_title: null,
      match_method: null, match_score: null, will_match_existing: false, candidate_class_ids: ["business.business-actor"] },
    { mention_label: "Insurance Claim", resolved_individual_id: null, resolved_individual_title: null,
      match_method: null, match_score: null, will_match_existing: false, candidate_class_ids: ["business.business-object"] },
    { mention_label: "Claims Database", resolved_individual_id: null, resolved_individual_title: null,
      match_method: null, match_score: null, will_match_existing: false, candidate_class_ids: ["data-store.database"] },
  ],
};

const XR_METHOD_VARIANT = { exact: "emerald", vector: "cyan", llm: "violet" };
const xrPct = (v) => (v == null ? "—" : `${Math.round(v * 100)}%`);
const xrLocated = (s) => s.start != null && s.end != null;

// ---- Source text with span highlighting --------------------------------
// spans: [{ key, start, end }]. Overlaps are handled by splitting the text at
// every boundary; a segment is "active" if any covering span's key is selected.
function CSSourceText({ text, spans, activeKey, onSelectKey, testId }) {
  const located = spans.filter(xrLocated);
  const cuts = Array.from(new Set([0, text.length, ...located.flatMap((s) => [s.start, s.end])])).sort(
    (a, b) => a - b,
  );
  const segments = [];
  for (let i = 0; i < cuts.length - 1; i++) {
    const a = cuts[i];
    const b = cuts[i + 1];
    segments.push({ a, b, covering: located.filter((s) => s.start <= a && s.end >= b) });
  }
  return (
    <p className="cs-source-text" data-testid={testId}>
      {segments.map(({ a, b, covering }) => {
        const chunk = text.slice(a, b);
        if (covering.length === 0) return <span key={a}>{chunk}</span>;
        const active = covering.some((s) => s.key === activeKey);
        return (
          <mark
            key={a}
            className={`cs-span${active ? " cs-span--active" : ""}${covering.length > 1 ? " cs-span--overlap" : ""}`}
            data-testid="extraction-review-span"
            data-span-keys={covering.map((s) => s.key).join(" ")}
            aria-current={active ? "true" : undefined}
            role="button"
            tabIndex={0}
            onClick={() => onSelectKey(active ? activeKey : covering[0].key)}
          >
            {chunk}
          </mark>
        );
      })}
    </p>
  );
}

// ---- Provenance list (inspector) ----------------------------------------
function CSProvenanceList({ provenance }) {
  return (
    <div className="cs-stack-sm" data-testid="extraction-review-provenance">
      {provenance.map((s, i) => (
        <div key={i} className="cs-between">
          <span className="cs-quote">“{s.quote || "—"}”</span>
          {xrLocated(s) ? (
            <span className="cs-mono-muted">
              {s.start}–{s.end}
            </span>
          ) : (
            <Chip variant="amber">unlocated</Chip>
          )}
        </div>
      ))}
    </div>
  );
}

// ---- Accept / reject (or merge / keep-separate) pair ---------------------
// Clicking the active choice again returns the item to "pending".
// `compact` renders icon-only square buttons for dense tables (triples).
function CSDecision({ value, onChange, yes = "Accept", no = "Reject", compact = false, testId }) {
  const pick = (v) => (e) => {
    e.stopPropagation();
    onChange(value === v ? "pending" : v);
  };
  return (
    <div className="cs-decision" role="group" aria-label="Review decision" data-testid={testId}>
      <Button
        size="sm"
        icon={compact}
        variant={value === "yes" ? "primary" : "ghost"}
        aria-pressed={value === "yes"}
        aria-label={yes}
        title={yes}
        onClick={pick("yes")}
      >
        <Icon name="check" size={12} /> {compact ? null : yes}
      </Button>
      <Button
        size="sm"
        icon={compact}
        variant={value === "no" ? "danger" : "ghost"}
        aria-pressed={value === "no"}
        aria-label={no}
        title={no}
        onClick={pick("no")}
      >
        <Icon name="x" size={12} /> {compact ? null : no}
      </Button>
    </div>
  );
}

// ---- NodeReference cell: label + mapped/new + DR layer · class ----------
function CSNodeRef({ node }) {
  if (node.kind === "literal") {
    return (
      <div className="cs-node-ref">
        <div className="cs-node-ref__head">
          <span className="cs-mono">"{node.value}"</span>
          <Chip variant="neutral">literal</Chip>
        </div>
        <span className="cs-mono-muted">{node.datatype}</span>
      </div>
    );
  }
  const mapped = !!node.id;
  const cls = node.class_ids?.[0];
  const L = drLayerOf(cls);
  return (
    <div className="cs-node-ref">
      <div className="cs-node-ref__head">
        <span className="cs-strong">{node.label}</span>
        <Chip variant={mapped ? "emerald" : "amber"}>{mapped ? "mapped" : "new"}</Chip>
      </div>
      {L && (
        <span className="cs-mono-muted">
          L{L.num} · {cls}
        </span>
      )}
    </div>
  );
}

// ---- Run state header for a tab -----------------------------------------
// The "prototype state" control exists only in the design file so the builder
// can see every state; production derives state from PipelineRunResponse.status.
function CSRunMeta({ run, state, onState, testId }) {
  const STATUS_CHIP = {
    ready: <Chip variant="emerald">COMPLETED</Chip>,
    running: <Chip variant="cyan">RUNNING</Chip>,
    failed: <Chip variant="rose">FAILED</Chip>,
    empty: <Chip variant="emerald">COMPLETED</Chip>,
  };
  return (
    <div className="cs-run-meta" data-testid={testId}>
      <Chip form="id-tag">{run.id}</Chip>
      {STATUS_CHIP[state]}
      <span className="cs-mono-muted">
        {run.pipeline_type} · {run.configuration_slug} v{run.configuration_version}
        {state !== "running" ? ` · ${run.duration}` : ""}
      </span>
      <span className="cs-run-meta__proto">
        <span className="cs-mono-muted">prototype state</span>
        <SegmentedControl
          value={state}
          onChange={onState}
          options={[
            { value: "ready", label: "ready" },
            { value: "running", label: "running" },
            { value: "failed", label: "failed" },
            { value: "empty", label: "empty" },
          ]}
        />
      </span>
    </div>
  );
}

function CSRunStateBody({ state, run, kind, onRetry }) {
  if (state === "running")
    return (
      <Panel data-testid={`extraction-review-${kind}-running`}>
        <FormCallout variant="info" icon="clock">
          {run.pipeline_type} is running. Candidates appear here when the run completes.
        </FormCallout>
      </Panel>
    );
  if (state === "failed")
    return (
      <Panel
        data-testid={`extraction-review-${kind}-failed`}
        footer={
          <div className="cs-actions-end">
            <Button variant="secondary" size="sm" onClick={onRetry}>
              <Icon name="reload" size={12} /> Re-run {run.pipeline_type}
            </Button>
          </div>
        }
      >
        <FormCallout variant="error" icon="alert">
          Run failed: {run.failure_reason}. The other extraction tab is unaffected.
        </FormCallout>
      </Panel>
    );
  if (state === "empty")
    return (
      <Panel data-testid={`extraction-review-${kind}-empty`}>
        <div className="cs-empty">
          <Icon name="search" size={18} />
          <div>The run completed but produced no candidates for this paragraph.</div>
        </div>
      </Panel>
    );
  return null;
}

// ---- Apply bar (same shape on both tabs) ---------------------------------
// Scope is read-only here: it was chosen in the run panel and lives in the
// run's input_summary, which is what apply reads.
function CSApplyBar({ kind, counts, scope, applied, onApply, onRevert, extra }) {
  return (
    <Panel
      data-testid={`extraction-review-${kind}-apply-bar`}
      title={applied ? "Applied" : "Apply to graph"}
      subtitle={
        applied
          ? "Draft entities were written. Revert removes everything this run created."
          : "Accepted candidates are written as DRAFT entities in the run's scope."
      }
    >
      <div className="cs-apply-bar">
        <KVGrid
          keyWidth={150}
          rows={[
            { key: "taxonomy", value: <span className="cs-mono">{scope.taxonomy_id}</span> },
            ...(kind === "schema"
              ? [{ key: "concept_scheme", value: <span className="cs-mono">{scope.concept_scheme_id}</span> }]
              : []),
            {
              key: "decisions",
              value: (
                <span className="cs-chip-row">
                  <Chip variant="emerald">{counts.yes} accepted</Chip>
                  <Chip variant="rose">{counts.no} rejected</Chip>
                  <Chip variant="neutral">{counts.pending} pending</Chip>
                </span>
              ),
            },
            ...(extra || []),
          ]}
        />
        <div className="cs-apply-bar__actions">
          {applied ? (
            <Button variant="danger" onClick={onRevert} data-testid={`extraction-review-${kind}-revert`}>
              <Icon name="reload" size={13} /> Revert run
            </Button>
          ) : (
            <Button
              variant="primary"
              disabled={counts.yes === 0}
              onClick={onApply}
              data-testid={`extraction-review-${kind}-apply`}
            >
              <Icon name="check" size={13} /> Apply {counts.yes} accepted
            </Button>
          )}
        </div>
      </div>
    </Panel>
  );
}

const xrCount = (decisions, keys) => {
  const c = { yes: 0, no: 0, pending: 0 };
  keys.forEach((k) => c[decisions[k] || "pending"]++);
  return c;
};
// Apply only takes confidence_threshold, so the effective filter is the lowest
// accepted confidence. Rejected items at or above it would still be applied.
const xrLeakedRejects = (decisions, items) => {
  const acc = items.filter((it) => decisions[it.key] === "yes").map((it) => it.confidence);
  if (!acc.length) return { min: null, leaked: [] };
  const min = Math.min(...acc);
  return { min, leaked: items.filter((it) => decisions[it.key] === "no" && it.confidence >= min) };
};

// =========================================================================
// Tab 1 — Schema / entity extraction review
// =========================================================================
function CSSchemaExtractionReview({ text, scope, run, onToast }) {
  const all = XR_MOCK.schemaCandidates.map((c, i) => ({ ...c, key: `sc-${i}` }));
  const [state, setState] = useState("ready");
  const [kind, setKind] = useState("schema_class");
  const [selectedKey, setSelectedKey] = useState("sc-1");
  const [decisions, setDecisions] = useState({ "sc-0": "yes", "sc-1": "yes", "sc-2": "no", "sc-4": "no", "sc-5": "yes", "sc-8": "yes" });
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [applied, setApplied] = useState(false);

  const setDecision = (k, v) => setDecisions((d) => ({ ...d, [k]: v }));
  const rows = all.filter((c) => c.candidate_type === kind);
  const selected = all.find((c) => c.key === selectedKey);
  const counts = xrCount(decisions, all.map((c) => c.key));
  const { min: minConf, leaked } = xrLeakedRejects(decisions, all);
  const label = (c) => c.label || `${c.subject_ref} → ${c.predicate} → ${c.object_ref}`;
  const spans = all.flatMap((c) => c.provenance.map((s) => ({ ...s, key: c.key })));
  const countOf = (t) => all.filter((c) => c.candidate_type === t).length;

  const decisionCol = {
    key: "key",
    label: "Decision",
    width: "196px",
    render: (k) => (
      <CSDecision
        value={decisions[k] || "pending"}
        onChange={(v) => setDecision(k, v)}
        testId={`extraction-review-schema-decision-${k}`}
      />
    ),
  };
  const confCol = {
    key: "confidence",
    label: "Conf",
    width: "64px",
    render: (v) => <span className="cs-mono">{xrPct(v)}</span>,
  };
  const COLUMNS = {
    schema_class: [
      { key: "label", label: "Proposed class", width: "160px", render: (v) => <span className="cs-strong">{v}</span> },
      {
        key: "proposed_definition",
        label: "Proposed definition",
        render: (v) => (v ? <span className="cs-muted">{v}</span> : <span className="cs-mono-muted">no definition</span>),
      },
      confCol,
      decisionCol,
    ],
    schema_property: [
      { key: "label", label: "Proposed property", width: "150px", render: (v) => <span className="cs-mono">{v}</span> },
      {
        key: "proposed_domain",
        label: "Domain → range",
        render: (v, r) => (
          <span className="cs-mono-muted">
            {v || "?"} → {r.proposed_range || "?"}
          </span>
        ),
      },
      confCol,
      decisionCol,
    ],
    schema_connection: [
      { key: "subject_ref", label: "Subject", render: (v) => <span className="cs-mono">{v}</span> },
      { key: "predicate", label: "Predicate", width: "110px", render: (v) => <Chip form="id-tag">{v}</Chip> },
      { key: "object_ref", label: "Object", render: (v) => <span className="cs-mono">{v}</span> },
      confCol,
      decisionCol,
    ],
  };

  return (
    <div data-testid="extraction-review-schema">
      <CSRunMeta run={run} state={state} onState={setState} testId="extraction-review-schema-run-meta" />
      {state !== "ready" ? (
        <CSRunStateBody state={state} run={run} kind="schema" onRetry={() => setState("running")} />
      ) : (
        <>
          <StatGrid columns={4}>
            <StatTile label="CLASSES" value={countOf("schema_class")} color="violet" icon="schema" meta="proposed classes" />
            <StatTile label="PROPERTIES" value={countOf("schema_property")} color="cyan" icon="component" meta="proposed properties" />
            <StatTile label="CONNECTIONS" value={countOf("schema_connection")} color="amber" icon="link" meta="class-to-class" />
            <StatTile
              label="ACCEPTED"
              value={`${counts.yes} / ${all.length}`}
              color="emerald"
              icon="check"
              meta={`${counts.no} rejected · ${counts.pending} pending`}
            />
          </StatGrid>
          <div className="cs-gap" />
          <div className="cs-review-grid">
            <Panel
              noPadding
              title="Candidates"
              subtitle="Accept or reject each proposal. Select a row to see its source spans."
              headerAction={
                <SegmentedControl
                  value={kind}
                  onChange={setKind}
                  options={[
                    { value: "schema_class", label: `Classes · ${countOf("schema_class")}` },
                    { value: "schema_property", label: `Properties · ${countOf("schema_property")}` },
                    { value: "schema_connection", label: `Connections · ${countOf("schema_connection")}` },
                  ]}
                />
              }
              data-testid="extraction-review-schema-candidates"
            >
              <Table
                columns={COLUMNS[kind]}
                data={rows}
                rowKey="key"
                selectedRows={[selectedKey]}
                onRowClick={(r) => setSelectedKey(r.key)}
                emptyState={<div className="cs-empty">No candidates of this type.</div>}
              />
            </Panel>

            <div className="cs-stack">
              <Panel
                title="Source text"
                subtitle="Highlights are candidate provenance. Click one to select its candidate."
                data-testid="extraction-review-schema-source-panel"
              >
                <CSSourceText
                  text={text}
                  spans={spans}
                  activeKey={selectedKey}
                  onSelectKey={(k) => {
                    setSelectedKey(k);
                    setKind(all.find((c) => c.key === k).candidate_type);
                  }}
                  testId="extraction-review-schema-source"
                />
              </Panel>
              {selected && (
                <InspectorPanel
                  eyebrow={selected.candidate_type.replace("_", " ").toUpperCase() + " CANDIDATE"}
                  title={label(selected)}
                  id={`${run.id} · #${selected.key.split("-")[1]}`}
                  actions={
                    <CSDecision
                      value={decisions[selected.key] || "pending"}
                      onChange={(v) => setDecision(selected.key, v)}
                      testId="extraction-review-schema-inspector-decision"
                    />
                  }
                  data-testid="extraction-review-schema-inspector"
                >
                  <InspectorPanel.Section title="Proposal">
                    <KVGrid
                      rows={[
                        { key: "candidate_type", value: <span className="cs-mono">{selected.candidate_type}</span> },
                        { key: "confidence", value: <span className="cs-mono">{xrPct(selected.confidence)}</span> },
                        ...(selected.proposed_definition !== undefined
                          ? [{ key: "definition", value: selected.proposed_definition || "—" }]
                          : []),
                        ...(selected.proposed_domain
                          ? [
                              { key: "domain", value: <span className="cs-mono">{selected.proposed_domain}</span> },
                              { key: "range", value: <span className="cs-mono">{selected.proposed_range}</span> },
                            ]
                          : []),
                        ...(selected.subject_ref
                          ? [
                              { key: "subject_ref", value: <span className="cs-mono">{selected.subject_ref}</span> },
                              { key: "predicate", value: <span className="cs-mono">{selected.predicate}</span> },
                              { key: "object_ref", value: <span className="cs-mono">{selected.object_ref}</span> },
                            ]
                          : []),
                      ]}
                    />
                  </InspectorPanel.Section>
                  <InspectorPanel.Section title="Provenance" count={selected.provenance.length}>
                    <CSProvenanceList provenance={selected.provenance} />
                  </InspectorPanel.Section>
                </InspectorPanel>
              )}
            </div>
          </div>
          <div className="cs-gap" />
          <CSApplyBar
            kind="schema"
            counts={counts}
            scope={scope}
            applied={applied}
            onApply={() => setConfirmOpen(true)}
            onRevert={() => {
              setApplied(false);
              onToast({ variant: "info", title: "Run reverted", subtitle: `${run.id} · draft schema removed` });
            }}
          />
          <ConfirmDialog
            isOpen={confirmOpen}
            onClose={() => setConfirmOpen(false)}
            onConfirm={() => {
              setConfirmOpen(false);
              setApplied(true);
              onToast({ variant: "success", title: "Schema candidates applied", subtitle: `${run.id} → ${scope.concept_scheme_id}` });
            }}
            variant="primary"
            title="Apply schema extraction"
            subtitle={`${run.id} → ${scope.taxonomy_id} / ${scope.concept_scheme_id}`}
            confirmLabel={`Apply ${counts.yes} accepted`}
            message={
              <div className="cs-stack-sm" data-testid="extraction-review-schema-confirm">
                <span>
                  Creates draft classes, property definitions and relationships from the {counts.yes} accepted
                  candidates. Entities that already exist with the same label are skipped.
                </span>
                {leaked.length > 0 && (
                  <FormCallout variant="warn" icon="alert">
                    Apply filters by confidence ≥ {xrPct(minConf)} (the lowest accepted score), so {leaked.length}{" "}
                    rejected candidate{leaked.length > 1 ? "s" : ""} above that score will also be applied:{" "}
                    {leaked.map(label).join(", ")}.
                  </FormCallout>
                )}
              </div>
            }
          />
        </>
      )}
    </div>
  );
}
window.CSSchemaExtractionReview = CSSchemaExtractionReview;

// =========================================================================
// Tab 2 — Individual extraction review
// =========================================================================
function CSIndividualExtractionReview({ text, scope, run, onToast }) {
  const triples = XR_MOCK.triples.map((t, i) => ({ ...t, key: `t-${i}` }));
  const rec = XR_MOCK.recognition;
  // Hits carry no spans: locate mention_label in the run's text client-side.
  const hits = rec.hits.map((h, i) => {
    const at = text.indexOf(h.mention_label);
    return {
      ...h,
      key: `hit-${i}`,
      provenance: [
        at < 0
          ? { quote: h.mention_label, start: null, end: null }
          : { quote: h.mention_label, start: at, end: at + h.mention_label.length },
      ],
    };
  });
  const [state, setState] = useState("ready");
  const [selectedKey, setSelectedKey] = useState("t-4");
  const [decisions, setDecisions] = useState({ "t-0": "yes", "t-1": "yes", "t-4": "yes", "t-5": "yes", "t-7": "no" });
  const [merges, setMerges] = useState({ "hit-0": "yes", "hit-1": "yes", "hit-2": "yes", "hit-3": "yes", "hit-4": "no" });
  const [nodeFilter, setNodeFilter] = useState("all");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [applied, setApplied] = useState(false);

  const matchedHits = hits.filter((h) => h.will_match_existing);
  const hasNewNode = (t) => [t.subject, t.object].some((n) => n.kind !== "literal" && !n.id);
  const filtered = triples.filter((t) =>
    nodeFilter === "all" ? true : nodeFilter === "new" ? hasNewNode(t) : !hasNewNode(t),
  );
  const nodes = Object.values(
    Object.fromEntries(
      triples
        .flatMap((t) => [t.subject, t.object])
        .filter((n) => n.kind !== "literal")
        .map((n) => [n.label, n]),
    ),
  );
  const counts = xrCount(decisions, triples.map((t) => t.key));
  const mergeCounts = xrCount(merges, matchedHits.map((h) => h.key));
  const { min: minConf, leaked } = xrLeakedRejects(decisions, triples);
  const tLabel = (t) => `${t.subject.label} → ${t.predicate.label} → ${t.object.label}`;
  const usesMention = (t, m) => t.subject.label === m || t.object.label === m;

  const selectedTriple = triples.find((t) => t.key === selectedKey);
  const selectedHit = hits.find((h) => h.key === selectedKey);
  const hitFor = (node) => hits.find((h) => h.mention_label === node.label);
  const spans = [
    ...triples.flatMap((t) => t.provenance.map((s) => ({ ...s, key: t.key }))),
    ...hits.flatMap((h) => h.provenance.map((s) => ({ ...s, key: h.key }))),
  ];
  const setDecision = (k, v) => setDecisions((d) => ({ ...d, [k]: v }));

  const nodeKV = (node) => {
    if (node.kind === "literal")
      return [
        { key: "kind", value: "literal" },
        { key: "value", value: <span className="cs-mono">{node.value}</span> },
        { key: "datatype", value: <span className="cs-mono">{node.datatype}</span> },
      ];
    const L = drLayerOf(node.class_ids?.[0]);
    const h = hitFor(node);
    return [
      { key: "label", value: node.label },
      {
        key: "status",
        value: node.id ? <Chip variant="emerald">mapped · {node.id}</Chip> : <Chip variant="amber">new individual</Chip>,
      },
      { key: "class", value: <span className="cs-mono">{node.class_ids?.[0]}</span> },
      { key: "dr_layer", value: L ? `L${L.num} · ${L.layer}` : "—" },
      ...(h && h.will_match_existing
        ? [{ key: "recognized_as", value: `${h.resolved_individual_title} (${h.match_method} ${xrPct(h.match_score)})` }]
        : []),
    ];
  };

  return (
    <div data-testid="extraction-review-individual">
      <CSRunMeta run={run} state={state} onState={setState} testId="extraction-review-individual-run-meta" />
      {state !== "ready" ? (
        <CSRunStateBody state={state} run={run} kind="individual" onRetry={() => setState("running")} />
      ) : (
        <>
          <StatGrid columns={4}>
            <StatTile label="TRIPLES" value={triples.length} color="violet" icon="link" meta={`${counts.yes} accepted · ${counts.no} rejected`} />
            <StatTile label="MAPPED NODES" value={nodes.filter((n) => n.id).length} color="emerald" icon="check" meta="resolve to existing individuals" />
            <StatTile label="NEW NODES" value={nodes.filter((n) => !n.id).length} color="amber" icon="plus" meta="created on apply" />
            <StatTile
              label="RECOGNITION"
              value={`${rec.matched_count} / ${rec.total_mentions}`}
              color="cyan"
              icon="search"
              meta={`${rec.unmatched_count} unmatched · ${rec.skipped_count} skipped`}
            />
          </StatGrid>
          <div className="cs-gap" />
          <div className="cs-review-grid">
            <div className="cs-stack">
              <Panel
                noPadding
                title="Extracted triples"
                subtitle="Mapped nodes resolve to an existing individual. New nodes are created on apply."
                headerAction={
                  <SegmentedControl
                    value={nodeFilter}
                    onChange={setNodeFilter}
                    options={[
                      { value: "all", label: "All" },
                      { value: "mapped", label: "Mapped only" },
                      { value: "new", label: "Has new node" },
                    ]}
                  />
                }
                data-testid="extraction-review-triples"
              >
                <Table
                  columns={[
                    { key: "subject", label: "Subject", render: (v) => <CSNodeRef node={v} /> },
                    {
                      key: "predicate",
                      label: "Predicate",
                      width: "140px",
                      render: (p) => (
                        <div className="cs-node-ref">
                          <span className="cs-mono">{p.label}</span>
                          {p.property_definition_id ? (
                            <span className="cs-mono-muted">↳ {p.property_definition_id}</span>
                          ) : (
                            <span>
                              <Chip variant="amber">new property</Chip>
                            </span>
                          )}
                        </div>
                      ),
                    },
                    { key: "object", label: "Object", render: (v) => <CSNodeRef node={v} /> },
                    { key: "confidence", label: "Conf", width: "60px", render: (v) => <span className="cs-mono">{xrPct(v)}</span> },
                    {
                      key: "key",
                      label: "Decision",
                      width: "84px",
                      render: (k) => (
                        <CSDecision
                          compact
                          value={decisions[k] || "pending"}
                          onChange={(v) => setDecision(k, v)}
                          testId={`extraction-review-individual-decision-${k}`}
                        />
                      ),
                    },
                  ]}
                  data={filtered}
                  rowKey="key"
                  selectedRows={[selectedKey]}
                  onRowClick={(r) => setSelectedKey(r.key)}
                  emptyState={<div className="cs-empty">No triples match this filter.</div>}
                />
              </Panel>

              <Panel
                noPadding
                title="Recognition · dedup hits"
                subtitle="Mentions that match an existing individual (recognition ≥ 90%). Merge reuses the existing node; keep separate creates a new one."
                headerAction={
                  <span className="cs-chip-row">
                    <Chip variant="emerald">{mergeCounts.yes} merge</Chip>
                    <Chip variant="neutral">{mergeCounts.no} separate</Chip>
                  </span>
                }
                data-testid="extraction-review-recognition"
              >
                <Table
                  columns={[
                    { key: "mention_label", label: "Mention", width: "170px", render: (v) => <span className="cs-strong">{v}</span> },
                    {
                      key: "resolved_individual_title",
                      label: "Existing individual",
                      render: (v, h) =>
                        h.will_match_existing ? (
                          <div className="cs-node-ref">
                            <span>{v}</span>
                            <span className="cs-mono-muted">
                              {h.resolved_individual_id} · {h.candidate_class_ids[0]}
                            </span>
                          </div>
                        ) : (
                          <span className="cs-mono-muted">no match · created as new</span>
                        ),
                    },
                    {
                      key: "match_method",
                      label: "Method",
                      width: "84px",
                      render: (v) => (v ? <Chip variant={XR_METHOD_VARIANT[v]}>{v}</Chip> : <span className="cs-mono-muted">—</span>),
                    },
                    { key: "match_score", label: "Score", width: "64px", render: (v) => <span className="cs-mono">{xrPct(v)}</span> },
                    {
                      key: "key",
                      label: "Decision",
                      width: "236px",
                      render: (k, h) =>
                        h.will_match_existing ? (
                          <CSDecision
                            value={merges[k] || "pending"}
                            onChange={(v) => setMerges((m) => ({ ...m, [k]: v }))}
                            yes="Merge"
                            no="Keep separate"
                            testId={`extraction-review-recognition-decision-${k}`}
                          />
                        ) : (
                          <Chip variant="amber">new</Chip>
                        ),
                    },
                  ]}
                  data={hits}
                  rowKey="key"
                  selectedRows={[selectedKey]}
                  onRowClick={(r) => setSelectedKey(r.key)}
                  emptyState={<div className="cs-empty">No mentions previewed.</div>}
                />
              </Panel>
            </div>

            <div className="cs-stack">
              <Panel
                title="Source text"
                subtitle="Highlights link to triples and mentions. Click one to select it."
                data-testid="extraction-review-individual-source-panel"
              >
                <CSSourceText
                  text={text}
                  spans={spans}
                  activeKey={selectedKey}
                  onSelectKey={setSelectedKey}
                  testId="extraction-review-individual-source"
                />
              </Panel>

              {selectedTriple && (
                <InspectorPanel
                  eyebrow="TRIPLE CANDIDATE"
                  title={tLabel(selectedTriple)}
                  id={`${run.id} · #${selectedTriple.key.split("-")[1]} · ${xrPct(selectedTriple.confidence)}`}
                  actions={
                    <CSDecision
                      value={decisions[selectedTriple.key] || "pending"}
                      onChange={(v) => setDecision(selectedTriple.key, v)}
                      testId="extraction-review-individual-inspector-decision"
                    />
                  }
                  data-testid="extraction-review-individual-inspector"
                >
                  <InspectorPanel.Section title="Subject">
                    <KVGrid rows={nodeKV(selectedTriple.subject)} />
                  </InspectorPanel.Section>
                  <InspectorPanel.Section title="Predicate">
                    <KVGrid
                      rows={[
                        { key: "label", value: <span className="cs-mono">{selectedTriple.predicate.label}</span> },
                        {
                          key: "property",
                          value: selectedTriple.predicate.property_definition_id ? (
                            <Chip variant="emerald">mapped · {selectedTriple.predicate.property_definition_id}</Chip>
                          ) : (
                            <Chip variant="amber">new property</Chip>
                          ),
                        },
                      ]}
                    />
                  </InspectorPanel.Section>
                  <InspectorPanel.Section title="Object">
                    <KVGrid rows={nodeKV(selectedTriple.object)} />
                  </InspectorPanel.Section>
                  <InspectorPanel.Section title="Provenance" count={selectedTriple.provenance.length}>
                    <CSProvenanceList provenance={selectedTriple.provenance} />
                  </InspectorPanel.Section>
                </InspectorPanel>
              )}

              {selectedHit && (
                <InspectorPanel
                  eyebrow="RECOGNITION HIT"
                  title={selectedHit.mention_label}
                  id={selectedHit.resolved_individual_id || "no match"}
                  data-testid="extraction-review-recognition-inspector"
                >
                  <InspectorPanel.Section title="Match">
                    <KVGrid
                      rows={[
                        { key: "will_match", value: selectedHit.will_match_existing ? "existing individual" : "created as new" },
                        { key: "resolved_title", value: selectedHit.resolved_individual_title || "—" },
                        { key: "method", value: selectedHit.match_method || "—" },
                        { key: "score", value: <span className="cs-mono">{xrPct(selectedHit.match_score)}</span> },
                        {
                          key: "classes",
                          value: (
                            <span className="cs-chip-row">
                              {selectedHit.candidate_class_ids.map((c) => (
                                <Chip key={c} form="id-tag">
                                  {c}
                                </Chip>
                              ))}
                            </span>
                          ),
                        },
                      ]}
                    />
                  </InspectorPanel.Section>
                  <InspectorPanel.Section
                    title="Triples using this mention"
                    count={triples.filter((t) => usesMention(t, selectedHit.mention_label)).length}
                  >
                    <div className="cs-stack-sm">
                      {triples
                        .filter((t) => usesMention(t, selectedHit.mention_label))
                        .map((t) => (
                          <Button key={t.key} variant="link" size="sm" onClick={() => setSelectedKey(t.key)}>
                            {tLabel(t)}
                          </Button>
                        ))}
                    </div>
                  </InspectorPanel.Section>
                </InspectorPanel>
              )}
            </div>
          </div>
          <div className="cs-gap" />
          <CSApplyBar
            kind="individual"
            counts={counts}
            scope={scope}
            applied={applied}
            onApply={() => setConfirmOpen(true)}
            onRevert={() => {
              setApplied(false);
              onToast({ variant: "info", title: "Run reverted", subtitle: `${run.id} · draft individuals removed` });
            }}
            extra={[
              {
                key: "recognition",
                value: (
                  <span className="cs-chip-row">
                    <Chip variant="emerald">{mergeCounts.yes} merge</Chip>
                    <Chip variant="neutral">{mergeCounts.no} keep separate</Chip>
                    <span className="cs-mono-muted">threshold 0.90</span>
                  </span>
                ),
              },
            ]}
          />
          <ConfirmDialog
            isOpen={confirmOpen}
            onClose={() => setConfirmOpen(false)}
            onConfirm={() => {
              setConfirmOpen(false);
              setApplied(true);
              onToast({ variant: "success", title: "Individuals applied", subtitle: `${run.id} → ${scope.taxonomy_id}` });
            }}
            variant="primary"
            title="Apply individual extraction"
            subtitle={`${run.id} → ${scope.taxonomy_id}`}
            confirmLabel={`Apply ${counts.yes} accepted`}
            message={
              <div className="cs-stack-sm" data-testid="extraction-review-individual-confirm">
                <span>
                  Creates draft individuals and relationships from {counts.yes} accepted triples. {mergeCounts.yes}{" "}
                  mentions merge into existing individuals; {nodes.filter((n) => !n.id).length} new individuals are
                  created.
                </span>
                {leaked.length > 0 && (
                  <FormCallout variant="warn" icon="alert">
                    Apply filters by confidence ≥ {xrPct(minConf)}, so {leaked.length} rejected triple
                    {leaked.length > 1 ? "s" : ""} above that score will also be applied.
                  </FormCallout>
                )}
                {mergeCounts.no > 0 && (
                  <FormCallout variant="warn" icon="alert">
                    {mergeCounts.no} "keep separate" choice{mergeCounts.no > 1 ? "s" : ""} can't be applied per hit.
                    Apply uses one recognition threshold for every mention.
                  </FormCallout>
                )}
              </div>
            }
          />
        </>
      )}
    </div>
  );
}
window.CSIndividualExtractionReview = CSIndividualExtractionReview;

// =========================================================================
// Page — paragraph input + run trigger + two review tabs
// =========================================================================
function CSExtractionReview({ onNav, onToast }) {
  const [text, setText] = useState(XR_TEXT);
  const [runText, setRunText] = useState(XR_TEXT);
  const [taxonomy, setTaxonomy] = useState(XR_MOCK.scope.taxonomy_id);
  const [scheme, setScheme] = useState(XR_MOCK.scope.concept_scheme_id);
  const [config, setConfig] = useState("default");
  const [textError, setTextError] = useState(undefined);
  const [tab, setTab] = useState(() => ((location.hash || "").includes("tab=individual") ? "individual" : "schema"));
  const [runKey, setRunKey] = useState(0);
  const scope = { taxonomy_id: taxonomy, concept_scheme_id: scheme };

  const run = () => {
    if (!text.trim()) {
      setTextError("Paste a paragraph to extract from");
      return;
    }
    setRunText(text);
    setRunKey((k) => k + 1);
    onToast({ variant: "info", title: "Extraction started", subtitle: "schema_extraction + individual_extraction" });
  };

  return (
    <div data-screen-label="08 Pipelines · Extraction review" data-testid="extraction-review-page">
      <PageHeader
        eyebrow="PIPELINES · extraction · review"
        title="Extraction review"
        idChip="/pipelines/review"
        subtitle="Paste a paragraph and run schema and individual extraction against a taxonomy. Review each result set, then apply what you accept. Nothing is written until you apply."
        actions={
          <Button variant="ghost" onClick={() => onNav("pipelines/runs")}>
            <Icon name="clock" size={13} /> Run history
          </Button>
        }
      />
      <div className="cs-gap" />

      <Panel
        title="Source paragraph"
        subtitle="Both runs read the same paragraph. Each result set is reviewed and applied separately."
        data-testid="extraction-review-input"
        footer={
          <div className="cs-between">
            <span className="cs-mono-muted">starts schema_extraction + individual_extraction</span>
            <Button variant="primary" onClick={run} data-testid="extraction-review-run">
              <Icon name="zap" size={13} /> Run extraction
            </Button>
          </div>
        }
      >
        <div className="cs-input-grid">
          <Field label="Paragraph" required error={textError} errorId="extraction-review-text-error">
            <TextArea
              rows={5}
              value={text}
              error={!!textError}
              aria-describedby={textError ? "extraction-review-text-error" : undefined}
              onChange={(e) => {
                setText(e.target.value);
                setTextError(undefined);
              }}
              data-testid="extraction-review-text"
            />
          </Field>
          <div className="cs-stack-sm">
            <Field label="Taxonomy" required>
              <Select value={taxonomy} onChange={setTaxonomy}>
                <Select.Item value="dr_spec">Documentation Robotics · dr_spec</Select.Item>
              </Select>
            </Field>
            <Field label="Concept scheme" required hint="schema target">
              <Select value={scheme} onChange={setScheme}>
                <Select.Item value="dr_spec.extracted">Extracted · dr_spec.extracted</Select.Item>
                <Select.Item value="dr_spec.core">Core layers · dr_spec.core</Select.Item>
              </Select>
            </Field>
            <Field label="Configuration">
              <Select value={config} onChange={setConfig}>
                <Select.Item value="default">default · v3</Select.Item>
                <Select.Item value="open_v1">open_v1 · v1</Select.Item>
              </Select>
            </Field>
          </div>
        </div>
        {text !== runText && (
          <div className="cs-gap-sm">
            <FormCallout variant="warn" icon="alert" data-testid="extraction-review-stale">
              The paragraph changed since the last run. Highlights show the text that was run. Re-run to review the
              new text.
            </FormCallout>
          </div>
        )}
      </Panel>

      <div className="cs-gap" />
      <TabBar
        tabs={[
          { id: "schema", label: "Schema extraction", count: XR_MOCK.schemaCandidates.length },
          { id: "individual", label: "Individual extraction", count: XR_MOCK.triples.length },
        ]}
        activeTabId={tab}
        onSelectTab={setTab}
        data-testid="extraction-review-tabs"
      />
      <div className="cs-gap-sm" />
      {tab === "schema" ? (
        <CSSchemaExtractionReview key={`s${runKey}`} text={runText} scope={scope} run={XR_MOCK.schemaRun} onToast={onToast} />
      ) : (
        <CSIndividualExtractionReview key={`i${runKey}`} text={runText} scope={scope} run={XR_MOCK.individualRun} onToast={onToast} />
      )}
    </div>
  );
}
window.CSExtractionReview = CSExtractionReview;
