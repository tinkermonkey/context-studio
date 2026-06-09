// =========================================================================
// Context Studio — CreateDrawer
// A focused, roomy "new element" surface that replaces the cramped inline-rail
// create mode. One component serves every EntitySurface type. Design goals:
//   • Title-first — you name the thing; the machine identifier auto-slugs from
//     it (editable, re-linkable). No more "invent a snake_case id first".
//   • Deferred validation — fresh fields never show errors; requirements are
//     hints until you touch a field or press Create.
//   • A required-fields progress meter so you always know what's left.
//   • Sticky footer: the primary CTA is ALWAYS visible (⌘↵), Esc cancels,
//     and an opt-in "Create another" keeps momentum.
//   • AI-assisted descriptions (reuses SuggestField).
// Commit still goes through CSStore.create, which logs activity + toasts.
// =========================================================================

// ---- per-type presentation + identifier rules -------------------------
const CD_FORMS = {
  taxonomy:     { icon: "schema",    noun: "taxonomy",        idKey: "id",         idPrefix: "tax_", titleKey: "title", blurb: "A top-level domain that groups related concept schemes." },
  scheme:       { icon: "schema",    noun: "concept scheme",  idKey: "id",         idPrefix: "sch_", titleKey: "title", blurb: "A focused vocabulary inside a taxonomy. Classes live in exactly one scheme." },
  class:        { icon: "graph",     noun: "class",           idKey: "id",         idPrefix: "cls_", titleKey: "title", blurb: "A structural node of the graph — the type that individuals instantiate." },
  property:     { icon: "component", noun: "property",        idKey: "identifier", idPrefix: "",     titleKey: "title", blurb: "A named predicate that relationships use to connect nodes." },
  individual:   { icon: "data",      noun: "individual",      idKey: "id",         idPrefix: "ind_", titleKey: "title", blurb: "A concrete instance that belongs to one or more classes." },
  relationship: { icon: "link",      noun: "relationship",    idKey: null,         idPrefix: "",     titleKey: null,    blurb: "A typed triple connecting a source node to a target node." },
};

// turn a human title into a clean snake_case stem (no prefix)
function cdSlug(s) {
  return (s || "").toLowerCase().trim()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/_{2,}/g, "_")
    .replace(/^_+|_+$/g, "");
}

// shape the draft into the payload CSStore.create expects (per type)
function cdFinalize(type, d) {
  if (type === "taxonomy")     return { ...d, classes: 0, individuals: 0 };
  if (type === "scheme")       return { ...d, classes: 0 };
  if (type === "class")        return { ...d, individuals: 0 };
  if (type === "property")     return { ...d, id: "prop_" + d.identifier, origin: d.origin || "manual" };
  if (type === "individual")   return { ...d, confidence: parseFloat(d.confidence) || 1 };
  if (type === "relationship") return { ...d, id: "rel_" + Math.random().toString(36).slice(2, 6), created: "now", confidence: parseFloat(d.confidence) || 1 };
  return d;
}

// =========================================================================
function CreateDrawer({ type, initialDraft, onCreated, onClose, inline }) {
  const data = useCS();
  const form = CD_FORMS[type];
  const base = useRef(initialDraft || newDraft(type)).current;

  const [draft, setDraft] = useState(() => ({ ...base }));
  const [touched, setTouched] = useState(() => new Set());
  const [attempted, setAttempted] = useState(false);
  // id starts "dirty" (manually-owned) only if it arrived pre-filled (duplicate)
  const [idDirty, setIdDirty] = useState(() => !!(form.idKey && base[form.idKey]));
  const [createAnother, setCreateAnother] = useState(false);
  const [justCreated, setJustCreated] = useState(null);
  const titleRef = useRef(null);

  const setField = useCallback((k, v) => setDraft((d) => ({ ...d, [k]: v })), []);
  const markTouched = useCallback((k) => setTouched((s) => (s.has(k) ? s : new Set(s).add(k))), []);
  const showErr = (k) => attempted || touched.has(k);

  // ---- title → identifier auto-slug ------------------------------------
  const onTitle = (v) => {
    setField(form.titleKey, v);
    if (form.idKey && !idDirty) setField(form.idKey, form.idPrefix + cdSlug(v));
  };
  const onIdEdit = (v) => { setIdDirty(true); setField(form.idKey, v); };
  const relinkId = () => {
    setIdDirty(false);
    setField(form.idKey, form.idPrefix + cdSlug(draft[form.titleKey] || ""));
  };

  // ---- requirements / progress -----------------------------------------
  const idErr = form.idKey ? CSStore.validateIdent(type === "property" ? "property" : type, draft[form.idKey] || "") : null;
  const reqs = useMemo(() => {
    const titleOk = form.titleKey ? !!(draft[form.titleKey] || "").trim() : true;
    const list = [];
    if (form.titleKey) list.push({ key: form.titleKey, label: "Title", ok: titleOk });
    if (form.idKey) list.push({ key: form.idKey, label: type === "property" ? "Identifier" : "Identifier", ok: !idErr });
    if (type === "scheme") list.push({ key: "taxonomy_id", label: "Taxonomy", ok: !!draft.taxonomy_id });
    if (type === "class")  list.push({ key: "concept_scheme_id", label: "Scheme", ok: !!draft.concept_scheme_id });
    if (type === "individual") list.push({ key: "class_ids", label: "Class", ok: !!(draft.class_ids || []).length });
    if (type === "relationship") {
      list.push({ key: "source_id", label: "Source", ok: !!draft.source_id });
      list.push({ key: "property_definition_id", label: "Predicate", ok: !!draft.property_definition_id });
      list.push({ key: "target_id", label: "Target", ok: !!draft.target_id });
    }
    return list;
  }, [draft, idErr, type, form]);

  const doneCount = reqs.filter((r) => r.ok).length;
  const canCreate = doneCount === reqs.length;

  // ---- commit -----------------------------------------------------------
  const submit = useCallback(() => {
    if (!canCreate) { setAttempted(true); return; }
    const row = CSStore.create(type, cdFinalize(type, draft)); // store handles toast + activity
    if (createAnother) {
      setDraft({ ...base, ...(type === "class" || type === "scheme" || type === "relationship" ? carryContext(type, base) : {}) });
      setTouched(new Set()); setAttempted(false);
      setIdDirty(!!(form.idKey && base[form.idKey]));
      setJustCreated(row.title || row.id);
      requestAnimationFrame(() => titleRef.current && titleRef.current.focus());
    } else {
      onCreated(row.id);
    }
  }, [canCreate, type, draft, createAnother, base, form, onCreated]);

  // keep keyboard handler pointed at the latest submit/close
  const submitRef = useRef(submit); submitRef.current = submit;
  const closeRef = useRef(onClose); closeRef.current = onClose;
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") { e.preventDefault(); closeRef.current(); }
      else if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { e.preventDefault(); submitRef.current(); }
    };
    document.addEventListener("keydown", onKey, true);
    requestAnimationFrame(() => titleRef.current && titleRef.current.focus());
    return () => document.removeEventListener("keydown", onKey, true);
  }, []);

  // clear the "created — add another" banner after a beat
  useEffect(() => {
    if (!justCreated) return;
    const t = setTimeout(() => setJustCreated(null), 2600);
    return () => clearTimeout(t);
  }, [justCreated]);

  const pct = reqs.length ? Math.round((doneCount / reqs.length) * 100) : 100;

  const ctx = { type, data, draft, setField, markTouched, showErr, idErr, onTitle, onIdEdit, relinkId, idDirty, titleRef, form };

  const panel = (
      <div className={"cd-panel" + (inline ? " cd-panel--inline" : "")} role="dialog" aria-modal={inline ? undefined : "true"} aria-label={`Create ${form.noun}`}>
        {/* header */}
        <div className="cd-head">
          <div className={`cd-head__icon cd-head__icon--${type}`}><Icon name={form.icon} size={20} /></div>
          <div className="cd-head__text">
            <div className="cd-head__eyebrow">NEW · {type}</div>
            <div className="cd-head__title">New {form.noun}</div>
            <div className="cd-head__blurb">{form.blurb}</div>
          </div>
          <button type="button" className="cd-head__close" onClick={onClose} aria-label="Close"><Icon name="x" size={15} /></button>
        </div>

        {/* progress */}
        <div className="cd-progress" aria-hidden="true">
          <div className="cd-progress__track"><div className={"cd-progress__bar" + (canCreate ? " is-complete" : "")} style={{ width: pct + "%" }} /></div>
          <div className="cd-progress__chips">
            {reqs.map((r) => (
              <span key={r.key} className={"cd-req" + (r.ok ? " is-ok" : "")}>
                <span className="cd-req__dot">{r.ok ? <Icon name="check" size={9} /> : null}</span>{r.label}
              </span>
            ))}
            <span className="cd-progress__count">{canCreate ? "ready" : `${doneCount} / ${reqs.length}`}</span>
          </div>
        </div>

        {/* body */}
        <div className="cd-body">
          {justCreated && (
            <div className="cd-created" role="status">
              <Icon name="check" size={13} /> Created <strong>{justCreated}</strong> — add another below.
            </div>
          )}
          <CreateBody {...ctx} />
        </div>

        {/* sticky footer */}
        <div className="cd-foot">
          <label className="cd-another">
            <input type="checkbox" checked={createAnother} onChange={(e) => setCreateAnother(e.target.checked)} />
            <span>Create another</span>
          </label>
          <div className="cd-foot__actions">
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
            <button type="button" className={"cd-create" + (canCreate ? "" : " is-disabled")} onClick={submit} aria-disabled={!canCreate}>
              <Icon name="check" size={14} />
              <span>Create {form.noun}</span>
              <kbd className="cd-kbd">⌘↵</kbd>
            </button>
          </div>
        </div>
      </div>
  );
  if (inline) return panel;
  return (
    <div className="cd-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      {panel}
    </div>
  );
}

// preserve contextual parent links when resetting for "create another"
function carryContext(type, base) {
  if (type === "class")  return { concept_scheme_id: base.concept_scheme_id, taxonomy_id: base.taxonomy_id, domain: base.domain, parent_class_id: base.parent_class_id };
  if (type === "scheme") return { taxonomy_id: base.taxonomy_id, domain: base.domain };
  if (type === "relationship") return { source_id: base.source_id };
  return {};
}

// =========================================================================
// CreateBody — type-specific fields, all using the stacked <Field> layout.
// =========================================================================
function CreateBody(ctx) {
  const { type } = ctx;
  if (type === "taxonomy")     return <TaxonomyBody {...ctx} />;
  if (type === "scheme")       return <SchemeBody {...ctx} />;
  if (type === "class")        return <ClassBody {...ctx} />;
  if (type === "property")     return <PropertyBody {...ctx} />;
  if (type === "individual")   return <IndividualBody {...ctx} />;
  if (type === "relationship") return <RelationshipBody {...ctx} />;
  return null;
}

// shared bits ------------------------------------------------------------
const cdDomainOpts = [{ value: "life", label: "life" }, { value: "climate", label: "climate" }, { value: "software", label: "software" }];

function TitleField({ ctx, label = "Title", placeholder = "Give it a clear, human name", hint }) {
  const { draft, form, onTitle, markTouched, showErr, titleRef } = ctx;
  const empty = !(draft[form.titleKey] || "").trim();
  const err = showErr(form.titleKey) && empty ? "A name is required." : null;
  return (
    <Field label={label} required hint={hint} error={err}>
      <TextInput ref={titleRef} value={draft[form.titleKey] || ""} placeholder={placeholder} error={!!err}
        onChange={(e) => onTitle(e.target.value)} onBlur={() => markTouched(form.titleKey)} />
    </Field>
  );
}

function IdField({ ctx, hintExample }) {
  const { draft, form, onIdEdit, relinkId, idDirty, idErr, showErr, markTouched } = ctx;
  const val = draft[form.idKey] || "";
  const err = showErr(form.idKey) && idErr ? idErr : null;
  return (
    <Field
      label="Identifier"
      hint={<span className="cd-id-hint">{idDirty ? "custom" : "auto from title"}</span>}
      error={err}
    >
      <div className="cd-id">
        <TextInput mono value={val} placeholder={hintExample} error={!!err}
          onChange={(e) => onIdEdit(e.target.value)} onBlur={() => markTouched(form.idKey)} />
        {idDirty && (
          <button type="button" className="cd-relink" onClick={relinkId} title="Re-link to title">
            <Icon name="reload" size={12} /> auto
          </button>
        )}
      </div>
    </Field>
  );
}

function DescField({ ctx, rows = 3 }) {
  const { draft, setField } = ctx;
  return (
    <Field label="Description" hint={<span className="cd-id-hint">optional</span>}>
      <SuggestField active value={draft.description} type={ctx.type} title={draft[ctx.form.titleKey]} rows={rows}
        onSave={(v) => setField("description", v)} onChangeLive={(v) => setField("description", v)} />
    </Field>
  );
}

// ---- Taxonomy ----------------------------------------------------------
function TaxonomyBody(ctx) {
  const { draft, setField } = ctx;
  return (
    <div className="cd-form">
      <TitleField ctx={ctx} placeholder="e.g. Life Sciences" />
      <IdField ctx={ctx} hintExample="tax_life_sciences" />
      <Field label="Domain">
        <SegmentedControl value={draft.domain} onChange={(v) => setField("domain", v)} options={cdDomainOpts} />
      </Field>
      <DescField ctx={ctx} />
    </div>
  );
}

// ---- Concept scheme ----------------------------------------------------
function SchemeBody(ctx) {
  const { data, draft, setField, markTouched, showErr } = ctx;
  const taxOpts = data.taxonomies.map((t) => ({ value: t.id, label: t.title, description: t.id }));
  const tax = data.taxonomies.find((t) => t.id === draft.taxonomy_id);
  const onTax = (v) => { const t = data.taxonomies.find((x) => x.id === v); setField("taxonomy_id", v); if (t) setField("domain", t.domain); markTouched("taxonomy_id"); };
  const taxErr = showErr("taxonomy_id") && !draft.taxonomy_id ? "Pick a taxonomy." : null;
  return (
    <div className="cd-form">
      <TitleField ctx={ctx} placeholder="e.g. Cellular Biology" />
      <IdField ctx={ctx} hintExample="sch_cellular_biology" />
      <Field label="Taxonomy" required error={taxErr} hint={<span className="cd-id-hint">sets the domain</span>}>
        <Select value={draft.taxonomy_id} placeholder="Select taxonomy…" onChange={onTax}>
          {taxOpts.map((o) => <Select.Item key={o.value} value={o.value} description={o.description}>{o.label}</Select.Item>)}
        </Select>
      </Field>
      {tax && <div className="cd-derived"><DomainPill domain={tax.domain} label={`domain: ${tax.domain}`} /><span className="cd-derived__note">inherited from {tax.title}</span></div>}
      <DescField ctx={ctx} />
    </div>
  );
}

// ---- Class -------------------------------------------------------------
function ClassBody(ctx) {
  const { data, draft, setField, markTouched, showErr } = ctx;
  const schemeOpts = data.concept_schemes.map((s) => ({ value: s.id, label: s.title, description: s.id }));
  const sch = data.concept_schemes.find((s) => s.id === draft.concept_scheme_id);
  const tax = data.taxonomies.find((t) => t.id === (sch?.taxonomy_id || draft.taxonomy_id));
  const parentOpts = [{ value: "", label: "— root (no parent) —" }].concat(
    data.classes.filter((x) => x.concept_scheme_id === draft.concept_scheme_id)
      .map((x) => ({ value: x.id, label: x.title, description: x.id })));
  const onScheme = (v) => { const s = data.concept_schemes.find((x) => x.id === v); setDraftScheme(setField, v, s); markTouched("concept_scheme_id"); };
  const schErr = showErr("concept_scheme_id") && !draft.concept_scheme_id ? "Pick a concept scheme." : null;
  const parent = draft.parent_class_id ? data.classes.find((x) => x.id === draft.parent_class_id) : null;
  return (
    <div className="cd-form">
      <TitleField ctx={ctx} placeholder="e.g. Ribosome" />
      <IdField ctx={ctx} hintExample="cls_ribosome" />
      <DescField ctx={ctx} />
      <Field label="Concept scheme" required error={schErr}>
        <Select value={draft.concept_scheme_id} placeholder="Select scheme…" onChange={onScheme}>
          {schemeOpts.map((o) => <Select.Item key={o.value} value={o.value} description={o.description}>{o.label}</Select.Item>)}
        </Select>
      </Field>
      <Field label="Parent class" hint={<span className="cd-id-hint">optional</span>}>
        <Select value={draft.parent_class_id || ""} placeholder="— root —" onChange={(v) => setField("parent_class_id", v)} disabled={!draft.concept_scheme_id}>
          {parentOpts.map((o) => <Select.Item key={o.value || "root"} value={o.value} description={o.description}>{o.label}</Select.Item>)}
        </Select>
      </Field>
      {(sch || tax || parent) && (
        <div className="cd-derived">
          {tax && <DomainPill domain={tax.domain} label={`domain: ${tax.domain}`} />}
          <span className="cd-derived__note">{[tax && `taxonomy ${tax.title}`, parent && `under ${parent.title}`].filter(Boolean).join(" · ") || "root class"}</span>
        </div>
      )}
    </div>
  );
}
function setDraftScheme(setField, v, s) { setField("concept_scheme_id", v); setField("taxonomy_id", s?.taxonomy_id); setField("domain", s?.domain); setField("parent_class_id", ""); }

// ---- Property ----------------------------------------------------------
function PropertyBody(ctx) {
  const { draft, setField } = ctx;
  const relVal = draft.is_relevant === true ? "true" : draft.is_relevant === false ? "false" : "null";
  const setRel = (v) => setField("is_relevant", v === "true" ? true : v === "false" ? false : null);
  return (
    <div className="cd-form">
      <TitleField ctx={ctx} label="Title" placeholder="e.g. Has Part" hint={<span className="cd-id-hint">human label</span>} />
      <IdField ctx={ctx} hintExample="has_part" />
      <DescField ctx={ctx} rows={2} />
      <Field label="Relevance" hint={<span className="cd-id-hint">drives the inferred graph</span>}>
        <SegmentedControl value={relVal} onChange={setRel}
          options={[{ value: "true", label: "relevant" }, { value: "null", label: "unevaluated" }, { value: "false", label: "irrelevant" }]} />
      </Field>
    </div>
  );
}

// ---- Individual --------------------------------------------------------
function IndividualBody(ctx) {
  const { data, draft, setField, markTouched, showErr } = ctx;
  const clsErr = showErr("class_ids") && !(draft.class_ids || []).length ? "Assign at least one class." : null;
  return (
    <div className="cd-form">
      <TitleField ctx={ctx} placeholder="e.g. BRCA1" />
      <IdField ctx={ctx} hintExample="ind_brca1" />
      <DescField ctx={ctx} rows={2} />
      <Field label="Classes" required error={clsErr} hint={<span className="cd-id-hint">one or more</span>}>
        <Select multiple values={draft.class_ids || []} placeholder="Assign classes…"
          onValuesChange={(vals) => { setField("class_ids", vals); markTouched("class_ids"); }}>
          {data.classes.map((cl) => <Select.CheckboxItem key={cl.id} value={cl.id} description={cl.id}>{cl.title}</Select.CheckboxItem>)}
        </Select>
      </Field>
      <div className="cd-row2">
        <Field label="Source"><TextInput mono value={draft.source || ""} placeholder="Manual" onChange={(e) => setField("source", e.target.value)} /></Field>
        <Field label="Confidence">
          <ParamSlider active label="" value={parseFloat(draft.confidence) || 0} min={0} max={1} step={0.01} fmt={(v) => v.toFixed(2)} onChange={(v) => setField("confidence", v)} />
        </Field>
      </div>
    </div>
  );
}

// ---- Relationship (triple) --------------------------------------------
function RelationshipBody(ctx) {
  const { data, draft, setField } = ctx;
  const nodeById = (id) => data.classes.find((x) => x.id === id) || data.individuals.find((x) => x.id === id);
  const toResult = (n) => n ? { id: n.id, label: n.title, domain: n.domain, domainColor: domainColorOf(n.domain) } : undefined;
  const [srcQ, setSrcQ] = useState(""); const [tgtQ, setTgtQ] = useState("");
  const search = (q) => { const Q = q.toLowerCase(); return [...data.classes, ...data.individuals].filter((n) => n.title.toLowerCase().includes(Q) || n.id.toLowerCase().includes(Q)).slice(0, 8).map(toResult); };
  const predicates = data.property_definitions.map((p) => p.identifier);
  const predById = (id) => data.property_definitions.find((p) => p.id === id);
  const predByIdent = (ident) => data.property_definitions.find((p) => p.identifier === ident);
  const builderValue = {
    source: toResult(nodeById(draft.source_id)),
    target: toResult(nodeById(draft.target_id)),
    predicate: predById(draft.property_definition_id)?.identifier || "",
  };
  const onBuilder = (v) => {
    setField("source_id", v.source?.id || "");
    setField("target_id", v.target?.id || "");
    if (v.predicate) { const p = predByIdent(v.predicate); if (p) setField("property_definition_id", p.id); }
  };
  return (
    <div className="cd-form">
      <div className="cd-section-label">Triple</div>
      <RelationshipBuilder
        value={builderValue} onChange={onBuilder}
        sourceQuery={srcQ} onSourceQueryChange={setSrcQ} sourceResults={search(srcQ)}
        targetQuery={tgtQ} onTargetQueryChange={setTgtQ} targetResults={search(tgtQ)}
        predicates={predicates}
        onSourceClear={() => onBuilder({ ...builderValue, source: undefined })}
        onTargetClear={() => onBuilder({ ...builderValue, target: undefined })}
      />
      <div className="cd-row2">
        <Field label="Source"><TextInput mono value={draft.source || ""} placeholder="manual" onChange={(e) => setField("source", e.target.value)} /></Field>
        <Field label="Confidence">
          <ParamSlider active label="" value={parseFloat(draft.confidence) || 0} min={0} max={1} step={0.01} fmt={(v) => v.toFixed(2)} onChange={(v) => setField("confidence", v)} />
        </Field>
      </div>
    </div>
  );
}

// ---- Empty state (first-create) ----------------------------------------
function CreateEmptyState({ icon = "layout", noun, onCreate }) {
  return (
    <div className="cd-empty">
      <div className="cd-empty__icon"><Icon name={icon} size={26} /></div>
      <div className="cd-empty__title">No {CSStore.pl(noun, 2)} yet</div>
      <div className="cd-empty__sub">Create the first {noun} to start building out this part of the graph.</div>
      <button type="button" className="cd-empty__cta" onClick={onCreate}><Icon name="plus" size={14} /> Create {noun}</button>
    </div>
  );
}

Object.assign(window, { CreateDrawer, CreateEmptyState, CD_FORMS, cdSlug });
