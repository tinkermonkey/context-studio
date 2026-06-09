// =========================================================================
// Context Studio — CRUD kit
// Reusable interaction components composed from Heimdall primitives:
//   DomainPill, EditableField, SuggestField, InlineInspector, EmptyInspector,
//   SelectableTable, BulkBar, CascadeDeleteDialog, ParamSlider, VariableChips.
// All exported to window for the page/inspector scripts that load after this.
// =========================================================================

const DOMAIN_COLOR = { life: "emerald", climate: "amber", software: "violet", default: "neutral" };
const domainColorOf = (d) => DOMAIN_COLOR[d] || "neutral";

function DomainPill({ domain, label }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontFamily: "var(--font-mono)", fontSize: 11.5 }}>
      <span className="cs-domain-dot" style={{ background: `var(--dom-${domain || "default"})` }} />
      <span>{label}</span>
    </span>
  );
}

// transient "saved" flash, per field
function useSavedFlash() {
  const [on, setOn] = useState(false);
  const t = useRef(null);
  const fire = useCallback(() => {
    setOn(true);
    clearTimeout(t.current);
    t.current = setTimeout(() => setOn(false), 1600);
  }, []);
  useEffect(() => () => clearTimeout(t.current), []);
  return { on, fire };
}

// -------------------------------------------------------------------------
// EditableField — one row's value. Reads as text in view mode; in `active`
// mode it's an input that saves on blur (optimistic) with a saved flash.
// Selects commit immediately. `validate(value)` shows a live inline error and
// blocks the save while invalid.
// -------------------------------------------------------------------------
function EditableField({
  active, value, onSave, onChangeLive, kind = "text", options = [],
  placeholder = "—", mono = false, rows = 3, validate, autoFocus = false,
}) {
  const [buf, setBuf] = useState(value ?? "");
  const [focused, setFocused] = useState(false);
  const flash = useSavedFlash();
  useEffect(() => { if (!focused) setBuf(value ?? ""); }, [value, focused]);

  const err = validate ? validate(buf) : null;

  const commit = (v) => {
    if (v === (value ?? "")) return;
    if (validate && validate(v)) return;
    onSave && onSave(v);
    flash.fire();
  };

  if (!active) {
    const empty = value === undefined || value === null || value === "";
    return (
      <span className={"ce-view"} style={{ cursor: "default" }}>
        {empty ? <span className="ce-view__placeholder">{placeholder}</span>
          : (mono ? <span style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>{value}</span> : value)}
      </span>
    );
  }

  const onChange = (v) => { setBuf(v); onChangeLive && onChangeLive(v); };

  let control;
  if (kind === "select") {
    control = (
      <Select value={buf} placeholder={placeholder}
        onChange={(v) => { setBuf(v); onChangeLive && onChangeLive(v); if (!(validate && validate(v))) { onSave && onSave(v); flash.fire(); } }}>
        {options.map((o) => (
          <Select.Item key={o.value} value={o.value} description={o.description}>{o.label}</Select.Item>
        ))}
      </Select>
    );
  } else if (kind === "textarea") {
    control = (
      <TextArea value={buf} rows={rows} error={!!err} autoFocus={autoFocus}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => { setFocused(false); commit(buf); }} />
    );
  } else if (kind === "number") {
    control = (
      <NumberInput mono value={buf} error={!!err} autoFocus={autoFocus}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => { setFocused(false); commit(buf); }} />
    );
  } else {
    control = (
      <TextInput mono={mono || kind === "ident"} value={buf} error={!!err} autoFocus={autoFocus}
        placeholder={placeholder === "—" ? "" : placeholder}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => { setFocused(false); commit(buf); }} />
    );
  }

  return (
    <div className="ce-field">
      <div className="ce-field__row">
        <div style={{ flex: 1, minWidth: 0 }}>{control}</div>
        {flash.on && !err && <span className="ce-saved"><Icon name="check" size={10} /> saved</span>}
      </div>
      {err && <div className="ce-err">{err}</div>}
    </div>
  );
}

// -------------------------------------------------------------------------
// SuggestField — a description/definition editor with an AI "suggest"
// affordance. In view mode it renders the text. When active it shows the
// editable textarea + a Suggest button that proposes copy (Replace / Append).
// -------------------------------------------------------------------------
function SuggestField({ active, value, onSave, onChangeLive, type, entityId, title, context, rows = 3 }) {
  const [busy, setBusy] = useState(false);
  const [proposal, setProposal] = useState(null);

  const run = () => {
    setBusy(true); setProposal(null);
    CSStore.suggest({ type, id: entityId, title, context }).then((text) => {
      setBusy(false); setProposal(text);
    });
  };

  return (
    <div className="ce-field">
      <EditableField active={active} value={value} onSave={onSave} onChangeLive={onChangeLive} kind="textarea" rows={rows} placeholder="No description yet." />
      {active && (
        <div style={{ display: "flex", marginTop: 6 }}>
          <button type="button" className="ce-suggest-btn" onClick={run} disabled={busy}>
            <Icon name={busy ? "loading" : "zap"} size={11} className={busy ? "ce-spin" : ""} />
            {busy ? "Thinking…" : "Suggest"}
          </button>
        </div>
      )}
      {active && (busy || proposal) && (
        <div className="ce-suggest-panel">
          <div className="ce-suggest-panel__label"><Icon name="zap" size={11} /> AI suggestion</div>
          {busy ? (
            <><div className="ce-shimmer" style={{ width: "100%" }} /><div className="ce-shimmer" style={{ width: "92%" }} /><div className="ce-shimmer" style={{ width: "68%" }} /></>
          ) : (
            <>
              <div className="ce-suggest-panel__text">{proposal}</div>
              <div className="ce-suggest-panel__actions">
                <Button variant="primary" size="sm" onClick={() => { onSave && onSave(proposal); onChangeLive && onChangeLive(proposal); setProposal(null); }}>Replace</Button>
                <Button variant="ghost" size="sm" onClick={() => { const merged = (value ? value + " " : "") + proposal; onSave && onSave(merged); onChangeLive && onChangeLive(merged); setProposal(null); }}>Append</Button>
                <Button variant="ghost" size="sm" onClick={() => setProposal(null)}>Dismiss</Button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// -------------------------------------------------------------------------
// InlineInspector — the editable right rail. Wraps Heimdall InspectorPanel,
// adds an Edit ⇄ Done flip, a "changes save automatically" strip in edit
// mode, a create footer, and a row menu (duplicate / delete).
// -------------------------------------------------------------------------
function InlineInspector({
  mode, eyebrow, title, id, version, typeLabel,
  onEdit, onDone, onDuplicate, onDelete, onCreate, onCancel, canCreate = true,
  footerHint, children,
}) {
  const isEdit = mode === "edit";
  const isCreate = mode === "create";

  const actions = isCreate ? null : isEdit ? (
    <Button variant="primary" size="sm" onClick={onDone}><Icon name="check" size={13} /> Done</Button>
  ) : (
    <div className="ce-inspector-actions">
      <Button variant="ghost" size="sm" icon onClick={onEdit} title="Edit"><Icon name="edit" size={13} /></Button>
      <RowMenu
        placement="bottom-end"
        actions={[
          { id: "edit", label: "Edit", icon: "edit" },
          { id: "duplicate", label: "Duplicate", icon: "copy" },
          { type: "separator" },
          { id: "delete", label: "Delete…", icon: "trash", danger: true },
        ]}
        onAction={(a) => { if (a === "edit") onEdit && onEdit(); if (a === "duplicate") onDuplicate && onDuplicate(); if (a === "delete") onDelete && onDelete(); }}
      />
    </div>
  );

  return (
    <InspectorPanel
      eyebrow={isCreate ? `NEW · ${typeLabel}` : eyebrow}
      title={title || "Untitled"}
      id={id || "—"}
      version={isCreate ? undefined : version}
      actions={actions}
    >
      {isEdit && (
        <div className="ce-edit-note">
          <Icon name="edit" size={11} />
          <span>Editing — fields save automatically when you click away.</span>
        </div>
      )}
      {children}
      {isCreate && (
        <div style={{ display: "flex", gap: 8, marginTop: 18 }}>
          <Button variant="primary" onClick={onCreate} disabled={!canCreate}><Icon name="check" size={13} /> Create {typeLabel}</Button>
          <Button variant="ghost" onClick={onCancel}>Cancel</Button>
        </div>
      )}
      {footerHint && !isCreate && (
        <div style={{ padding: "11px 16px 13px", fontFamily: "var(--font-mono)", fontSize: 11, color: "rgb(var(--canvas-fg-3))" }}>{footerHint}</div>
      )}
    </InspectorPanel>
  );
}

function EmptyInspector({ icon = "layout", title, sub }) {
  return (
    <div className="ce-empty">
      <div className="ce-empty__icon"><Icon name={icon} size={22} /></div>
      <div className="ce-empty__title">{title}</div>
      <div className="ce-empty__sub">{sub}</div>
    </div>
  );
}

// -------------------------------------------------------------------------
// SelectableTable — Heimdall Table + a leading checkbox column (with a
// select-all header) and a trailing row-menu column.
// -------------------------------------------------------------------------
function SelectableTable({ columns, data, rowKey = "id", selectedId, onRowClick, selection, onToggle, onToggleAll, rowActions, onRowAction, pageSize = 9 }) {
  const allOn = data.length > 0 && data.every((r) => selection.has(r[rowKey]));
  const someOn = data.some((r) => selection.has(r[rowKey]));

  const [page, setPage] = useState(0);
  const pageCount = Math.max(1, Math.ceil(data.length / pageSize));
  // clamp page when the filtered dataset shrinks
  useEffect(() => { if (page > pageCount - 1) setPage(pageCount - 1); }, [pageCount, page]);
  const safePage = Math.min(page, pageCount - 1);
  const start = safePage * pageSize;
  const pageData = data.slice(start, start + pageSize);

  const checkboxCol = {
    key: "__sel", label: (
      <span className="csb-check" onClick={(e) => e.stopPropagation()}>
        <TriState checked={allOn} indeterminate={!allOn && someOn} onChange={() => onToggleAll(!allOn)} aria-label="Select all" />
      </span>
    ), width: "40px",
    render: (_, row) => (
      <span className="csb-check" onClick={(e) => { e.stopPropagation(); onToggle(row[rowKey]); }}>
        <TriState checked={selection.has(row[rowKey])} readOnly aria-label={"Select " + row[rowKey]} />
      </span>
    ),
  };

  const menuCol = {
    key: "__menu", label: "", width: "44px",
    render: (_, row) => (
      <span className="csb-rowmenu" onClick={(e) => e.stopPropagation()}>
        <RowMenu placement="bottom-end" actions={rowActions(row)} onAction={(a) => onRowAction(row, a)} />
      </span>
    ),
  };

  return (
    <Panel noPadding>
      <Table
        columns={[checkboxCol, ...columns, menuCol]}
        data={pageData}
        rowKey={rowKey}
        selectedRows={selectedId ? [selectedId] : []}
        onRowClick={onRowClick}
        emptyState={<div style={{ padding: 40, textAlign: "center", color: "rgb(var(--canvas-fg-3))" }}>Nothing matches these filters.</div>}
      />
      {data.length > 0 && (
        <div className="cs-table-pager">
          <span className="cs-table-pager__range">
            {start + 1}–{Math.min(start + pageSize, data.length)} of {data.length}
          </span>
          {pageCount > 1 && (
            <div className="cs-table-pager__nav">
              <Button variant="ghost" size="sm" icon disabled={safePage === 0} onClick={() => setPage(safePage - 1)} title="Previous page"><Icon name="chevronLeft" size={14} /></Button>
              <span className="cs-table-pager__page">Page {safePage + 1} of {pageCount}</span>
              <Button variant="ghost" size="sm" icon disabled={safePage >= pageCount - 1} onClick={() => setPage(safePage + 1)} title="Next page"><Icon name="chevronRight" size={14} /></Button>
            </div>
          )}
        </div>
      )}
    </Panel>
  );
}

// -------------------------------------------------------------------------
// BulkBar — floating action bar shown when rows are selected.
// -------------------------------------------------------------------------
function BulkBar({ count, label, actions, onAction, onClear }) {
  if (!count) return null;
  return (
    <div className="csb-bar" role="toolbar" aria-label="Bulk actions">
      <div className="csb-bar__count">
        <span className="csb-bar__badge">{count}</span> {CSStore.pl(label, count)} selected
      </div>
      <div className="csb-bar__sep" />
      <div className="csb-bar__actions">
        {actions.map((a) => (
          <Button key={a.id} variant={a.danger ? "danger" : "ghost"} size="sm" onClick={() => onAction(a.id)}>
            {a.icon && <Icon name={a.icon} size={13} />} {a.label}
          </Button>
        ))}
      </div>
      <div className="csb-bar__sep" />
      <Button variant="ghost" size="sm" icon onClick={onClear} title="Clear selection"><Icon name="x" size={13} /></Button>
    </div>
  );
}

// -------------------------------------------------------------------------
// CascadeDeleteDialog — danger confirm that previews everything a delete
// will cascade to (children, individuals, orphaned relationships).
// -------------------------------------------------------------------------
const TYPE_ICON = { scheme: "schema", class: "graph", individual: "data", relationship: "link", taxonomy: "schema", property: "component", configuration: "settings" };

function CascadeDeleteDialog({ open, type, target, ids, onClose, onConfirm }) {
  const data = useCS(); // re-read so cascade reflects current state
  if (!open || (!target && !(ids && ids.length))) return null;

  const targets = ids && ids.length ? ids : [target.id];
  const merged = { scheme: 0, class: 0, individual: 0, relationship: 0 };
  let items = [];
  targets.forEach((tid) => {
    const imp = CSStore.cascade(type, tid);
    merged.scheme += imp.counts.scheme; merged.class += imp.counts.class;
    merged.individual += imp.counts.individual; merged.relationship += imp.counts.relationship;
    items = items.concat(imp.items);
  });
  // de-dup display list
  const seen = new Set();
  items = items.filter((it) => (seen.has(it.id) ? false : seen.add(it.id)));
  const total = merged.scheme + merged.class + merged.individual + merged.relationship;

  const nice = CSStore.NICE[type];
  const subjectLabel = ids && ids.length > 1 ? `${ids.length} ${CSStore.pl(nice, ids.length)}` : `${nice} ${target ? (target.title || target.name || target.id) : ""}`;

  const stats = [
    ["concept scheme", merged.scheme], ["class", merged.class],
    ["individual", merged.individual], ["relationship", merged.relationship],
  ].filter(([, n]) => n > 0);

  return (
    <Modal
      isOpen={open}
      onClose={onClose}
      title={`Delete ${subjectLabel}?`}
      subtitle={total ? "This cascades through the graph. Review what will be removed." : "This action cannot be undone."}
      size={total ? "lg" : "md"}
      hintFooter={`DELETE /${CSStore.collectionOf[type]}`}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="danger" onClick={onConfirm}><Icon name="trash" size={13} /> Delete{total ? ` + ${total} dependent${total === 1 ? "" : "s"}` : ""}</Button>
        </>
      }
    >
      <div className="ce-cascade">
        {total === 0 ? (
          <FormCallout variant="warn" icon="alert">No dependents — this {nice} can be safely removed.</FormCallout>
        ) : (
          <>
            <FormCallout variant="error" icon="alert">
              Deleting {ids && ids.length > 1 ? "these" : "this"} {ids && ids.length > 1 ? CSStore.pl(nice, 2) : nice} will also remove {total} dependent node{total === 1 ? "" : "s"}. Orphaned relationships are deleted, not detached.
            </FormCallout>
            <div className="ce-cascade__summary">
              {stats.map(([k, n]) => (
                <div key={k} className="ce-cascade__stat">
                  <span className="ce-cascade__num">{n}</span>
                  <span className="ce-cascade__kind">{CSStore.pl(k, n)}</span>
                </div>
              ))}
            </div>
            <div className="ce-cascade__list">
              {items.slice(0, 60).map((it) => (
                <div key={it.id} className="ce-cascade__item">
                  <span className="ce-cascade__type">{it.type}</span>
                  <Icon name={TYPE_ICON[it.type] || "data"} size={13} />
                  <span style={{ color: "rgb(var(--canvas-fg-1))" }}>{it.label}</span>
                  <span className="ce-cascade__item-id">{it.id}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}

// -------------------------------------------------------------------------
// ParamSlider — token-styled range with a live numeric readout.
// -------------------------------------------------------------------------
function ParamSlider({ label, value, min, max, step, onChange, active, fmt = (v) => v }) {
  return (
    <div className="ce-param">
      <div className="ce-param__top">
        <span className="ce-param__label">{label}</span>
        <span className="ce-param__val">{fmt(value)}</span>
      </div>
      <input type="range" className="ce-range" min={min} max={max} step={step} value={value} disabled={!active}
        onChange={(e) => onChange(parseFloat(e.target.value))} />
    </div>
  );
}

// -------------------------------------------------------------------------
// VariableChips — parse {{var}} tokens from a template, render as chips.
// -------------------------------------------------------------------------
function VariableChips({ template, onInsert }) {
  const vars = useMemo(() => {
    const set = [];
    const re = /\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g; let m;
    while ((m = re.exec(template || "")) !== null) if (!set.includes(m[1])) set.push(m[1]);
    return set;
  }, [template]);
  if (vars.length === 0) return <span style={{ fontSize: 11.5, color: "rgb(var(--canvas-fg-3))", fontStyle: "italic" }}>No variables — add e.g. {"{{concept}}"}.</span>;
  return (
    <div className="ce-varchips">
      {vars.map((v) => (
        <span key={v} className="ce-varchip" onClick={() => onInsert && onInsert(v)} title={onInsert ? "Insert into template" : undefined}>{"{{"}{v}{"}}"}</span>
      ))}
    </div>
  );
}

Object.assign(window, {
  DOMAIN_COLOR, domainColorOf, DomainPill, useSavedFlash,
  EditableField, SuggestField, InlineInspector, EmptyInspector,
  SelectableTable, BulkBar, CascadeDeleteDialog, ParamSlider, VariableChips,
});
