// =========================================================================
// Context Studio — Datasets (Data › Datasets · /data/datasets)
// Admin surface for the importable knowledge-source snapshots the server
// exposes at /api/v1/admin/datasets. Unlike the graph-node entities, a
// dataset is a versioned file import with a contents summary and one piece
// of exclusive state: exactly one dataset is ACTIVE (the working set every
// extraction / graph / query operation targets). This page is built on the
// same kit primitives as EntitySurface (SelectableTable + InlineInspector)
// but adds the activate semantic, a file-aware identity panel, and a
// metrics readout — none of which fit the shared graph machinery.
// =========================================================================

// ---- helpers -----------------------------------------------------------
function dsSlug(s) {
  return (s || "").toLowerCase().trim()
    .replace(/[^a-z0-9]+/g, "_").replace(/_{2,}/g, "_").replace(/^_+|_+$/g, "");
}
function dsNewDraft() {
  return { id: "", title: "", filename: "", description: "", schema_version: "2.0", is_active: false,
    metrics: { layers_count: 0, domains_count: 0, terms_count: 0, relationships_count: 0, individuals_count: 0 } };
}
// crude extension → icon (Heimdall icon set)
function fileIconFor(filename) {
  const ext = (filename || "").split(".").pop().toLowerCase();
  if (["db", "sql", "sqlite"].includes(ext)) return "hardDrive";
  if (["ttl", "owl", "rdf"].includes(ext)) return "schema";
  if (["json", "jsonl"].includes(ext)) return "component";
  if (["csv", "tsv"].includes(ext)) return "data";
  return "file";
}
function dsExtLabel(filename) {
  const ext = (filename || "").split(".").pop().toUpperCase();
  return ext || "FILE";
}

const monoSm = { fontFamily: "var(--font-mono)", fontSize: 11.5, color: "rgb(var(--canvas-fg-3))" };

// local FilterBar (the one in cs/crud/pages.jsx is module-scoped, not on window)
function FilterBar({ q, setQ, placeholder, total, shown, children }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
      <div style={{ flex: "0 1 340px", position: "relative" }}>
        <div style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "rgb(var(--canvas-fg-3))", pointerEvents: "none" }}><Icon name="search" size={13} /></div>
        <TextInput value={q} onChange={(e) => setQ(e.target.value)} placeholder={placeholder} style={{ paddingLeft: 30, width: "100%" }} />
      </div>
      {children}
      <span style={{ marginLeft: "auto", fontFamily: "var(--font-mono)", fontSize: 11, color: "rgb(var(--canvas-fg-3))" }}>showing {shown} of {total}</span>
    </div>
  );
}

// ---- contents (metrics) grid ------------------------------------------
function DatasetMetrics({ metrics }) {
  const m = metrics || {};
  const cells = [
    { label: "Layers", value: m.layers_count ?? 0, icon: "schema" },
    { label: "Domains", value: m.domains_count ?? 0, icon: "folder" },
    { label: "Terms", value: m.terms_count ?? 0, icon: "component" },
    { label: "Relationships", value: m.relationships_count ?? 0, icon: "link" },
    { label: "Individuals", value: m.individuals_count ?? 0, icon: "data" },
  ];
  return (
    <div className="ds-metrics">
      {cells.map((c) => (
        <div key={c.label} className="ds-metric">
          <div className="ds-metric__top"><Icon name={c.icon} size={12} /><span>{c.label}</span></div>
          <div className="ds-metric__val">{c.value}</div>
        </div>
      ))}
    </div>
  );
}

const kvRowD = (key, value) => ({ key, value });

// =========================================================================
// DatasetInspector — view / inline-edit / create, built on InlineInspector.
// =========================================================================
function DatasetInspector({ entity, mode, initialDraft, onEnterEdit, onDone, onCreated, onCancel, onDelete, onDuplicate, onActivate }) {
  const isCreate = mode === "create";
  const isEdit = mode === "edit";
  const active = isCreate || isEdit;

  const [draft, setDraft] = useState(() => initialDraft || dsNewDraft());
  const cur = isCreate ? draft : (entity || {});
  const setField = (k, v) => setDraft((d) => ({ ...d, [k]: v }));
  const saveField = (k) => (isCreate ? (v) => setField(k, v) : (v) => CSStore.update("dataset", entity.id, { [k]: v }, { field: k }));
  const liveField = (k) => (isCreate ? (v) => setField(k, v) : undefined);

  const idVal = isCreate ? (draft.id || (draft.title ? "ds_" + dsSlug(draft.title) : "")) : entity.id;
  const validId = isCreate && CSStore.validateIdent("dataset", idVal) === null && draft.title.trim() && draft.filename.trim();
  const create = () => {
    const row = CSStore.create("dataset", { ...draft, id: idVal, created_at: "today", last_accessed: "now" });
    onCreated(row.id);
  };

  const isActive = !isCreate && entity.is_active;

  return (
    <InlineInspector mode={mode} typeLabel="dataset" eyebrow={`DATASET · ${dsExtLabel(cur.filename)} · v${cur.schema_version || "—"}`}
      title={cur.title} id={idVal || "—"} version={entity?.version}
      onEdit={onEnterEdit} onDone={onDone} onCreate={create} onCancel={onCancel} canCreate={validId}
      onDelete={onDelete} onDuplicate={onDuplicate} footerHint={`PUT /api/v1/admin/datasets/${idVal || "…"}`}>

      <InspectorPanel.Section title="Identity">
        <KVGrid keyWidth={120} rows={[
          kvRowD("IDENTIFIER", isCreate
            ? <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "rgb(var(--canvas-fg-3))" }}>{idVal || "ds_…"}<span style={{ marginLeft: 8, fontSize: 10.5 }}>auto from title</span></span>
            : <span style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>{entity.id}</span>),
          kvRowD("TITLE", <EditableField active={active} value={cur.title} onSave={saveField("title")} onChangeLive={liveField("title")} placeholder="Dataset name" autoFocus={isCreate} />),
          kvRowD("FILENAME", <EditableField active={active} value={cur.filename} mono kind="text" onSave={saveField("filename")} onChangeLive={liveField("filename")} placeholder="source.jsonl" />),
          kvRowD("SCHEMA", isCreate
            ? <EditableField active kind="select" value={cur.schema_version} options={[{ value: "2.0", label: "2.0 (current)" }, { value: "1.2", label: "1.2" }, { value: "1.0", label: "1.0" }]} onSave={saveField("schema_version")} />
            : <Chip variant={(entity.schema_version || "").startsWith("2") ? "cyan" : "neutral"}>v{entity.schema_version}</Chip>),
          kvRowD("DESCRIPTION", <SuggestField active={active} value={cur.description} type="dataset" entityId={entity?.id} title={cur.title} onSave={saveField("description")} onChangeLive={liveField("description")} rows={3} />),
        ]} />
      </InspectorPanel.Section>

      {!isCreate && (
        <>
          <InspectorPanel.Section title="Status" actions={isActive ? <Chip variant="emerald">active</Chip> : null}>
            {isActive ? (
              <div className="ds-callout">
                <Icon name="check" size={15} />
                <span>This is the <strong>active</strong> dataset — every extraction, graph and query operation in this workspace targets it.</span>
              </div>
            ) : (
              <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                <span style={{ fontSize: 12.5, color: "rgb(var(--canvas-fg-2))" }}>Inactive — loaded but not the current working set.</span>
                <Button variant="primary" size="sm" onClick={() => onActivate(entity.id)} style={{ marginLeft: "auto" }}>
                  <Icon name="check" size={13} /> Activate dataset
                </Button>
              </div>
            )}
          </InspectorPanel.Section>

          <InspectorPanel.Section title="Contents" actions={<span style={monoSm}>once loaded</span>}>
            <DatasetMetrics metrics={entity.metrics} />
          </InspectorPanel.Section>

          <InspectorPanel.Section title="Provenance">
            <KVGrid keyWidth={120} rows={[
              kvRowD("SOURCE FILE", <span style={{ display: "inline-flex", alignItems: "center", gap: 7, fontFamily: "var(--font-mono)", fontSize: 11.5 }}><Icon name={fileIconFor(entity.filename)} size={13} />{entity.filename}</span>),
              kvRowD("IMPORTED", <span style={monoSm}>{entity.created_at}</span>),
              kvRowD("LAST ACCESSED", <span style={monoSm}>{entity.last_accessed}</span>),
              kvRowD("VERSION", <span style={{ fontFamily: "var(--font-mono)" }}>{entity.version}</span>),
            ]} />
          </InspectorPanel.Section>
        </>
      )}
    </InlineInspector>
  );
}

// =========================================================================
// DatasetSurface — master/detail tailored to datasets (mirrors EntitySurface
// but renders DatasetInspector and wires the activate action everywhere).
// =========================================================================
const DatasetSurface = forwardRef(function DatasetSurface({ rows, columns, inspectorWidth = 460 }, ref) {
  const data = useCS();
  const collection = data.datasets;

  const [selectedId, setSelectedId] = useState(null);
  const [mode, setMode] = useState("view");
  const [initialDraft, setInitialDraft] = useState(null);
  const [draftKey, setDraftKey] = useState(0);
  const [selection, setSelection] = useState(() => new Set());
  const [del, setDel] = useState({ open: false, target: null, ids: null });

  const entity = selectedId ? collection.find((x) => x.id === selectedId) : null;
  const isCreate = mode === "create";
  const showRail = (mode === "view" || mode === "edit") && !!entity;
  const isEmpty = collection.length === 0;

  const startCreate = () => { setInitialDraft(dsNewDraft()); setSelectedId(null); setMode("create"); setDraftKey((k) => k + 1); };
  useImperativeHandle(ref, () => ({ startCreate }), []);

  const selectRow = (row) => { setSelectedId(row.id); setMode("view"); };
  const onCreated = (id) => { setSelectedId(id); setMode("view"); };
  const activate = (id) => CSStore.activateDataset(id);

  const duplicate = (e) => {
    setInitialDraft({ ...dsNewDraft(), title: (e.title || "") + " (copy)", filename: e.filename, description: e.description, schema_version: e.schema_version });
    setSelectedId(null); setMode("create"); setDraftKey((k) => k + 1);
  };

  const confirmDelete = () => {
    if (del.ids) { CSStore.bulkRemove("dataset", del.ids); setSelection(new Set()); }
    else if (del.target) { CSStore.remove("dataset", del.target.id); if (selectedId === del.target.id) setSelectedId(null); }
    setDel({ open: false, target: null, ids: null });
  };

  const toggle = (id) => setSelection((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const toggleAll = (on) => setSelection(on ? new Set(rows.map((r) => r.id)) : new Set());

  const rowActions = (row) => [
    ...(row.is_active ? [{ id: "active", label: "Active (current)", icon: "check", disabled: true }]
      : [{ id: "activate", label: "Activate", icon: "check" }]),
    { id: "edit", label: "Edit", icon: "edit" },
    { id: "duplicate", label: "Duplicate", icon: "copy" },
    { type: "separator" },
    { id: "delete", label: "Delete…", icon: "trash", danger: true },
  ];
  const onRowAction = (row, a) => {
    if (a === "activate") activate(row.id);
    if (a === "edit") { setSelectedId(row.id); setMode("edit"); }
    if (a === "duplicate") duplicate(row);
    if (a === "delete") setDel({ open: true, target: row, ids: null });
  };

  return (
    <>
      {(isCreate || !isEmpty) ? (
        <div style={{ display: "grid", gridTemplateColumns: (isCreate || showRail) ? `1fr ${inspectorWidth}px` : "1fr", gap: 14, alignItems: "start" }}>
          <SelectableTable
            columns={columns} data={rows} selectedId={selectedId} onRowClick={selectRow}
            selection={selection} onToggle={toggle} onToggleAll={toggleAll}
            rowActions={rowActions} onRowAction={onRowAction}
          />
          {(isCreate || (showRail && entity)) && (
            <DatasetInspector key={isCreate ? `create-${draftKey}` : `${entity.id}-${mode}`}
              entity={entity} mode={mode} initialDraft={initialDraft}
              onEnterEdit={() => setMode("edit")} onDone={() => setMode("view")}
              onCreated={onCreated} onCancel={() => { setMode("view"); setInitialDraft(null); }}
              onDelete={() => setDel({ open: true, target: entity, ids: null })}
              onDuplicate={() => duplicate(entity)} onActivate={activate} />
          )}
        </div>
      ) : (
        <CreateEmptyState icon="data" noun="dataset" onCreate={startCreate} />
      )}

      <BulkBar
        count={selection.size} label="dataset"
        actions={[{ id: "delete", label: "Delete", icon: "trash", danger: true }]}
        onAction={(id) => { if (id === "delete") setDel({ open: true, target: null, ids: [...selection] }); }}
        onClear={() => setSelection(new Set())}
      />

      <Modal isOpen={del.open} onClose={() => setDel({ open: false, target: null, ids: null })}
        title={del.ids ? `Delete ${del.ids.length} dataset${del.ids.length === 1 ? "" : "s"}?` : `Delete ${del.target ? del.target.title : "dataset"}?`}
        subtitle="The import record is removed from the workspace. The original source file on disk is left untouched."
        hintFooter="DELETE /api/v1/admin/datasets"
        footer={<><Button variant="ghost" onClick={() => setDel({ open: false, target: null, ids: null })}>Cancel</Button><Button variant="danger" onClick={confirmDelete}><Icon name="trash" size={13} /> Delete</Button></>}>
        {del.target && del.target.is_active && (
          <div className="ds-callout ds-callout--warn">
            <Icon name="alert" size={15} />
            <span>This is the active dataset. Deleting it leaves the workspace with no active working set until you activate another.</span>
          </div>
        )}
      </Modal>
    </>
  );
});

// =========================================================================
// CSDatasets — the page (PageHeader + active banner + filters + surface)
// =========================================================================
function CSDatasets({ onNav }) {
  const data = useCS();
  const surf = useRef(null);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("all");

  // pick up a "New dataset…" request fired from the command palette
  useEffect(() => {
    const p = window.__CS_PENDING;
    if (p && p.type === "dataset") {
      window.__CS_PENDING = null;
      const t = setTimeout(() => surf.current && surf.current.startCreate(), 30);
      return () => clearTimeout(t);
    }
  }, []);


  const activeDs = data.datasets.find((d) => d.is_active);
  const rows = data.datasets.filter((d) => {
    if (status === "active" && !d.is_active) return false;
    if (status === "inactive" && d.is_active) return false;
    if (!q) return true;
    return (d.title + d.id + d.filename + (d.description || "")).toLowerCase().includes(q.toLowerCase());
  });

  const statusCell = (_, d) => (
    <span className={"ds-dot" + (d.is_active ? " ds-dot--on" : "")} title={d.is_active ? "Active" : "Inactive"} />
  );

  return (
    <div data-screen-label="08 Data · Datasets">
      <PageHeader eyebrow="DATA · admin · dataset" title="Datasets" idChip="/data/datasets"
        subtitle="Imported knowledge-source snapshots. Each dataset is a versioned file import; exactly one is active at a time — the working set every extraction and query targets."
        actions={<>
          <Button variant="ghost"><Icon name="download" size={13} /> Import…</Button>
          <Button variant="primary" onClick={() => surf.current.startCreate()}><Icon name="plus" size={13} /> New dataset</Button>
        </>} />

      <div style={{ height: 14 }} />

      {activeDs && (
        <div className="ds-active-banner">
          <span className="ds-dot ds-dot--on" />
          <span className="ds-active-banner__label">ACTIVE WORKING SET</span>
          <span className="ds-active-banner__title">{activeDs.title}</span>
          <span className="ds-active-banner__file"><Icon name={fileIconFor(activeDs.filename)} size={12} /> {activeDs.filename}</span>
          <span className="ds-active-banner__meta">{activeDs.metrics.individuals_count} individuals · {activeDs.metrics.terms_count} terms · {activeDs.metrics.relationships_count} relationships</span>
        </div>
      )}

      <FilterBar q={q} setQ={setQ} placeholder="Search datasets, filenames, descriptions…" total={data.datasets.length} shown={rows.length}>
        <SegmentedControl value={status} onChange={setStatus} options={[
          { value: "all", label: "All" }, { value: "active", label: "Active" }, { value: "inactive", label: "Inactive" },
        ]} />
      </FilterBar>

      <DatasetSurface ref={surf} rows={rows}
        columns={[
          { key: "active_dot", label: "", width: "34px", render: statusCell },
          { key: "id", label: "Identifier", width: "150px", render: (v) => <span style={{ fontFamily: "var(--font-mono)", fontSize: 12.5 }}>{v}</span> },
          { key: "title", label: "Name", render: (v) => <span style={{ fontWeight: 500 }}>{v}</span> },
          { key: "filename", label: "Source file", width: "190px", render: (v) => (
            <span style={{ display: "inline-flex", alignItems: "center", gap: 7, fontFamily: "var(--font-mono)", fontSize: 11.5, color: "rgb(var(--canvas-fg-2))" }}><Icon name={fileIconFor(v)} size={13} />{v}</span>
          ) },
          { key: "description", label: "Description", render: (v) => <span style={{ color: "rgb(var(--canvas-fg-3))", fontSize: 12.5 }}>{v ? (v.length > 64 ? v.slice(0, 64) + "…" : v) : "—"}</span> },
          { key: "metrics", label: "Individuals", width: "92px", render: (m) => <span style={{ fontFamily: "var(--font-mono)", textAlign: "right", display: "block" }}>{m.individuals_count}</span> },
          { key: "schema_version", label: "Schema", width: "84px", render: (v) => <Chip variant={(v || "").startsWith("2") ? "cyan" : "neutral"}>v{v}</Chip> },
          { key: "is_active", label: "Status", width: "104px", render: (v) => v ? <Chip variant="emerald">active</Chip> : <Chip variant="neutral">inactive</Chip> },
          { key: "version", label: "Ver", width: "56px", render: (v) => <VersionPill>{v}</VersionPill> },
        ]} />
    </div>
  );
}

window.CSDatasets = CSDatasets;
