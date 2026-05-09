// Schema pages — Taxonomies, ConceptSchemes, Classes, Properties, Relationships
// Live-wired to the store with full CRUD via dialogs.

function PageHeader({ title, subtitle, badge, actions }) {
  return (
    <div className="page-head">
      <div>
        {badge && <div style={{ marginBottom: 6 }}>{badge}</div>}
        <h1>{title}</h1>
        {subtitle && <div className="subtitle">{subtitle}</div>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}

function FilterBar({ search, onSearch, children, placeholder = "Filter…" }) {
  return (
    <div className="filterbar">
      <div className="search-input">
        <Icon name="search" size={16} />
        <input
          className="input"
          placeholder={placeholder}
          value={search}
          onChange={(e) => onSearch(e.target.value)}
        />
      </div>
      {children}
    </div>
  );
}

function RowMenu({ items }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);
  return (
    <div className="row-menu" ref={ref}>
      <button
        className="btn btn-ghost btn-sm btn-icon"
        onClick={(e) => {
          e.stopPropagation();
          setOpen(!open);
        }}
        aria-label="More"
      >
        <Icon name="more" size={14} />
      </button>
      {open && (
        <div className="row-menu-pop">
          {items.map((it, i) =>
            it === "-" ? (
              <div key={i} className="row-menu-sep"></div>
            ) : (
              <button
                key={i}
                className={"row-menu-item" + (it.danger ? " danger" : "")}
                onClick={(e) => {
                  e.stopPropagation();
                  setOpen(false);
                  it.onClick();
                }}
              >
                {it.icon && <Icon name={it.icon} size={12} />}
                <span>{it.label}</span>
              </button>
            ),
          )}
        </div>
      )}
    </div>
  );
}

// =================== Taxonomies ===================
function TaxonomiesPage() {
  const { state, actions } = useStore();
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState(null);
  const [creating, setCreating] = useState(false);
  const [confirm, setConfirm] = useState(null);

  const filtered = state.taxonomies.filter((t) =>
    t.title.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="canvas-inner">
      <PageHeader
        title="Taxonomies"
        subtitle="Top-level domains. Concept schemes, classes, individuals all live within."
        actions={
          <>
            <button className="btn btn-ghost">
              <Icon name="ext" /> Import
            </button>
            <button className="btn btn-primary" onClick={() => setCreating(true)}>
              <Icon name="plus" /> New taxonomy
            </button>
          </>
        }
      />
      <FilterBar search={search} onSearch={setSearch} placeholder="Filter taxonomies…">
        <button className="btn btn-ghost btn-sm">
          <Icon name="filter" /> Domain
        </button>
        <button className="btn btn-ghost btn-sm">Sort: Recent</button>
      </FilterBar>
      <div className="panel">
        <table className="t">
          <thead>
            <tr>
              <th style={{ width: 36 }}>
                <span className="check"></span>
              </th>
              <th>Title</th>
              <th>Description</th>
              <th>Schemes</th>
              <th>Classes</th>
              <th>Individuals</th>
              <th style={{ width: 70 }}>Version</th>
              <th style={{ width: 80 }}></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((t) => {
              const schemes = state.concept_schemes.filter((s) => s.taxonomy_id === t.id).length;
              const classes = state.classes.filter((c) => c.taxonomy_id === t.id).length;
              const inds = state.individuals.filter((i) => {
                const c = state.classes.find((x) => x.id === i.class_ids[0]);
                return c?.taxonomy_id === t.id;
              }).length;
              return (
                <tr key={t.id}>
                  <td>
                    <span className="check"></span>
                  </td>
                  <td>
                    <div className="row gap-12">
                      <span
                        className="kg-node"
                        data-domain={t.domain}
                        style={{ height: 24, fontSize: 12 }}
                      >
                        <span className="swatch"></span>
                        {t.title}
                      </span>
                    </div>
                  </td>
                  <td className="muted">{t.description}</td>
                  <td className="mono">{schemes}</td>
                  <td className="mono">{classes}</td>
                  <td className="mono">{inds}</td>
                  <td>
                    <span className="version-pill">v{t.version}</span>
                  </td>
                  <td className="row-actions">
                    <RowMenu
                      items={[
                        { label: "Edit", icon: "edit", onClick: () => setEditing(t) },
                        { label: "Delete", icon: "x", danger: true, onClick: () => setConfirm(t) },
                      ]}
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <TaxonomyDialog open={creating} onClose={() => setCreating(false)} initial={null} />
      <TaxonomyDialog open={!!editing} onClose={() => setEditing(null)} initial={editing} />
      <ConfirmModal
        open={!!confirm}
        onClose={() => setConfirm(null)}
        title={"Delete " + (confirm?.title || "") + "?"}
        body={
          <>
            This taxonomy and its <strong>concept schemes must be empty</strong> first. The API
            returns <code>409 has_children</code> otherwise.
          </>
        }
        onConfirm={() => {
          try {
            actions.deleteTaxonomy(confirm.id);
            setConfirm(null);
          } catch {}
        }}
      />
    </div>
  );
}

// =================== Concept Schemes ===================
function ConceptSchemesPage() {
  const { state, actions } = useStore();
  const [search, setSearch] = useState("");
  const [taxFilter, setTaxFilter] = useState("all");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState(null);
  const [confirm, setConfirm] = useState(null);

  const filtered = state.concept_schemes.filter(
    (s) =>
      (taxFilter === "all" || s.taxonomy_id === taxFilter) &&
      s.title.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="canvas-inner">
      <PageHeader
        title={
          <>
            Concept schemes{" "}
            <span className="id-tag">
              {filtered.length} of {state.concept_schemes.length}
            </span>
          </>
        }
        subtitle="Concept schemes group related classes within a taxonomy."
        actions={
          <>
            <button className="btn btn-primary" onClick={() => setCreating(true)}>
              <Icon name="plus" /> New concept scheme
            </button>
          </>
        }
      />
      <FilterBar search={search} onSearch={setSearch} placeholder="Filter schemes…">
        <select
          className="input"
          style={{ width: 220, height: 30, fontSize: 12.5 }}
          value={taxFilter}
          onChange={(e) => setTaxFilter(e.target.value)}
        >
          <option value="all">All taxonomies</option>
          {state.taxonomies.map((t) => (
            <option key={t.id} value={t.id}>
              {t.title}
            </option>
          ))}
        </select>
      </FilterBar>
      <div className="panel">
        <table className="t">
          <thead>
            <tr>
              <th style={{ width: 36 }}>
                <span className="check"></span>
              </th>
              <th>Scheme</th>
              <th>Description</th>
              <th>Taxonomy</th>
              <th>Classes</th>
              <th style={{ width: 70 }}>Version</th>
              <th style={{ width: 80 }}></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((s) => {
              const t = state.taxonomies.find((x) => x.id === s.taxonomy_id);
              const classes = state.classes.filter((c) => c.concept_scheme_id === s.id).length;
              return (
                <tr key={s.id}>
                  <td>
                    <span className="check"></span>
                  </td>
                  <td>
                    <span
                      className="kg-node"
                      data-domain={s.domain}
                      style={{ height: 24, fontSize: 12 }}
                    >
                      <span className="swatch"></span>
                      {s.title}
                    </span>
                  </td>
                  <td className="muted">{s.description}</td>
                  <td>
                    <span className="mono muted" style={{ fontSize: 11.5 }}>
                      {t?.title}
                    </span>
                  </td>
                  <td className="mono">{classes}</td>
                  <td>
                    <span className="version-pill">v{s.version}</span>
                  </td>
                  <td className="row-actions">
                    <RowMenu
                      items={[
                        { label: "Edit", icon: "edit", onClick: () => setEditing(s) },
                        { label: "Delete", icon: "x", danger: true, onClick: () => setConfirm(s) },
                      ]}
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <ConceptSchemeDialog
        open={creating}
        onClose={() => setCreating(false)}
        initial={null}
        defaultTaxonomyId={taxFilter !== "all" ? taxFilter : null}
      />
      <ConceptSchemeDialog open={!!editing} onClose={() => setEditing(null)} initial={editing} />
      <ConfirmModal
        open={!!confirm}
        onClose={() => setConfirm(null)}
        title={"Delete " + (confirm?.title || "") + "?"}
        body={
          <>
            This scheme must be <strong>empty of classes</strong> first.
          </>
        }
        onConfirm={() => {
          try {
            actions.deleteScheme(confirm.id);
            setConfirm(null);
          } catch {}
        }}
      />
    </div>
  );
}

// =================== Classes ===================
function ClassesPage() {
  const { state, actions } = useStore();
  const [search, setSearch] = useState("");
  const [taxFilter, setTaxFilter] = useState("all");
  const [schemeFilter, setSchemeFilter] = useState("all");
  const [selectedId, setSelectedId] = useState(state.classes[0]?.id);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState(null);
  const [moving, setMoving] = useState(null);
  const [confirm, setConfirm] = useState(null);

  const filtered = state.classes.filter(
    (c) =>
      (taxFilter === "all" || c.taxonomy_id === taxFilter) &&
      (schemeFilter === "all" || c.concept_scheme_id === schemeFilter) &&
      c.title.toLowerCase().includes(search.toLowerCase()),
  );
  const selected = state.classes.find((c) => c.id === selectedId) || filtered[0];
  const visibleSchemes = state.concept_schemes.filter(
    (s) => taxFilter === "all" || s.taxonomy_id === taxFilter,
  );

  return (
    <div className="canvas-inner">
      <PageHeader
        title={
          <>
            Classes{" "}
            <span className="id-tag">
              {filtered.length} of {state.classes.length}
            </span>
          </>
        }
        subtitle="The structural backbone — concepts, classes, and their hierarchy."
        actions={
          <>
            <button className="btn btn-ghost">
              <Icon name="schema" /> View as tree
            </button>
            <button className="btn btn-primary" onClick={() => setCreating(true)}>
              <Icon name="plus" /> New class
            </button>
          </>
        }
      />

      <FilterBar search={search} onSearch={setSearch} placeholder="Filter classes…">
        <select
          className="input"
          style={{ width: 200, height: 30, fontSize: 12.5 }}
          value={taxFilter}
          onChange={(e) => {
            setTaxFilter(e.target.value);
            setSchemeFilter("all");
          }}
        >
          <option value="all">All taxonomies</option>
          {state.taxonomies.map((t) => (
            <option key={t.id} value={t.id}>
              {t.title}
            </option>
          ))}
        </select>
        <select
          className="input"
          style={{ width: 220, height: 30, fontSize: 12.5 }}
          value={schemeFilter}
          onChange={(e) => setSchemeFilter(e.target.value)}
        >
          <option value="all">All schemes</option>
          {visibleSchemes.map((s) => (
            <option key={s.id} value={s.id}>
              {s.title}
            </option>
          ))}
        </select>
      </FilterBar>

      <div className="split-2">
        <div className="panel">
          <table className="t">
            <thead>
              <tr>
                <th style={{ width: 36 }}>
                  <span className="check"></span>
                </th>
                <th>Class</th>
                <th>Scheme</th>
                <th>Parent</th>
                <th>Individuals</th>
                <th style={{ width: 60 }}>Ver</th>
                <th style={{ width: 60 }}></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((c) => {
                const parent = c.parent_class_id
                  ? state.classes.find((x) => x.id === c.parent_class_id)
                  : null;
                const scheme = state.concept_schemes.find((x) => x.id === c.concept_scheme_id);
                const indCount = state.individuals.filter((i) => i.class_ids.includes(c.id)).length;
                return (
                  <tr
                    key={c.id}
                    onClick={() => setSelectedId(c.id)}
                    style={{ cursor: "pointer" }}
                    className={selected?.id === c.id ? "selected" : ""}
                  >
                    <td>
                      <span className="check"></span>
                    </td>
                    <td>
                      <span
                        className="kg-node"
                        data-domain={c.domain}
                        style={{ height: 24, fontSize: 12 }}
                      >
                        <span className="swatch"></span>
                        {c.title}
                      </span>
                    </td>
                    <td className="mono muted" style={{ fontSize: 11.5 }}>
                      {scheme?.title}
                    </td>
                    <td>
                      {parent ? (
                        <span className="mono" style={{ fontSize: 11.5 }}>
                          {parent.title}
                        </span>
                      ) : (
                        <span className="muted mono" style={{ fontSize: 11 }}>
                          — root —
                        </span>
                      )}
                    </td>
                    <td className="mono">{indCount}</td>
                    <td>
                      <span className="version-pill">v{c.version}</span>
                    </td>
                    <td className="row-actions">
                      <RowMenu
                        items={[
                          { label: "Edit", icon: "edit", onClick: () => setEditing(c) },
                          { label: "Move to scheme…", icon: "arrow", onClick: () => setMoving(c) },
                          "-",
                          {
                            label: "Delete",
                            icon: "x",
                            danger: true,
                            onClick: () => setConfirm(c),
                          },
                        ]}
                      />
                    </td>
                  </tr>
                );
              })}
              {filtered.length === 0 && (
                <tr>
                  <td
                    colSpan={7}
                    style={{ padding: "24px", textAlign: "center", color: "var(--canvas-fg-3)" }}
                  >
                    No classes match these filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {selected && (
          <ClassDrawer
            cls={selected}
            onEdit={() => setEditing(selected)}
            onMove={() => setMoving(selected)}
            onDelete={() => setConfirm(selected)}
          />
        )}
      </div>

      <ClassDialog
        open={creating}
        onClose={() => setCreating(false)}
        initial={null}
        defaultSchemeId={schemeFilter !== "all" ? schemeFilter : null}
      />
      <ClassDialog open={!!editing} onClose={() => setEditing(null)} initial={editing} />
      <MoveClassDialog open={!!moving} onClose={() => setMoving(null)} cls={moving} />
      <ConfirmModal
        open={!!confirm}
        onClose={() => setConfirm(null)}
        title={"Delete " + (confirm?.title || "") + "?"}
        body={
          <>
            This class must have <strong>no children, individuals, or relationships</strong>. The
            API returns <code>409</code> otherwise.
          </>
        }
        onConfirm={() => {
          try {
            actions.deleteClass(confirm.id);
            setConfirm(null);
          } catch {}
        }}
      />
    </div>
  );
}

function ClassDrawer({ cls, onEdit, onMove, onDelete }) {
  const { state } = useStore();
  const [tab, setTab] = useState("overview");
  const tax = state.taxonomies.find((t) => t.id === cls.taxonomy_id);
  const scheme = state.concept_schemes.find((s) => s.id === cls.concept_scheme_id);
  const parent = cls.parent_class_id
    ? state.classes.find((x) => x.id === cls.parent_class_id)
    : null;
  const children = state.classes.filter((c) => c.parent_class_id === cls.id);
  const inds = state.individuals.filter((i) => i.class_ids.includes(cls.id));
  const rels = state.relationships.filter((r) => r.source_id === cls.id || r.target_id === cls.id);
  const structProp = state.property_definitions.find((p) => p.id === cls.structural_property_id);

  return (
    <div className="drawer">
      <div className="drawer-head">
        <div>
          <div className="title">{cls.title}</div>
          <div className="muted mono" style={{ fontSize: 11, marginTop: 2 }}>
            {cls.id} · v{cls.version}
          </div>
        </div>
        <div className="row" style={{ gap: 6 }}>
          <button className="btn btn-ghost btn-sm" onClick={onEdit}>
            <Icon name="edit" /> Edit
          </button>
          <RowMenu
            items={[
              { label: "Move to scheme…", icon: "arrow", onClick: onMove },
              "-",
              { label: "Delete class", icon: "x", danger: true, onClick: onDelete },
            ]}
          />
        </div>
      </div>
      <div className="drawer-tabs">
        {[
          ["overview", "Overview"],
          ["lexical", "Lexical · " + cls.lexical_senses.length],
          ["external", "External · " + cls.external_references.length],
          ["data", "Data props · " + cls.data_properties.length],
          ["rels", "Relationships · " + rels.length],
        ].map(([id, label]) => (
          <button
            key={id}
            className={"drawer-tab" + (tab === id ? " active" : "")}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="drawer-body">
        {tab === "overview" && (
          <>
            <p style={{ marginTop: 0, color: "var(--canvas-fg-2)" }}>{cls.description}</p>
            <dl className="kv">
              <dt>taxonomy</dt>
              <dd>
                <span
                  className="kg-node"
                  data-domain={tax?.domain}
                  style={{ height: 22, fontSize: 11.5 }}
                >
                  <span className="swatch"></span>
                  {tax?.title}
                </span>
              </dd>
              <dt>scheme</dt>
              <dd>
                <span
                  className="kg-node"
                  data-domain={scheme?.domain}
                  style={{ height: 22, fontSize: 11.5 }}
                >
                  <span className="swatch"></span>
                  {scheme?.title}
                </span>
              </dd>
              <dt>parent</dt>
              <dd>
                {parent ? (
                  <span
                    className="kg-node"
                    data-domain={parent.domain}
                    style={{ height: 22, fontSize: 11.5 }}
                  >
                    <span className="swatch"></span>
                    {parent.title}
                  </span>
                ) : (
                  <span className="muted">— root —</span>
                )}
              </dd>
              <dt>children</dt>
              <dd>
                {children.length ? (
                  <div className="row" style={{ flexWrap: "wrap", gap: 4 }}>
                    {children.map((c) => (
                      <span key={c.id} className="chip">
                        {c.title}
                      </span>
                    ))}
                  </div>
                ) : (
                  <span className="muted">none</span>
                )}
              </dd>
              <dt>structural prop</dt>
              <dd>
                {structProp ? (
                  <span className="mono" style={{ fontSize: 11.5 }}>
                    {structProp.identifier}
                  </span>
                ) : (
                  <span className="muted">—</span>
                )}
              </dd>
              <dt>individuals</dt>
              <dd className="mono">{inds.length}</dd>
            </dl>
          </>
        )}
        {tab === "lexical" &&
          (cls.lexical_senses.length ? (
            <table className="mini-t">
              <thead>
                <tr>
                  <th>Label</th>
                  <th>Lang</th>
                  <th>Sense</th>
                </tr>
              </thead>
              <tbody>
                {cls.lexical_senses.map((s, i) => (
                  <tr key={i}>
                    <td>{s.label}</td>
                    <td className="mono">{s.language}</td>
                    <td>
                      <span className="chip gray">{s.sense_type}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="empty-mini">No lexical senses defined.</div>
          ))}
        {tab === "external" &&
          (cls.external_references.length ? (
            <ul className="ref-list">
              {cls.external_references.map((r, i) => (
                <li key={i}>
                  <span className="chip cyan">{r.source}</span>
                  <span className="mono">{r.identifier}</span>
                  {r.url && (
                    <a href={r.url} target="_blank" rel="noreferrer" className="ref-link">
                      <Icon name="ext" size={11} />
                    </a>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <div className="empty-mini">No external references.</div>
          ))}
        {tab === "data" &&
          (cls.data_properties.length ? (
            <table className="mini-t">
              <thead>
                <tr>
                  <th>Key</th>
                  <th>Value</th>
                  <th>Datatype</th>
                </tr>
              </thead>
              <tbody>
                {cls.data_properties.map((p, i) => (
                  <tr key={i}>
                    <td className="mono">{p.key}</td>
                    <td>{p.value}</td>
                    <td className="mono muted">{p.datatype || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="empty-mini">No data properties.</div>
          ))}
        {tab === "rels" &&
          (rels.length ? (
            <ul className="ref-list">
              {rels.map((r) => {
                const dir = r.source_id === cls.id ? "out" : "in";
                const otherId = dir === "out" ? r.target_id : r.source_id;
                const other =
                  state.classes.find((x) => x.id === otherId) ||
                  state.individuals.find((x) => x.id === otherId);
                const prop = state.property_definitions.find(
                  (p) => p.id === r.property_definition_id,
                );
                return (
                  <li key={r.id} className="rel-mini">
                    <span className={"rel-dir " + dir}>{dir === "out" ? "→" : "←"}</span>
                    <span className="mono cyan-text">{prop?.identifier || "?"}</span>
                    <span
                      className="kg-node"
                      data-domain={other?.domain || "default"}
                      style={{ height: 20, fontSize: 11 }}
                    >
                      <span className="swatch"></span>
                      {other?.title || other?.id}
                    </span>
                  </li>
                );
              })}
            </ul>
          ) : (
            <div className="empty-mini">No relationships involving this class.</div>
          ))}
      </div>
    </div>
  );
}

// =================== Properties ===================
function PropertiesPage() {
  const { state, actions } = useStore();
  const [search, setSearch] = useState("");
  const [relevance, setRelevance] = useState("all");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState(null);
  const [confirm, setConfirm] = useState(null);

  const filtered = state.property_definitions.filter((p) => {
    if (relevance !== "all") {
      if (relevance === "null" && p.is_relevant !== null) return false;
      if (relevance === "true" && p.is_relevant !== true) return false;
      if (relevance === "false" && p.is_relevant !== false) return false;
    }
    return (
      p.title.toLowerCase().includes(search.toLowerCase()) ||
      p.identifier.includes(search.toLowerCase())
    );
  });

  const counts = {
    all: state.property_definitions.length,
    null: state.property_definitions.filter((p) => p.is_relevant === null).length,
    true: state.property_definitions.filter((p) => p.is_relevant === true).length,
    false: state.property_definitions.filter((p) => p.is_relevant === false).length,
  };

  return (
    <div className="canvas-inner">
      <PageHeader
        title="Property definitions"
        subtitle="Properties name relationships. Auto-created when a relationship references an unknown identifier."
        actions={
          <>
            <button className="btn btn-primary" onClick={() => setCreating(true)}>
              <Icon name="plus" /> New property
            </button>
          </>
        }
      />
      <div className="tabs">
        <div
          className={"tab" + (relevance === "all" ? " active" : "")}
          onClick={() => setRelevance("all")}
        >
          All <span className="count">{counts.all}</span>
        </div>
        <div
          className={"tab" + (relevance === "null" ? " active" : "")}
          onClick={() => setRelevance("null")}
        >
          Not evaluated <span className="count">{counts.null}</span>
        </div>
        <div
          className={"tab" + (relevance === "true" ? " active" : "")}
          onClick={() => setRelevance("true")}
        >
          Relevant <span className="count">{counts.true}</span>
        </div>
        <div
          className={"tab" + (relevance === "false" ? " active" : "")}
          onClick={() => setRelevance("false")}
        >
          Irrelevant <span className="count">{counts.false}</span>
        </div>
      </div>
      <FilterBar
        search={search}
        onSearch={setSearch}
        placeholder="Filter by title or identifier…"
      />
      <div className="panel">
        <table className="t">
          <thead>
            <tr>
              <th style={{ width: 36 }}>
                <span className="check"></span>
              </th>
              <th>Title</th>
              <th>Identifier</th>
              <th>Description</th>
              <th>Origin</th>
              <th>Used in</th>
              <th>Relevance</th>
              <th style={{ width: 60 }}>Ver</th>
              <th style={{ width: 80 }}></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((p) => {
              const usage = state.relationships.filter(
                (r) => r.property_definition_id === p.id,
              ).length;
              const relCls =
                p.is_relevant === true ? "emerald" : p.is_relevant === false ? "rose" : "gray";
              const relLabel =
                p.is_relevant === true
                  ? "Relevant"
                  : p.is_relevant === false
                    ? "Irrelevant"
                    : "Not evaluated";
              return (
                <tr key={p.id}>
                  <td>
                    <span className="check"></span>
                  </td>
                  <td>{p.title}</td>
                  <td className="mono">{p.identifier}</td>
                  <td className="muted">{p.description}</td>
                  <td>
                    {p.origin === "auto" ? (
                      <span className="chip cyan">auto</span>
                    ) : (
                      <span className="chip gray">manual</span>
                    )}
                  </td>
                  <td className="mono">{usage}</td>
                  <td>
                    <span className={"chip " + relCls}>{relLabel}</span>
                  </td>
                  <td>
                    <span className="version-pill">v{p.version}</span>
                  </td>
                  <td className="row-actions">
                    <RowMenu
                      items={[
                        { label: "Edit", icon: "edit", onClick: () => setEditing(p) },
                        "-",
                        { label: "Delete", icon: "x", danger: true, onClick: () => setConfirm(p) },
                      ]}
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <PropertyDialog open={creating} onClose={() => setCreating(false)} initial={null} />
      <PropertyDialog open={!!editing} onClose={() => setEditing(null)} initial={editing} />
      <ConfirmModal
        open={!!confirm}
        onClose={() => setConfirm(null)}
        title={"Delete " + (confirm?.title || "") + "?"}
        body={
          <>
            Properties in use by relationships return <code>409 in_use</code>.
          </>
        }
        onConfirm={() => {
          try {
            actions.deletePropertyDefinition(confirm.id);
            setConfirm(null);
          } catch {}
        }}
      />
    </div>
  );
}

// =================== Relationships ===================
function RelationshipsPage() {
  const { state, actions } = useStore();
  const [search, setSearch] = useState("");
  const [propFilter, setPropFilter] = useState("all");
  const [creating, setCreating] = useState(false);
  const [confirm, setConfirm] = useState(null);
  const [view, setView] = useState("graph");

  const lookup = (id) => {
    const c = state.classes.find((x) => x.id === id);
    if (c) return { node: c, kind: "class" };
    const i = state.individuals.find((x) => x.id === id);
    if (i) {
      const cc = state.classes.find((x) => x.id === i.class_ids[0]);
      return { node: { ...i, domain: cc?.domain || "default" }, kind: "individual" };
    }
    return { node: { title: id, domain: "default" }, kind: "?" };
  };

  const filtered = state.relationships.filter((r) => {
    if (propFilter !== "all" && r.property_definition_id !== propFilter) return false;
    if (!search) return true;
    const s = lookup(r.source_id).node.title.toLowerCase();
    const t = lookup(r.target_id).node.title.toLowerCase();
    const p = state.property_definitions.find((x) => x.id === r.property_definition_id);
    return (
      s.includes(search.toLowerCase()) ||
      t.includes(search.toLowerCase()) ||
      (p?.identifier || "").includes(search.toLowerCase())
    );
  });

  return (
    <div className="canvas-inner">
      <PageHeader
        title={
          <>
            Relationships{" "}
            <span className="id-tag">
              {filtered.length} of {state.relationships.length}
            </span>
          </>
        }
        subtitle="Typed directed edges between classes and individuals. Mixed endpoints are allowed."
        actions={
          <>
            <div className="view-toggle" role="tablist" aria-label="View mode">
              <button className={view === "table" ? "on" : ""} onClick={() => setView("table")}>
                <Icon name="table" size={13} /> Table
              </button>
              <button className={view === "graph" ? "on" : ""} onClick={() => setView("graph")}>
                <Icon name="graph" size={13} /> Graph
              </button>
            </div>
            <button className="btn btn-primary" onClick={() => setCreating(true)}>
              <Icon name="plus" /> New relationship
            </button>
          </>
        }
      />

      {view === "graph" ? (
        <window.GraphView />
      ) : (
        <>
          <FilterBar
            search={search}
            onSearch={setSearch}
            placeholder="Filter by subject, object, or predicate…"
          >
            <select
              className="input"
              style={{ width: 220, height: 30, fontSize: 12.5 }}
              value={propFilter}
              onChange={(e) => setPropFilter(e.target.value)}
            >
              <option value="all">All predicates</option>
              {state.property_definitions.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.identifier}
                </option>
              ))}
            </select>
          </FilterBar>
          <div className="panel">
            <table className="t">
              <thead>
                <tr>
                  <th>Subject</th>
                  <th style={{ width: 36 }}></th>
                  <th>Predicate</th>
                  <th style={{ width: 36 }}></th>
                  <th>Object</th>
                  <th>Source</th>
                  <th>Confidence</th>
                  <th style={{ width: 60 }}></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((r) => {
                  const s = lookup(r.source_id);
                  const o = lookup(r.target_id);
                  const prop = state.property_definitions.find(
                    (p) => p.id === r.property_definition_id,
                  );
                  return (
                    <tr key={r.id}>
                      <td>
                        <span
                          className="kg-node"
                          data-domain={s.node.domain}
                          style={{ height: 22, fontSize: 11.5 }}
                        >
                          <span className="swatch"></span>
                          {s.node.title}
                        </span>
                        <span className="mono muted" style={{ fontSize: 10, marginLeft: 6 }}>
                          {s.kind}
                        </span>
                      </td>
                      <td>
                        <span className="rel-arrow-cell">▶</span>
                      </td>
                      <td>
                        <span className="mono cyan-text">{prop?.identifier || "—"}</span>
                        {prop?.is_relevant === false && (
                          <span className="chip rose" style={{ marginLeft: 6 }}>
                            irrelevant
                          </span>
                        )}
                      </td>
                      <td>
                        <span className="rel-arrow-cell">▶</span>
                      </td>
                      <td>
                        <span
                          className="kg-node"
                          data-domain={o.node.domain}
                          style={{ height: 22, fontSize: 11.5 }}
                        >
                          <span className="swatch"></span>
                          {o.node.title}
                        </span>
                        <span className="mono muted" style={{ fontSize: 10, marginLeft: 6 }}>
                          {o.kind}
                        </span>
                      </td>
                      <td className="mono muted" style={{ fontSize: 12 }}>
                        {r.source}
                      </td>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <div
                            style={{
                              width: 60,
                              height: 4,
                              background: "var(--canvas-bg-2)",
                              borderRadius: 2,
                              overflow: "hidden",
                            }}
                          >
                            <div
                              style={{
                                width: `${r.confidence * 100}%`,
                                height: "100%",
                                background:
                                  r.confidence > 0.9
                                    ? "var(--accent-emerald)"
                                    : "var(--accent-amber)",
                              }}
                            ></div>
                          </div>
                          <span className="mono" style={{ fontSize: 11.5 }}>
                            {r.confidence.toFixed(2)}
                          </span>
                        </div>
                      </td>
                      <td className="row-actions">
                        <RowMenu
                          items={[
                            {
                              label: "Delete",
                              icon: "x",
                              danger: true,
                              onClick: () => setConfirm(r),
                            },
                          ]}
                        />
                      </td>
                    </tr>
                  );
                })}
                {filtered.length === 0 && (
                  <tr>
                    <td
                      colSpan={8}
                      style={{ padding: "24px", textAlign: "center", color: "var(--canvas-fg-3)" }}
                    >
                      No relationships match.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <RelationshipDialog open={creating} onClose={() => setCreating(false)} />
          <ConfirmModal
            open={!!confirm}
            onClose={() => setConfirm(null)}
            title="Delete relationship?"
            body="The triple will be removed. The property definition stays — delete that separately if no longer in use."
            onConfirm={() => {
              actions.deleteRelationship(confirm.id);
              setConfirm(null);
            }}
          />
        </>
      )}
    </div>
  );
}

window.TaxonomiesPage = TaxonomiesPage;
window.ConceptSchemesPage = ConceptSchemesPage;
window.ClassesPage = ClassesPage;
window.PropertiesPage = PropertiesPage;
window.RelationshipsPage = RelationshipsPage;
window.PageHeader = PageHeader;
window.FilterBar = FilterBar;
window.RowMenu = RowMenu;
