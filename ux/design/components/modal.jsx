// Modal / dialog primitives + form fields. All dialogs in dialogs.jsx use these.

function Modal({ open, onClose, title, subtitle, children, size = "md", footer, headerAccessory }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className={"modal modal-" + size}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label={title}
      >
        <div className="modal-head">
          <div className="modal-head-text">
            <div className="modal-title">{title}</div>
            {subtitle && <div className="modal-sub">{subtitle}</div>}
          </div>
          {headerAccessory}
          <button className="modal-x" onClick={onClose} aria-label="Close">
            <Icon name="x" size={14} />
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  );
}

function ConfirmModal({
  open,
  onClose,
  onConfirm,
  title,
  body,
  confirmLabel = "Delete",
  danger = true,
}) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      size="sm"
      footer={
        <>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>
            Cancel
          </button>
          <button
            className={"btn btn-sm " + (danger ? "btn-danger" : "btn-primary")}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 13.5, color: "var(--canvas-fg-2)", lineHeight: 1.55 }}>{body}</div>
    </Modal>
  );
}

// ---- Form fields ----
function Field({ label, hint, error, required, children, mono }) {
  return (
    <label className="field">
      <div className="field-label">
        <span>
          {label}
          {required && <span className="req">*</span>}
        </span>
        {hint && <span className="field-hint">{hint}</span>}
      </div>
      <div className={"field-control" + (mono ? " mono" : "")}>{children}</div>
      {error && <div className="field-error">{error}</div>}
    </label>
  );
}

function TextInput({ value, onChange, placeholder, mono, autoFocus }) {
  return (
    <input
      className={"input" + (mono ? " mono" : "")}
      value={value || ""}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      autoFocus={autoFocus}
    />
  );
}

function TextArea({ value, onChange, placeholder, rows = 3 }) {
  return (
    <textarea
      className="input textarea"
      value={value || ""}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      rows={rows}
    />
  );
}

function Select({ value, onChange, options, placeholder }) {
  return (
    <select
      className="input"
      value={value || ""}
      onChange={(e) => onChange(e.target.value || null)}
    >
      {placeholder && <option value="">{placeholder}</option>}
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

function NumberInput({ value, onChange, min, max, step }) {
  return (
    <input
      type="number"
      className="input mono"
      value={value ?? ""}
      min={min}
      max={max}
      step={step}
      onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
    />
  );
}

// Tri-state segmented control for is_relevant (null / true / false)
function TriState({ value, onChange }) {
  const opts = [
    { v: null, label: "Not evaluated", cls: "gray" },
    { v: true, label: "Relevant", cls: "emerald" },
    { v: false, label: "Irrelevant", cls: "rose" },
  ];
  return (
    <div className="tri-state">
      {opts.map((o) => (
        <button
          key={String(o.v)}
          type="button"
          className={"tri-pill " + (value === o.v ? "active " + o.cls : "")}
          onClick={() => onChange(o.v)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

// Picker for entities (classes or individuals) by typeahead
function EntityPicker({
  value,
  onChange,
  kinds = ["class", "individual"],
  placeholder = "Search…",
  exclude = [],
}) {
  const { state } = window.useStore();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    const onDoc = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const items = useMemo(() => {
    const all = [];
    if (kinds.includes("class"))
      state.classes.forEach((c) =>
        all.push({ id: c.id, kind: "class", title: c.title, domain: c.domain, sub: c.id }),
      );
    if (kinds.includes("individual"))
      state.individuals.forEach((i) => {
        const c = state.classes.find((x) => x.id === i.class_ids[0]);
        all.push({
          id: i.id,
          kind: "individual",
          title: i.title,
          domain: c?.domain || "default",
          sub: i.id,
        });
      });
    const Q = q.toLowerCase();
    return all
      .filter(
        (it) =>
          !exclude.includes(it.id) &&
          (it.title.toLowerCase().includes(Q) || it.sub.toLowerCase().includes(Q)),
      )
      .slice(0, 8);
  }, [state.classes, state.individuals, q, exclude.join(","), kinds.join(",")]);

  const selected = useMemo(() => {
    if (!value) return null;
    const c = state.classes.find((x) => x.id === value);
    if (c) return { id: c.id, kind: "class", title: c.title, domain: c.domain };
    const i = state.individuals.find((x) => x.id === value);
    if (i) {
      const cc = state.classes.find((x) => x.id === i.class_ids[0]);
      return { id: i.id, kind: "individual", title: i.title, domain: cc?.domain || "default" };
    }
    return null;
  }, [value, state.classes, state.individuals]);

  return (
    <div className="entity-picker" ref={ref}>
      {selected ? (
        <div className="entity-picked">
          <span
            className="kg-node"
            data-domain={selected.domain}
            style={{ height: 26, fontSize: 12 }}
          >
            <span className="swatch"></span>
            {selected.title}
          </span>
          <span className="mono muted" style={{ fontSize: 10.5, marginLeft: 6 }}>
            {selected.kind}
          </span>
          <button
            type="button"
            className="entity-clear"
            onClick={() => {
              onChange(null);
              setQ("");
              setOpen(true);
            }}
            aria-label="Clear"
          >
            <Icon name="x" size={11} />
          </button>
        </div>
      ) : (
        <input
          className="input"
          value={q}
          placeholder={placeholder}
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
        />
      )}
      {open && !selected && items.length > 0 && (
        <div className="entity-results">
          {items.map((it) => (
            <button
              key={it.id}
              type="button"
              className="entity-result"
              onClick={() => {
                onChange(it.id);
                setOpen(false);
                setQ("");
              }}
            >
              <span
                className="kg-node"
                data-domain={it.domain}
                style={{ height: 22, fontSize: 11.5 }}
              >
                <span className="swatch"></span>
                {it.title}
              </span>
              <span className="mono muted" style={{ fontSize: 10.5, marginLeft: "auto" }}>
                {it.kind} · {it.id}
              </span>
            </button>
          ))}
        </div>
      )}
      {open && !selected && items.length === 0 && q && (
        <div className="entity-results">
          <div className="entity-empty">No matches</div>
        </div>
      )}
    </div>
  );
}

// Editable list of {key, value, datatype} rows
function KeyValueListEditor({ rows, onChange, datatypes }) {
  const update = (i, patch) => {
    const next = rows.map((r, k) => (k === i ? { ...r, ...patch } : r));
    onChange(next);
  };
  const remove = (i) => onChange(rows.filter((_, k) => k !== i));
  const add = () =>
    onChange([...rows, { key: "", value: "", datatype: datatypes ? datatypes[0] : "" }]);
  return (
    <div className="kvle">
      {rows.length === 0 && <div className="kvle-empty">No entries yet.</div>}
      {rows.map((r, i) => (
        <div key={i} className="kvle-row">
          <input
            className="input mono"
            placeholder="key"
            value={r.key}
            onChange={(e) => update(i, { key: e.target.value })}
          />
          <input
            className="input"
            placeholder="value"
            value={r.value}
            onChange={(e) => update(i, { value: e.target.value })}
          />
          {datatypes && (
            <select
              className="input mono"
              value={r.datatype || ""}
              onChange={(e) => update(i, { datatype: e.target.value })}
            >
              {datatypes.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          )}
          <button type="button" className="btn btn-ghost btn-sm btn-icon" onClick={() => remove(i)}>
            <Icon name="x" size={12} />
          </button>
        </div>
      ))}
      <button type="button" className="btn btn-ghost btn-sm" onClick={add}>
        <Icon name="plus" size={12} /> Add row
      </button>
    </div>
  );
}

// External references list editor — { source, identifier, url? }
function RefListEditor({ rows, onChange }) {
  const update = (i, patch) => {
    onChange(rows.map((r, k) => (k === i ? { ...r, ...patch } : r)));
  };
  const remove = (i) => onChange(rows.filter((_, k) => k !== i));
  const add = () => onChange([...rows, { source: "Wikidata", identifier: "", url: "" }]);
  const sources = ["Wikidata", "DBpedia", "ConceptNet", "Reactome", "UniProt", "NCBI", "Other"];
  return (
    <div className="kvle">
      {rows.length === 0 && <div className="kvle-empty">No external references yet.</div>}
      {rows.map((r, i) => (
        <div key={i} className="kvle-row reflist">
          <select
            className="input mono"
            value={r.source || "Other"}
            onChange={(e) => update(i, { source: e.target.value })}
          >
            {sources.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <input
            className="input mono"
            placeholder="identifier (e.g. Q7868)"
            value={r.identifier || ""}
            onChange={(e) => update(i, { identifier: e.target.value })}
          />
          <input
            className="input"
            placeholder="https://…"
            value={r.url || ""}
            onChange={(e) => update(i, { url: e.target.value })}
          />
          <button type="button" className="btn btn-ghost btn-sm btn-icon" onClick={() => remove(i)}>
            <Icon name="x" size={12} />
          </button>
        </div>
      ))}
      <button type="button" className="btn btn-ghost btn-sm" onClick={add}>
        <Icon name="plus" size={12} /> Add reference
      </button>
    </div>
  );
}

function LexicalListEditor({ rows, onChange }) {
  const update = (i, patch) => {
    onChange(rows.map((r, k) => (k === i ? { ...r, ...patch } : r)));
  };
  const remove = (i) => onChange(rows.filter((_, k) => k !== i));
  const add = () => onChange([...rows, { label: "", language: "en", sense_type: "preferred" }]);
  const senseTypes = ["preferred", "alias", "abbreviation", "translation", "colloquial", "symbol"];
  return (
    <div className="kvle">
      {rows.length === 0 && <div className="kvle-empty">No lexical senses yet.</div>}
      {rows.map((r, i) => (
        <div key={i} className="kvle-row lexlist">
          <input
            className="input"
            placeholder="label"
            value={r.label || ""}
            onChange={(e) => update(i, { label: e.target.value })}
          />
          <input
            className="input mono"
            placeholder="lang"
            maxLength={5}
            value={r.language || ""}
            onChange={(e) => update(i, { language: e.target.value })}
          />
          <select
            className="input mono"
            value={r.sense_type || "preferred"}
            onChange={(e) => update(i, { sense_type: e.target.value })}
          >
            {senseTypes.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <button type="button" className="btn btn-ghost btn-sm btn-icon" onClick={() => remove(i)}>
            <Icon name="x" size={12} />
          </button>
        </div>
      ))}
      <button type="button" className="btn btn-ghost btn-sm" onClick={add}>
        <Icon name="plus" size={12} /> Add sense
      </button>
    </div>
  );
}

// Reorderable chips for ordered class_ids on Individuals
function OrderedClassList({ classIds, onChange }) {
  const { state } = window.useStore();
  const [picking, setPicking] = useState(false);
  const [pickValue, setPickValue] = useState(null);

  const move = (i, dir) => {
    const j = i + dir;
    if (j < 0 || j >= classIds.length) return;
    const next = [...classIds];
    [next[i], next[j]] = [next[j], next[i]];
    onChange(next);
  };
  const remove = (i) => {
    if (classIds.length <= 1) return;
    onChange(classIds.filter((_, k) => k !== i));
  };
  const add = () => {
    if (pickValue && !classIds.includes(pickValue)) onChange([...classIds, pickValue]);
    setPickValue(null);
    setPicking(false);
  };

  return (
    <div className="ordered-cls">
      {classIds.map((id, i) => {
        const c = state.classes.find((x) => x.id === id);
        if (!c) return null;
        return (
          <div key={id} className="ord-row">
            <span className="ord-rank mono">{i + 1}</span>
            <span className="kg-node" data-domain={c.domain} style={{ height: 24, fontSize: 12 }}>
              <span className="swatch"></span>
              {c.title}
            </span>
            {i === 0 && (
              <span
                className="chip cyan"
                title="Wins data-property conflicts"
                style={{ marginLeft: 6 }}
              >
                primary
              </span>
            )}
            <span style={{ flex: 1 }}></span>
            <button
              type="button"
              className="btn btn-ghost btn-sm btn-icon"
              disabled={i === 0}
              onClick={() => move(i, -1)}
              aria-label="Move up"
            >
              <Icon name="chevDown" size={11} className="rotate-180" />
            </button>
            <button
              type="button"
              className="btn btn-ghost btn-sm btn-icon"
              disabled={i === classIds.length - 1}
              onClick={() => move(i, 1)}
              aria-label="Move down"
            >
              <Icon name="chevDown" size={11} />
            </button>
            <button
              type="button"
              className="btn btn-ghost btn-sm btn-icon"
              disabled={classIds.length <= 1}
              onClick={() => remove(i)}
              aria-label="Remove"
            >
              <Icon name="x" size={12} />
            </button>
          </div>
        );
      })}
      {picking ? (
        <div className="ord-picker">
          <EntityPicker
            value={pickValue}
            onChange={setPickValue}
            kinds={["class"]}
            exclude={classIds}
            placeholder="Add a class…"
          />
          <button
            type="button"
            className="btn btn-sm btn-primary"
            disabled={!pickValue}
            onClick={add}
          >
            Add
          </button>
          <button
            type="button"
            className="btn btn-sm btn-ghost"
            onClick={() => {
              setPicking(false);
              setPickValue(null);
            }}
          >
            Cancel
          </button>
        </div>
      ) : (
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setPicking(true)}>
          <Icon name="plus" size={12} /> Add another class
        </button>
      )}
      <div className="ord-help">
        First parent wins on conflicting data properties · drag rank to reorder.
      </div>
    </div>
  );
}

// ---- Toast viewport ----
function ToastViewport() {
  const { toasts, dismissToast } = window.useToast();
  return (
    <div className="toast-viewport">
      {toasts.map((t) => (
        <div key={t.id} className={"toast toast-" + t.kind}>
          <span className="toast-mark">
            {t.kind === "success" ? <Icon name="check" size={14} /> : <Icon name="x" size={14} />}
          </span>
          <div className="toast-body">
            <div className="toast-title">{t.title}</div>
            {t.body && <div className="toast-sub">{t.body}</div>}
          </div>
          <button className="toast-x" onClick={() => dismissToast(t.id)}>
            <Icon name="x" size={11} />
          </button>
        </div>
      ))}
    </div>
  );
}

window.Modal = Modal;
window.ConfirmModal = ConfirmModal;
window.Field = Field;
window.TextInput = TextInput;
window.TextArea = TextArea;
window.Select = Select;
window.NumberInput = NumberInput;
window.TriState = TriState;
window.EntityPicker = EntityPicker;
window.KeyValueListEditor = KeyValueListEditor;
window.RefListEditor = RefListEditor;
window.LexicalListEditor = LexicalListEditor;
window.OrderedClassList = OrderedClassList;
window.ToastViewport = ToastViewport;
