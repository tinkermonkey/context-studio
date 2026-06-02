// =========================================================================
// Schema pages — Taxonomies, Concept schemes, Classes, Properties, Relationships
// Pattern: page-head + filter bar + table (8 cols) | drawer (4 cols)
// =========================================================================

// ---------------------------------------------------------------------
// Schema route dispatcher
// ---------------------------------------------------------------------
function SchemaPage({ route, onNav, onOpenNewClass }) {
  if (route === "schema/taxonomies") return <TaxonomiesPage onNav={onNav} />;
  if (route === "schema/schemes") return <SchemesPage onNav={onNav} />;
  if (route === "schema/classes")
    return <ClassesPage onNav={onNav} onOpenNewClass={onOpenNewClass} />;
  if (route === "schema/properties") return <PropertiesPage onNav={onNav} />;
  if (route === "schema/relationships") return <RelationshipsPage onNav={onNav} />;
  return <StubPage route={route} />;
}
window.SchemaPage = SchemaPage;

// ---------------------------------------------------------------------
// Tabs for the schema surfaces
// ---------------------------------------------------------------------
function SchemaTabs({ active, onNav }) {
  const D = window.CS_DATA;
  const tabs = [
    { id: "schema/taxonomies", label: "Taxonomies", count: D.taxonomies.length },
    { id: "schema/schemes", label: "Concept schemes", count: D.concept_schemes.length },
    { id: "schema/classes", label: "Classes", count: D.classes.length },
    { id: "schema/properties", label: "Properties", count: D.property_definitions.length },
    { id: "schema/relationships", label: "Relationships", count: D.relationships.length },
  ];
  return (
    <div className="tabs">
      {tabs.map((t) => (
        <button
          key={t.id}
          className={"tab" + (active === t.id ? " active" : "")}
          onClick={() => onNav(t.id)}
        >
          {t.label} <span className="count">{t.count}</span>
        </button>
      ))}
    </div>
  );
}

// =====================================================================
// Classes — the keystone surface
// =====================================================================
function ClassesPage({ onNav, onOpenNewClass }) {
  const D = window.CS_DATA;
  const [q, setQ] = useState("");
  const [domain, setDomain] = useState("all");
  const [selectedId, setSelectedId] = useState("cls_gene");

  const filtered = useMemo(
    () =>
      D.classes.filter((c) => {
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

  const selected = D.classes.find((c) => c.id === selectedId);

  return (
    <div className="canvas-inner" data-screen-label="03 Schema · Classes">
      <div className="page-head">
        <div>
          <div className="page-head-meta">
            <span className="chip violet">
              <span className="dot"></span>schema
            </span>
            <span className="id-tag">node_type · class</span>
            <span className="muted mono" style={{ fontSize: 11 }}>
              {D.classes.length} classes · {D.concept_schemes.length} schemes ·{" "}
              {D.taxonomies.length} taxonomies
            </span>
          </div>
          <h1>
            Classes <span className="id-tag">/schema/classes</span>
          </h1>
          <div className="subtitle">
            Classes are the structural nodes of the graph. Each belongs to a concept scheme,
            inherits from a parent class, and carries data-property definitions populated by
            pipelines or curators.
          </div>
        </div>
        <div className="page-actions">
          <button className="btn">
            <Icon name="ext" size={13} /> Export
          </button>
          <button className="btn btn-primary" onClick={onOpenNewClass}>
            <Icon name="plus" size={13} /> New class
          </button>
        </div>
      </div>

      <SchemaTabs active="schema/classes" onNav={onNav} />

      <div className="filter-bar">
        <div className="search-input-wrap">
          <Icon name="search" size={13} />
          <input
            className="input with-icon"
            placeholder="Search classes, descriptions, ids…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <div className="seg">
          {["all", "life", "climate", "software"].map((d) => (
            <button
              key={d}
              className={"seg-btn" + (domain === d ? " active" : "")}
              onClick={() => setDomain(d)}
            >
              {d === "all" ? "All domains" : d}
            </button>
          ))}
        </div>
        <span className="muted mono" style={{ fontSize: 11, marginLeft: "auto" }}>
          showing {filtered.length} of {D.classes.length}
        </span>
      </div>

      <div className="split-master-detail" style={{ minHeight: 540 }}>
        <div className="panel">
          <div className="table-wrap" style={{ maxHeight: 600 }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th style={{ width: 36 }}></th>
                  <th>Identifier</th>
                  <th>Title</th>
                  <th>Description</th>
                  <th style={{ width: 130 }}>Scheme</th>
                  <th style={{ width: 90, textAlign: "right" }}>Ind</th>
                  <th style={{ width: 64 }}></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((c) => {
                  const sch = D.concept_schemes.find((s) => s.id === c.concept_scheme_id);
                  return (
                    <tr
                      key={c.id}
                      className={selectedId === c.id ? "selected" : ""}
                      onClick={() => setSelectedId(c.id)}
                    >
                      <td>
                        <span className="kg-node-pill sm" data-domain={c.domain}>
                          <span className="swatch"></span>
                        </span>
                      </td>
                      <td className="mono">{c.id}</td>
                      <td>
                        <span className="row-link">{c.title}</span>
                      </td>
                      <td className="muted" style={{ fontSize: 12.5 }}>
                        {c.description}
                      </td>
                      <td>
                        <span className="chip mono">{sch?.title}</span>
                      </td>
                      <td className="num">{c.individuals}</td>
                      <td style={{ textAlign: "right" }}>
                        <div className="row-actions">
                          <button className="btn btn-ghost btn-icon" title="Edit">
                            <Icon name="edit" size={12} />
                          </button>
                          <button className="btn btn-ghost btn-icon" title="More">
                            <Icon name="more" size={12} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={7}>
                      <div className="empty">
                        <div className="ic">
                          <Icon name="search" size={20} />
                        </div>
                        <div className="t">No classes match</div>
                        <div className="d">Adjust the filters or create a new class.</div>
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {selected && <ClassDrawer cls={selected} />}
      </div>
    </div>
  );
}
window.ClassesPage = ClassesPage;

// ---------------------------------------------------------------------
// Class drawer — class detail with inline KV and related lists
// ---------------------------------------------------------------------
function ClassDrawer({ cls }) {
  const D = window.CS_DATA;
  const sch = D.concept_schemes.find((s) => s.id === cls.concept_scheme_id);
  const tax = D.taxonomies.find((t) => t.id === cls.taxonomy_id);
  const parent = cls.parent_class_id ? D.classes.find((c) => c.id === cls.parent_class_id) : null;
  const children = D.classes.filter((c) => c.parent_class_id === cls.id);
  const indSample = D.individuals.filter((i) => i.class_ids.includes(cls.id)).slice(0, 5);
  const rels = D.relationships.filter((r) => r.source_id === cls.id || r.target_id === cls.id);
  const props = D.property_definitions.slice(0, 4);

  return (
    <div className="inspector">
      <div className="inspector-head">
        <div style={{ minWidth: 0, flex: 1 }}>
          <div className="eyebrow">class · {tax?.domain}</div>
          <div className="title">{cls.title}</div>
          <div className="mono-id">{cls.id}</div>
        </div>
        <div className="row gap-12" style={{ flexShrink: 0 }}>
          <span className="version-pill">v{cls.version}</span>
          <button className="btn btn-ghost btn-icon" title="Edit">
            <Icon name="edit" size={13} />
          </button>
          <button className="btn btn-ghost btn-icon" title="More">
            <Icon name="more" size={13} />
          </button>
        </div>
      </div>

      <div className="inspector-body">
        {/* Identity */}
        <div className="kv-grid">
          <div className="k">Description</div>
          <div className="v">{cls.description}</div>
          <div className="k">Domain</div>
          <div className="v">
            <span className="kg-node-pill sm" data-domain={cls.domain}>
              <span className="swatch"></span>
              {cls.domain}
            </span>
          </div>
          <div className="k">Scheme</div>
          <div className="v">
            <span className="kg-node-pill sm" data-domain={sch.domain}>
              <span className="swatch"></span>
              {sch.title}
            </span>
            <span className="mono muted" style={{ fontSize: 11 }}>
              {sch.id}
            </span>
          </div>
          <div className="k">Taxonomy</div>
          <div className="v">
            <span className="kg-node-pill sm" data-domain={tax.domain}>
              <span className="swatch"></span>
              {tax.title}
            </span>
            <span className="mono muted" style={{ fontSize: 11 }}>
              {tax.id}
            </span>
          </div>
          <div className="k">Parent class</div>
          <div className="v">
            {parent ? (
              <span className="kg-node-pill sm" data-domain={parent.domain}>
                <span className="swatch"></span>
                {parent.title}
              </span>
            ) : (
              <em className="muted">— root —</em>
            )}
          </div>
          <div className="k">Children</div>
          <div className="v" style={{ flexDirection: "row", flexWrap: "wrap", gap: 4 }}>
            {children.length === 0 && <em className="muted">— none —</em>}
            {children.map((c) => (
              <span key={c.id} className="kg-node-pill sm" data-domain={c.domain}>
                <span className="swatch"></span>
                {c.title}
              </span>
            ))}
          </div>
        </div>

        {/* Inherited properties */}
        <div style={{ padding: "14px 16px", borderBottom: "1px solid var(--canvas-border)" }}>
          <div className="row between" style={{ marginBottom: 8 }}>
            <div className="row gap-12">
              <strong style={{ fontSize: 13 }}>Property definitions</strong>
              <span className="muted mono" style={{ fontSize: 11 }}>
                {props.length}
              </span>
            </div>
            <button className="btn btn-ghost btn-xs">
              <Icon name="plus" size={11} /> Add
            </button>
          </div>
          <table className="tbl" style={{ fontSize: 12 }}>
            <thead>
              <tr>
                <th>Identifier</th>
                <th>Title</th>
                <th style={{ width: 80 }}>Used by</th>
              </tr>
            </thead>
            <tbody>
              {props.map((p) => (
                <tr key={p.id}>
                  <td className="mono">{p.identifier}</td>
                  <td>{p.title}</td>
                  <td className="num">{p.used_by}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Individuals sample */}
        <div style={{ padding: "14px 16px", borderBottom: "1px solid var(--canvas-border)" }}>
          <div className="row between" style={{ marginBottom: 8 }}>
            <div className="row gap-12">
              <strong style={{ fontSize: 13 }}>Sample individuals</strong>
              <span className="muted mono" style={{ fontSize: 11 }}>
                {cls.individuals} total
              </span>
            </div>
            <button className="btn btn-ghost btn-xs">
              Show all <Icon name="arrow" size={10} />
            </button>
          </div>
          {indSample.length === 0 && (
            <em className="muted" style={{ fontSize: 12 }}>
              — no individuals yet —
            </em>
          )}
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {indSample.map((i) => (
              <div key={i.id} className="row gap-12" style={{ padding: "4px 0" }}>
                <span style={{ flex: 1, fontSize: 12.5 }}>{i.title}</span>
                <span className="mono muted" style={{ fontSize: 11 }}>
                  {i.id}
                </span>
                <span className="version-pill">v{i.version}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Relationships */}
        <div style={{ padding: "14px 16px" }}>
          <div className="row between" style={{ marginBottom: 8 }}>
            <strong style={{ fontSize: 13 }}>Relationships</strong>
            <span className="muted mono" style={{ fontSize: 11 }}>
              {rels.length}
            </span>
          </div>
          {rels.length === 0 ? (
            <em className="muted" style={{ fontSize: 12 }}>
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
                const prop = D.property_definitions.find((p) => p.id === r.property_definition_id);
                const isSource = r.source_id === cls.id;
                const other = isSource
                  ? D.classes.find((c) => c.id === r.target_id) ||
                    D.individuals.find((i) => i.id === r.target_id)
                  : D.classes.find((c) => c.id === r.source_id) ||
                    D.individuals.find((i) => i.id === r.source_id);
                return (
                  <div key={r.id} className="row gap-12">
                    <span style={{ flex: 1 }}>
                      {isSource ? cls.title : other?.title || "?"}
                      <span className="muted"> — {prop?.identifier} → </span>
                      {isSource ? other?.title || "?" : cls.title}
                    </span>
                    <span className="muted">{r.id}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// =====================================================================
// Taxonomies — table, big rows
// =====================================================================
function TaxonomiesPage({ onNav }) {
  const D = window.CS_DATA;
  return (
    <div className="canvas-inner" data-screen-label="02 Schema · Taxonomies">
      <div className="page-head">
        <div>
          <div className="page-head-meta">
            <span className="chip cyan">
              <span className="dot"></span>schema
            </span>
            <span className="id-tag">node_type · taxonomy</span>
            <span className="muted mono" style={{ fontSize: 11 }}>
              {D.taxonomies.length} taxonomies · {D.concept_schemes.length} schemes total
            </span>
          </div>
          <h1>
            Taxonomies <span className="id-tag">/schema/taxonomies</span>
          </h1>
          <div className="subtitle">
            A taxonomy is the top-level domain. It groups concept schemes — each scheme is a focused
            area of knowledge.
          </div>
        </div>
        <div className="page-actions">
          <button className="btn">
            <Icon name="ext" size={13} /> Export
          </button>
          <button className="btn btn-primary">
            <Icon name="plus" size={13} /> New taxonomy
          </button>
        </div>
      </div>
      <SchemaTabs active="schema/taxonomies" onNav={onNav} />

      <div className="panel">
        <table className="tbl">
          <thead>
            <tr>
              <th style={{ width: 36 }}></th>
              <th>Identifier</th>
              <th>Title</th>
              <th>Description</th>
              <th style={{ width: 90 }}>Schemes</th>
              <th style={{ width: 90, textAlign: "right" }}>Classes</th>
              <th style={{ width: 100, textAlign: "right" }}>Individuals</th>
              <th style={{ width: 120 }}>Updated</th>
              <th style={{ width: 60 }}></th>
            </tr>
          </thead>
          <tbody>
            {D.taxonomies.map((t) => (
              <tr key={t.id}>
                <td>
                  <span className="kg-node-pill sm" data-domain={t.domain}>
                    <span className="swatch"></span>
                  </span>
                </td>
                <td className="mono">{t.id}</td>
                <td>
                  <span className="row-link" style={{ fontWeight: 600 }}>
                    {t.title}
                  </span>
                </td>
                <td className="muted" style={{ fontSize: 12.5 }}>
                  {t.description}
                </td>
                <td>
                  <span className="chip mono">
                    {D.concept_schemes.filter((s) => s.taxonomy_id === t.id).length}
                  </span>
                </td>
                <td className="num">{t.classes}</td>
                <td className="num">{t.individuals}</td>
                <td className="mono muted" style={{ fontSize: 11.5 }}>
                  {t.updated}
                </td>
                <td style={{ textAlign: "right" }}>
                  <button className="btn btn-ghost btn-icon">
                    <Icon name="more" size={12} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
window.TaxonomiesPage = TaxonomiesPage;

// =====================================================================
// Concept schemes — same pattern
// =====================================================================
function SchemesPage({ onNav }) {
  const D = window.CS_DATA;
  return (
    <div className="canvas-inner" data-screen-label="03 Schema · Concept schemes">
      <div className="page-head">
        <div>
          <div className="page-head-meta">
            <span className="chip cyan">
              <span className="dot"></span>schema
            </span>
            <span className="id-tag">node_type · concept_scheme</span>
          </div>
          <h1>
            Concept schemes <span className="id-tag">/schema/schemes</span>
          </h1>
          <div className="subtitle">
            A concept scheme is a focused vocabulary inside a taxonomy. Classes belong to exactly
            one scheme.
          </div>
        </div>
        <div className="page-actions">
          <button className="btn">
            <Icon name="ext" size={13} /> Export
          </button>
          <button className="btn btn-primary">
            <Icon name="plus" size={13} /> New scheme
          </button>
        </div>
      </div>
      <SchemaTabs active="schema/schemes" onNav={onNav} />

      <div className="panel">
        <table className="tbl">
          <thead>
            <tr>
              <th style={{ width: 36 }}></th>
              <th>Identifier</th>
              <th>Title</th>
              <th>Description</th>
              <th style={{ width: 130 }}>Taxonomy</th>
              <th style={{ width: 80, textAlign: "right" }}>Classes</th>
              <th style={{ width: 80, textAlign: "right" }}>Version</th>
              <th style={{ width: 60 }}></th>
            </tr>
          </thead>
          <tbody>
            {D.concept_schemes.map((s) => {
              const tax = D.taxonomies.find((t) => t.id === s.taxonomy_id);
              return (
                <tr key={s.id}>
                  <td>
                    <span className="kg-node-pill sm" data-domain={s.domain}>
                      <span className="swatch"></span>
                    </span>
                  </td>
                  <td className="mono">{s.id}</td>
                  <td>
                    <span className="row-link" style={{ fontWeight: 600 }}>
                      {s.title}
                    </span>
                  </td>
                  <td className="muted" style={{ fontSize: 12.5 }}>
                    {s.description}
                  </td>
                  <td>
                    <span className="kg-node-pill sm" data-domain={tax.domain}>
                      <span className="swatch"></span>
                      {tax.title}
                    </span>
                  </td>
                  <td className="num">{s.classes}</td>
                  <td className="num">v{s.version}</td>
                  <td style={{ textAlign: "right" }}>
                    <button className="btn btn-ghost btn-icon">
                      <Icon name="more" size={12} />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
window.SchemesPage = SchemesPage;

// =====================================================================
// Properties — PropertyDefinitions table
// =====================================================================
function PropertiesPage({ onNav }) {
  const D = window.CS_DATA;
  const relevanceChip = (r) =>
    r === true ? (
      <span className="chip emerald">
        <span className="dot"></span>relevant
      </span>
    ) : r === false ? (
      <span className="chip rose">
        <span className="dot"></span>irrelevant
      </span>
    ) : (
      <span className="chip gray">
        <span className="dot"></span>unevaluated
      </span>
    );
  return (
    <div className="canvas-inner" data-screen-label="04 Schema · Properties">
      <div className="page-head">
        <div>
          <div className="page-head-meta">
            <span className="chip violet">
              <span className="dot"></span>schema
            </span>
            <span className="id-tag">node_type · property_definition</span>
          </div>
          <h1>
            Properties <span className="id-tag">/schema/properties</span>
          </h1>
          <div className="subtitle">
            Property definitions are the named predicates used by relationships. A tri-state
            relevance flag drives which appear in the inferred graph.
          </div>
        </div>
        <div className="page-actions">
          <button className="btn">
            <Icon name="filter" size={13} /> Filter
          </button>
          <button className="btn btn-primary">
            <Icon name="plus" size={13} /> New property
          </button>
        </div>
      </div>
      <SchemaTabs active="schema/properties" onNav={onNav} />

      <div className="panel">
        <table className="tbl">
          <thead>
            <tr>
              <th>Identifier</th>
              <th>Title</th>
              <th>Description</th>
              <th style={{ width: 140 }}>Relevance</th>
              <th style={{ width: 160 }}>Origin</th>
              <th style={{ width: 90, textAlign: "right" }}>Used by</th>
              <th style={{ width: 70, textAlign: "right" }}>Version</th>
              <th style={{ width: 60 }}></th>
            </tr>
          </thead>
          <tbody>
            {D.property_definitions.map((p) => (
              <tr key={p.id}>
                <td className="mono">
                  <span className="row-link">{p.identifier}</span>
                </td>
                <td>{p.title}</td>
                <td className="muted" style={{ fontSize: 12.5 }}>
                  {p.description}
                </td>
                <td>{relevanceChip(p.is_relevant)}</td>
                <td className="mono muted" style={{ fontSize: 11.5 }}>
                  {p.origin}
                </td>
                <td className="num">{p.used_by}</td>
                <td className="num">v{p.version}</td>
                <td style={{ textAlign: "right" }}>
                  <button className="btn btn-ghost btn-icon">
                    <Icon name="more" size={12} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
window.PropertiesPage = PropertiesPage;

// =====================================================================
// Relationships — triples (s, p, o)
// =====================================================================
function RelationshipsPage({ onNav }) {
  const D = window.CS_DATA;
  const lookup = (id) =>
    D.classes.find((c) => c.id === id) || D.individuals.find((i) => i.id === id);
  return (
    <div className="canvas-inner" data-screen-label="05 Schema · Relationships">
      <div className="page-head">
        <div>
          <div className="page-head-meta">
            <span className="chip violet">
              <span className="dot"></span>schema
            </span>
            <span className="id-tag">node_type · relationship</span>
          </div>
          <h1>
            Relationships <span className="id-tag">/schema/relationships</span>
          </h1>
          <div className="subtitle">
            A relationship is a typed triple <span className="mono">(s, p, o)</span> between two
            graph nodes. Source and confidence are tracked separately from the data.
          </div>
        </div>
        <div className="page-actions">
          <button className="btn">
            <Icon name="ext" size={13} /> Export
          </button>
          <button className="btn btn-primary">
            <Icon name="plus" size={13} /> New relationship
          </button>
        </div>
      </div>
      <SchemaTabs active="schema/relationships" onNav={onNav} />

      <div className="panel">
        <table className="tbl">
          <thead>
            <tr>
              <th>Identifier</th>
              <th>Source</th>
              <th style={{ width: 160 }}>Predicate</th>
              <th>Target</th>
              <th style={{ width: 120 }}>Origin</th>
              <th style={{ width: 90, textAlign: "right" }}>Conf.</th>
              <th style={{ width: 110 }}>Created</th>
              <th style={{ width: 60 }}></th>
            </tr>
          </thead>
          <tbody>
            {D.relationships.map((r) => {
              const s = lookup(r.source_id);
              const t = lookup(r.target_id);
              const p = D.property_definitions.find((pd) => pd.id === r.property_definition_id);
              return (
                <tr key={r.id}>
                  <td className="mono">{r.id}</td>
                  <td>
                    <span className="kg-node-pill sm" data-domain={s?.domain || "default"}>
                      <span className="swatch"></span>
                      {s?.title}
                    </span>
                  </td>
                  <td className="mono">
                    <span className="row-link">— {p?.identifier} →</span>
                  </td>
                  <td>
                    <span className="kg-node-pill sm" data-domain={t?.domain || "default"}>
                      <span className="swatch"></span>
                      {t?.title}
                    </span>
                  </td>
                  <td className="mono muted" style={{ fontSize: 11.5 }}>
                    {r.source}
                  </td>
                  <td className="num">{r.confidence.toFixed(2)}</td>
                  <td className="mono muted" style={{ fontSize: 11.5 }}>
                    {r.created}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <button className="btn btn-ghost btn-icon">
                      <Icon name="more" size={12} />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
window.RelationshipsPage = RelationshipsPage;
