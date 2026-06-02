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
