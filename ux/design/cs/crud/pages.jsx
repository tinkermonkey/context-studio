// =========================================================================
// Context Studio — CRUD pages (override the read-only base pages)
// Each schema/data page = PageHeader + tabs + filter bar + <EntitySurface>.
// Loaded AFTER cs/pages.jsx so these window.* assignments win.
// =========================================================================

// local copy of the schema tab strip (base SchemaTabs isn't exported)
function CrudSchemaTabs({ route, onNav }) {
  const data = useCS();
  const tabs = [
    { id: "schema/taxonomies", label: "Taxonomies", count: data.taxonomies.length },
    { id: "schema/schemes", label: "Concept schemes", count: data.concept_schemes.length },
    { id: "schema/classes", label: "Classes", count: data.classes.length },
    { id: "schema/properties", label: "Properties", count: data.property_definitions.length },
    { id: "schema/relationships", label: "Relationships", count: data.relationships.length },
  ];
  return (
    <div style={{ marginBottom: 16 }}>
      <TabBar tabs={tabs} activeTabId={route} onSelectTab={onNav} />
    </div>
  );
}

function FilterBar({ q, setQ, placeholder, total, shown, children }) {
  return (
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
          placeholder={placeholder}
          style={{ paddingLeft: 30, width: "100%" }}
        />
      </div>
      {children}
      <span
        style={{
          marginLeft: "auto",
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          color: "rgb(var(--canvas-fg-3))",
        }}
      >
        showing {shown} of {total}
      </span>
    </div>
  );
}

// pick up a cross-page "create child" request after navigation
function usePendingCreate(type, surfaceRef) {
  useEffect(() => {
    const p = window.__CS_PENDING;
    if (p && p.type === type) {
      window.__CS_PENDING = null;
      const t = setTimeout(() => surfaceRef.current && surfaceRef.current.startCreate(p.ctx), 30);
      return () => clearTimeout(t);
    }
  }, []); // eslint-disable-line
}
function csRequestChild(onNav, route, type, ctx) {
  window.__CS_PENDING = { type, ctx };
  onNav(route);
}

const domDot = (d) => <span className="cs-domain-dot" style={{ background: `var(--dom-${d})` }} />;
const monoCell = (v) => <span style={{ fontFamily: "var(--font-mono)", fontSize: 12.5 }}>{v}</span>;
const descCell = (v) => (
  <span style={{ color: "rgb(var(--canvas-fg-3))", fontSize: 12.5 }}>{v}</span>
);
const numCell = (v) => (
  <span style={{ fontFamily: "var(--font-mono)", textAlign: "right", display: "block" }}>{v}</span>
);

// ---- Taxonomies --------------------------------------------------------
function CSSchemaTaxonomies({ route, onNav }) {
  const data = useCS();
  const surf = useRef(null);
  const [q, setQ] = useState("");
  usePendingCreate("taxonomy", surf);
  const rows = data.taxonomies.filter(
    (t) => !q || (t.title + t.id + t.description).toLowerCase().includes(q.toLowerCase()),
  );
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
            <Button variant="primary" onClick={() => surf.current.startCreate()}>
              <Icon name="plus" size={13} /> New taxonomy
            </Button>
          </>
        }
      />
      <div style={{ height: 14 }} />
      <CrudSchemaTabs route={route} onNav={onNav} />
      <FilterBar
        q={q}
        setQ={setQ}
        placeholder="Search taxonomies…"
        total={data.taxonomies.length}
        shown={rows.length}
      />
      <EntitySurface
        ref={surf}
        type="taxonomy"
        rows={rows}
        inspectorEmpty={{
          icon: "schema",
          title: "No taxonomy selected",
          sub: "Select a taxonomy to inspect it, or create one.",
        }}
        childAction={{
          label: "Add concept scheme",
          icon: "plus",
          onTrigger: (row) =>
            csRequestChild(onNav, "schema/schemes", "scheme", {
              taxonomy_id: row.id,
              domain: row.domain,
            }),
        }}
        columns={[
          { key: "swatch", label: "", width: "36px", render: (_, t) => domDot(t.domain) },
          { key: "id", label: "Identifier", width: "120px", render: monoCell },
          {
            key: "title",
            label: "Title",
            render: (v) => <span style={{ fontWeight: 500 }}>{v}</span>,
          },
          { key: "description", label: "Description", render: descCell },
          { key: "classes", label: "Classes", width: "84px", render: numCell },
          { key: "individuals", label: "Indiv.", width: "84px", render: numCell },
          {
            key: "version",
            label: "Ver",
            width: "56px",
            render: (v) => <VersionPill>{v}</VersionPill>,
          },
        ]}
      />
    </div>
  );
}
window.CSSchemaTaxonomies = CSSchemaTaxonomies;

// ---- Concept schemes ---------------------------------------------------
function CSSchemaSchemes({ route, onNav }) {
  const data = useCS();
  const surf = useRef(null);
  const [q, setQ] = useState("");
  usePendingCreate("scheme", surf);
  const rows = data.concept_schemes.filter(
    (s) => !q || (s.title + s.id + s.description).toLowerCase().includes(q.toLowerCase()),
  );
  const taxOpts = data.taxonomies.map((t) => ({ value: t.id, label: t.title, description: t.id }));
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
            <Button variant="primary" onClick={() => surf.current.startCreate()}>
              <Icon name="plus" size={13} /> New scheme
            </Button>
          </>
        }
      />
      <div style={{ height: 14 }} />
      <CrudSchemaTabs route={route} onNav={onNav} />
      <FilterBar
        q={q}
        setQ={setQ}
        placeholder="Search concept schemes…"
        total={data.concept_schemes.length}
        shown={rows.length}
      />
      <EntitySurface
        ref={surf}
        type="scheme"
        rows={rows}
        inspectorEmpty={{
          icon: "schema",
          title: "No scheme selected",
          sub: "Select a concept scheme to inspect it, or create one.",
        }}
        childAction={{
          label: "Add class",
          icon: "plus",
          onTrigger: (row) =>
            csRequestChild(onNav, "schema/classes", "class", {
              concept_scheme_id: row.id,
              taxonomy_id: row.taxonomy_id,
              domain: row.domain,
            }),
        }}
        bulkOps={[
          { id: "delete", label: "Delete", icon: "trash", danger: true, kind: "delete" },
          {
            id: "move",
            label: "Move to taxonomy",
            icon: "folder",
            kind: "select",
            title: "Move to taxonomy",
            fieldLabel: "Taxonomy",
            options: taxOpts,
            apply: (v, d) => {
              const t = d.taxonomies.find((x) => x.id === v);
              return { taxonomy_id: v, domain: t ? t.domain : undefined };
            },
          },
        ]}
        columns={[
          { key: "swatch", label: "", width: "36px", render: (_, s) => domDot(s.domain) },
          { key: "id", label: "Identifier", width: "150px", render: monoCell },
          {
            key: "title",
            label: "Title",
            render: (v) => <span style={{ fontWeight: 500 }}>{v}</span>,
          },
          { key: "description", label: "Description", render: descCell },
          {
            key: "taxonomy_id",
            label: "Taxonomy",
            width: "150px",
            render: (v) => {
              const t = data.taxonomies.find((x) => x.id === v);
              return <Chip variant="neutral">{t?.title}</Chip>;
            },
          },
          { key: "classes", label: "Classes", width: "76px", render: numCell },
          {
            key: "version",
            label: "Ver",
            width: "56px",
            render: (v) => <VersionPill>{v}</VersionPill>,
          },
        ]}
      />
    </div>
  );
}
window.CSSchemaSchemes = CSSchemaSchemes;

// ---- Classes -----------------------------------------------------------
function CSSchemaClasses({ route, onNav }) {
  const data = useCS();
  const surf = useRef(null);
  const [q, setQ] = useState("");
  const [domain, setDomain] = useState("all");
  usePendingCreate("class", surf);
  const rows = data.classes.filter((c) => {
    if (domain !== "all" && c.domain !== domain) return false;
    if (!q) return true;
    return (c.title + c.id + c.description).toLowerCase().includes(q.toLowerCase());
  });
  const schemeOpts = data.concept_schemes.map((s) => ({
    value: s.id,
    label: s.title,
    description: s.id,
  }));
  return (
    <div data-screen-label="04 Schema · Classes">
      <PageHeader
        eyebrow="SCHEMA · node_type · class"
        title="Classes"
        idChip="/schema/classes"
        subtitle="Classes are the structural nodes of the graph. Each belongs to a concept scheme, inherits from a parent class, and carries data-property definitions."
        actions={
          <>
            <Button variant="ghost">
              <Icon name="download" size={13} /> Export
            </Button>
            <Button variant="primary" onClick={() => surf.current.startCreate()}>
              <Icon name="plus" size={13} /> New class
            </Button>
          </>
        }
      />
      <div style={{ height: 14 }} />
      <CrudSchemaTabs route={route} onNav={onNav} />
      <FilterBar
        q={q}
        setQ={setQ}
        placeholder="Search classes, descriptions, ids…"
        total={data.classes.length}
        shown={rows.length}
      >
        <SegmentedControl
          value={domain}
          onChange={setDomain}
          options={[
            { value: "all", label: "All domains" },
            { value: "life", label: "life" },
            { value: "climate", label: "climate" },
            { value: "software", label: "software" },
          ]}
        />
      </FilterBar>
      <EntitySurface
        ref={surf}
        type="class"
        rows={rows}
        inspectorEmpty={{
          icon: "graph",
          title: "No class selected",
          sub: "Select a class to inspect it, or create one.",
        }}
        childAction={{
          label: "Add child class",
          icon: "plus",
          onTrigger: (row) =>
            surf.current.startCreate({
              concept_scheme_id: row.concept_scheme_id,
              taxonomy_id: row.taxonomy_id,
              domain: row.domain,
              parent_class_id: row.id,
            }),
        }}
        bulkOps={[
          { id: "delete", label: "Delete", icon: "trash", danger: true, kind: "delete" },
          {
            id: "move",
            label: "Move to scheme",
            icon: "folder",
            kind: "select",
            title: "Move to concept scheme",
            fieldLabel: "Concept scheme",
            options: schemeOpts,
            apply: (v, d) => {
              const s = d.concept_schemes.find((x) => x.id === v);
              return { concept_scheme_id: v, taxonomy_id: s?.taxonomy_id, domain: s?.domain };
            },
          },
        ]}
        columns={[
          { key: "swatch", label: "", width: "36px", render: (_, c) => domDot(c.domain) },
          { key: "id", label: "Identifier", width: "150px", render: monoCell },
          {
            key: "title",
            label: "Title",
            render: (v) => <span style={{ fontWeight: 500 }}>{v}</span>,
          },
          { key: "description", label: "Description", render: descCell },
          {
            key: "concept_scheme_id",
            label: "Scheme",
            width: "140px",
            render: (v) => {
              const s = data.concept_schemes.find((x) => x.id === v);
              return <Chip variant="neutral">{s?.title}</Chip>;
            },
          },
          { key: "individuals", label: "Ind", width: "64px", render: numCell },
          {
            key: "version",
            label: "Ver",
            width: "56px",
            render: (v) => <VersionPill>{v}</VersionPill>,
          },
        ]}
      />
    </div>
  );
}
window.CSSchemaClasses = CSSchemaClasses;

// ---- Properties --------------------------------------------------------
function CSSchemaProperties({ route, onNav }) {
  const data = useCS();
  const surf = useRef(null);
  const [q, setQ] = useState("");
  usePendingCreate("property", surf);
  const rows = data.property_definitions.filter(
    (p) => !q || (p.identifier + p.title + p.description).toLowerCase().includes(q.toLowerCase()),
  );
  const relChip = (r) =>
    r === true ? (
      <Chip variant="emerald">relevant</Chip>
    ) : r === false ? (
      <Chip variant="rose">irrelevant</Chip>
    ) : (
      <Chip variant="neutral">unevaluated</Chip>
    );
  return (
    <div data-screen-label="05 Schema · Properties">
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
            <Button variant="primary" onClick={() => surf.current.startCreate()}>
              <Icon name="plus" size={13} /> New property
            </Button>
          </>
        }
      />
      <div style={{ height: 14 }} />
      <CrudSchemaTabs route={route} onNav={onNav} />
      <FilterBar
        q={q}
        setQ={setQ}
        placeholder="Search properties…"
        total={data.property_definitions.length}
        shown={rows.length}
      />
      <EntitySurface
        ref={surf}
        type="property"
        rows={rows}
        inspectorWidth={400}
        inspectorEmpty={{
          icon: "component",
          title: "No property selected",
          sub: "Select a property definition to inspect it, or create one.",
        }}
        bulkOps={[
          { id: "delete", label: "Delete", icon: "trash", danger: true, kind: "delete" },
          {
            id: "relevance",
            label: "Set relevance",
            icon: "check",
            kind: "segmented",
            title: "Set relevance",
            default: "true",
            apply: (v) => ({ is_relevant: v === "true" ? true : v === "false" ? false : null }),
            options: [
              { value: "true", label: "relevant" },
              { value: "null", label: "unevaluated" },
              { value: "false", label: "irrelevant" },
            ],
          },
        ]}
        columns={[
          {
            key: "identifier",
            label: "Identifier",
            width: "170px",
            render: (v) => (
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 12.5, fontWeight: 500 }}>
                {v}
              </span>
            ),
          },
          { key: "title", label: "Title" },
          { key: "description", label: "Description", render: descCell },
          { key: "is_relevant", label: "Relevance", width: "130px", render: relChip },
          {
            key: "used_by",
            label: "Used",
            width: "64px",
            render: (v) => <span style={{ fontFamily: "var(--font-mono)" }}>{v}</span>,
          },
          {
            key: "version",
            label: "Ver",
            width: "56px",
            render: (v) => <VersionPill>{v}</VersionPill>,
          },
        ]}
      />
    </div>
  );
}
window.CSSchemaProperties = CSSchemaProperties;

// ---- Relationships -----------------------------------------------------
function CSSchemaRelationships({ route, onNav }) {
  const data = useCS();
  const surf = useRef(null);
  const [q, setQ] = useState("");
  usePendingCreate("relationship", surf);
  const lookup = (id) =>
    data.classes.find((c) => c.id === id) || data.individuals.find((i) => i.id === id);
  const rows = data.relationships.filter((r) => {
    if (!q) return true;
    const s = lookup(r.source_id),
      t = lookup(r.target_id);
    return (r.id + (s?.title || "") + (t?.title || "")).toLowerCase().includes(q.toLowerCase());
  });
  return (
    <div data-screen-label="06 Schema · Relationships">
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
            <Button variant="primary" onClick={() => surf.current.startCreate()}>
              <Icon name="plus" size={13} /> New relationship
            </Button>
          </>
        }
      />
      <div style={{ height: 14 }} />
      <CrudSchemaTabs route={route} onNav={onNav} />
      <FilterBar
        q={q}
        setQ={setQ}
        placeholder="Search relationships…"
        total={data.relationships.length}
        shown={rows.length}
      />
      <EntitySurface
        ref={surf}
        type="relationship"
        rows={rows}
        inspectorWidth={440}
        inspectorEmpty={{
          icon: "link",
          title: "No relationship selected",
          sub: "Select a triple to inspect it, or create one.",
        }}
        columns={[
          { key: "id", label: "Identifier", width: "110px", render: monoCell },
          {
            key: "source_id",
            label: "Source",
            render: (v) => {
              const s = lookup(v);
              return (
                <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                  {domDot(s?.domain || "default")}
                  {s?.title}
                </span>
              );
            },
          },
          {
            key: "property_definition_id",
            label: "Predicate",
            width: "170px",
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
                  {domDot(t?.domain || "default")}
                  {t?.title}
                </span>
              );
            },
          },
          {
            key: "confidence",
            label: "Conf.",
            width: "72px",
            render: (v) => (
              <span style={{ fontFamily: "var(--font-mono)" }}>
                {(v ?? 0).toFixed ? v.toFixed(2) : v}
              </span>
            ),
          },
        ]}
      />
    </div>
  );
}
window.CSSchemaRelationships = CSSchemaRelationships;

// ---- Individuals -------------------------------------------------------
function CSIndividuals({ onNav }) {
  const data = useCS();
  const surf = useRef(null);
  const [q, setQ] = useState("");
  usePendingCreate("individual", surf);
  const rows = data.individuals.filter(
    (i) => !q || (i.title + i.id + i.description).toLowerCase().includes(q.toLowerCase()),
  );
  return (
    <div data-screen-label="07 Data · Individuals">
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
            <Button variant="primary" onClick={() => surf.current.startCreate()}>
              <Icon name="plus" size={13} /> New individual
            </Button>
          </>
        }
      />
      <div style={{ height: 18 }} />
      <FilterBar
        q={q}
        setQ={setQ}
        placeholder="Search individuals…"
        total={data.individuals.length}
        shown={rows.length}
      />
      <EntitySurface
        ref={surf}
        type="individual"
        rows={rows}
        inspectorWidth={400}
        inspectorEmpty={{
          icon: "data",
          title: "No individual selected",
          sub: "Select an individual to inspect it, or create one.",
        }}
        columns={[
          { key: "id", label: "Identifier", width: "160px", render: monoCell },
          {
            key: "title",
            label: "Title",
            render: (v) => <span style={{ fontWeight: 500 }}>{v}</span>,
          },
          { key: "description", label: "Description", render: descCell },
          {
            key: "class_ids",
            label: "Classes",
            width: "180px",
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
            width: "92px",
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
            width: "72px",
            render: (v) => (
              <span style={{ fontFamily: "var(--font-mono)" }}>
                {(v ?? 0).toFixed ? v.toFixed(2) : v}
              </span>
            ),
          },
          {
            key: "version",
            label: "Ver",
            width: "56px",
            render: (v) => <VersionPill>{v}</VersionPill>,
          },
        ]}
      />
    </div>
  );
}
window.CSIndividuals = CSIndividuals;
