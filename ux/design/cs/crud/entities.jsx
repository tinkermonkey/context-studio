// =========================================================================
// Context Studio — Entity inspectors
// One <EntityInspector type=…> that renders view / inline-edit / create for
// every schema & data node type, composed on InlineInspector + EditableField
// + SuggestField + RelationshipBuilder. Edits save on blur (optimistic);
// create commits explicitly. Identity rows reuse KVGrid for visual parity
// with the read-only inspector that already shipped.
// =========================================================================

// ---- draft factories (also used for "duplicate") ----------------------
function newDraft(type, ctx = {}) {
  if (type === "taxonomy") return { id: "", title: "", domain: "life", description: "" };
  if (type === "scheme") return { id: "", title: "", taxonomy_id: ctx.taxonomy_id || "", domain: "life", description: "", classes: 0 };
  if (type === "class") return { id: "", title: "", concept_scheme_id: ctx.concept_scheme_id || "", taxonomy_id: ctx.taxonomy_id || "", parent_class_id: ctx.parent_class_id || "", domain: ctx.domain || "life", description: "", individuals: 0 };
  if (type === "property") return { id: "", identifier: "", title: "", description: "", is_relevant: null, origin: "manual", used_by: 0 };
  if (type === "individual") return { id: "", title: "", description: "", class_ids: ctx.class_ids || [], source: "Manual", confidence: 1.0 };
  if (type === "relationship") return { id: "", source_id: ctx.source_id || "", target_id: "", property_definition_id: "", source: "manual", confidence: 1.0 };
  return {};
}

const REL_PREDICATE_DEFAULT = "prop_related_to";

// ---- helpers -----------------------------------------------------------
const domSelectOptions = [
  { value: "life", label: "life" }, { value: "climate", label: "climate" }, { value: "software", label: "software" },
];

function kvRow(key, value) { return { key, value }; }

// =========================================================================
function EntityInspector(props) {
  const { type } = props;
  if (type === "taxonomy") return <TaxonomyInspector {...props} />;
  if (type === "scheme") return <SchemeInspector {...props} />;
  if (type === "class") return <ClassInspector {...props} />;
  if (type === "property") return <PropertyInspector {...props} />;
  if (type === "individual") return <IndividualInspector {...props} />;
  if (type === "relationship") return <RelationshipInspector {...props} />;
  return null;
}

// shared controller behaviour for the "scalar" inspectors
function useEntityEdit(type, entity, mode, initialDraft) {
  const isCreate = mode === "create";
  const isEdit = mode === "edit";
  const active = isCreate || isEdit;
  const [draft, setDraft] = useState(() => initialDraft || newDraft(type));
  const cur = isCreate ? draft : (entity || {});
  const setField = useCallback((k, v) => setDraft((d) => ({ ...d, [k]: v })), []);
  const saveField = (k) => (isCreate
    ? (v) => setField(k, v)
    : (v) => CSStore.update(type, entity.id, { [k]: v }, { field: k }));
  const liveField = (k) => (isCreate ? (v) => setField(k, v) : undefined);
  return { isCreate, isEdit, active, draft, setDraft, cur, setField, saveField, liveField };
}

// ---- Taxonomy ----------------------------------------------------------
function TaxonomyInspector({ entity, mode, initialDraft, onEnterEdit, onDone, onCreated, onCancel, onDelete, onDuplicate }) {
  const data = useCS();
  const c = useEntityEdit("taxonomy", entity, mode, initialDraft);
  const identType = "taxonomy";
  const idVal = c.isCreate ? c.draft.id : entity.id;
  const validId = c.isCreate && CSStore.validateIdent(identType, c.draft.id) === null && c.draft.title.trim();

  const schemes = entity ? data.concept_schemes.filter((s) => s.taxonomy_id === entity.id) : [];
  const create = () => { const r = CSStore.create("taxonomy", { ...c.draft, classes: 0, individuals: 0 }); onCreated(r.id); };

  return (
    <InlineInspector mode={mode} typeLabel="taxonomy" eyebrow={`TAXONOMY · ${c.cur.domain || ""}`}
      title={c.cur.title} id={idVal || "—"} version={entity?.version}
      onEdit={onEnterEdit} onDone={onDone} onCreate={create} onCancel={onCancel} canCreate={validId}
      onDelete={onDelete} onDuplicate={onDuplicate} footerHint={`PUT /taxonomies/${idVal || "…"}`}>
      <InspectorPanel.Section title="Identity">
        <KVGrid keyWidth={120} rows={[
          kvRow("IDENTIFIER", c.isCreate
            ? <EditableField active value={c.draft.id} kind="ident" placeholder="tax_my_domain" onChangeLive={(v) => c.setField("id", v)} onSave={(v) => c.setField("id", v)} validate={(v) => CSStore.validateIdent(identType, v)} autoFocus />
            : <span style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>{entity.id}</span>),
          kvRow("TITLE", <EditableField active={c.active} value={c.cur.title} onSave={c.saveField("title")} onChangeLive={c.liveField("title")} placeholder="Display title" />),
          kvRow("DOMAIN", c.active
            ? <EditableField active kind="select" value={c.cur.domain} options={domSelectOptions} onSave={c.saveField("domain")} />
            : <DomainPill domain={entity.domain} label={entity.domain} />),
          kvRow("DESCRIPTION", <SuggestField active={c.active} value={c.cur.description} type="taxonomy" entityId={entity?.id} title={c.cur.title} onSave={c.saveField("description")} onChangeLive={c.liveField("description")} />),
        ]} />
      </InspectorPanel.Section>

      {!c.isCreate && (
        <>
          <InspectorPanel.Section title="Concept schemes" count={schemes.length}>
            {schemes.length === 0 ? <em style={{ fontSize: 12, color: "rgb(var(--canvas-fg-3))" }}>— none —</em> : (
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {schemes.map((s) => (
                  <div key={s.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "3px 0" }}>
                    <DomainPill domain={s.domain} label={s.title} />
                    <span style={{ marginLeft: "auto", fontFamily: "var(--font-mono)", fontSize: 11, color: "rgb(var(--canvas-fg-3))" }}>{s.classes} cls</span>
                  </div>
                ))}
              </div>
            )}
          </InspectorPanel.Section>
          <InspectorPanel.Section title="Stats">
            <KVGrid keyWidth={120} rows={[
              kvRow("CLASSES", <span style={{ fontFamily: "var(--font-mono)" }}>{entity.classes}</span>),
              kvRow("INDIVIDUALS", <span style={{ fontFamily: "var(--font-mono)" }}>{entity.individuals}</span>),
              kvRow("UPDATED", <span style={{ fontFamily: "var(--font-mono)", fontSize: 11.5, color: "rgb(var(--canvas-fg-3))" }}>{entity.updated}</span>),
            ]} />
          </InspectorPanel.Section>
        </>
      )}
    </InlineInspector>
  );
}

// ---- Concept scheme ----------------------------------------------------
function SchemeInspector({ entity, mode, initialDraft, onEnterEdit, onDone, onCreated, onCancel, onDelete, onDuplicate }) {
  const data = useCS();
  const c = useEntityEdit("scheme", entity, mode, initialDraft);
  const idVal = c.isCreate ? c.draft.id : entity.id;
  const tax = data.taxonomies.find((t) => t.id === c.cur.taxonomy_id);
  const taxOpts = data.taxonomies.map((t) => ({ value: t.id, label: t.title, description: t.id }));
  const classes = entity ? data.classes.filter((x) => x.concept_scheme_id === entity.id) : [];
  const validId = c.isCreate && CSStore.validateIdent("scheme", c.draft.id) === null && c.draft.title.trim() && c.draft.taxonomy_id;

  // cross-field: scheme domain follows its taxonomy
  const onTax = (v) => {
    const t = data.taxonomies.find((x) => x.id === v);
    if (c.isCreate) { c.setField("taxonomy_id", v); if (t) c.setField("domain", t.domain); }
    else { CSStore.update("scheme", entity.id, { taxonomy_id: v, domain: t ? t.domain : entity.domain }, { field: "taxonomy" }); }
  };

  const create = () => { const r = CSStore.create("scheme", { ...c.draft, classes: 0 }); onCreated(r.id); };

  return (
    <InlineInspector mode={mode} typeLabel="scheme" eyebrow={`CONCEPT SCHEME · ${c.cur.domain || ""}`}
      title={c.cur.title} id={idVal || "—"} version={entity?.version}
      onEdit={onEnterEdit} onDone={onDone} onCreate={create} onCancel={onCancel} canCreate={validId}
      onDelete={onDelete} onDuplicate={onDuplicate} footerHint={`PUT /concept_schemes/${idVal || "…"}`}>
      <InspectorPanel.Section title="Identity">
        <KVGrid keyWidth={120} rows={[
          kvRow("IDENTIFIER", c.isCreate
            ? <EditableField active value={c.draft.id} kind="ident" placeholder="sch_my_scheme" onChangeLive={(v) => c.setField("id", v)} onSave={(v) => c.setField("id", v)} validate={(v) => CSStore.validateIdent("scheme", v)} autoFocus />
            : <span style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>{entity.id}</span>),
          kvRow("TITLE", <EditableField active={c.active} value={c.cur.title} onSave={c.saveField("title")} onChangeLive={c.liveField("title")} placeholder="Display title" />),
          kvRow("TAXONOMY", c.active
            ? <EditableField active kind="select" value={c.cur.taxonomy_id} options={taxOpts} onSave={onTax} placeholder="Select taxonomy…" />
            : <span>{tax ? <DomainPill domain={tax.domain} label={tax.title} /> : "—"}</span>),
          kvRow("DOMAIN", <DomainPill domain={c.cur.domain} label={(c.cur.domain || "—") + " · inherited"} />),
          kvRow("DESCRIPTION", <SuggestField active={c.active} value={c.cur.description} type="scheme" entityId={entity?.id} title={c.cur.title} context={tax?.title} onSave={c.saveField("description")} onChangeLive={c.liveField("description")} />),
        ]} />
      </InspectorPanel.Section>

      {!c.isCreate && (
        <InspectorPanel.Section title="Classes" count={classes.length}>
          {classes.length === 0 ? <em style={{ fontSize: 12, color: "rgb(var(--canvas-fg-3))" }}>— none —</em> : (
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {classes.map((cl) => (
                <div key={cl.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "3px 0" }}>
                  <DomainPill domain={cl.domain} label={cl.title} />
                  <span style={{ marginLeft: "auto", fontFamily: "var(--font-mono)", fontSize: 11, color: "rgb(var(--canvas-fg-3))" }}>{cl.individuals} ind</span>
                </div>
              ))}
            </div>
          )}
        </InspectorPanel.Section>
      )}
    </InlineInspector>
  );
}

// ---- Class -------------------------------------------------------------
function ClassInspector({ entity, mode, initialDraft, onEnterEdit, onDone, onCreated, onCancel, onDelete, onDuplicate }) {
  const data = useCS();
  const c = useEntityEdit("class", entity, mode, initialDraft);
  const idVal = c.isCreate ? c.draft.id : entity.id;
  const sch = data.concept_schemes.find((s) => s.id === c.cur.concept_scheme_id);
  const tax = data.taxonomies.find((t) => t.id === (sch?.taxonomy_id || c.cur.taxonomy_id));
  const schemeOpts = data.concept_schemes.map((s) => ({ value: s.id, label: s.title, description: s.id }));
  // parent options: same scheme, exclude self & descendants
  const descendants = useMemo(() => {
    if (!entity) return new Set();
    const set = new Set(); const walk = (id) => data.classes.filter((x) => x.parent_class_id === id).forEach((x) => { set.add(x.id); walk(x.id); });
    walk(entity.id); return set;
  }, [data.classes, entity]);
  const parentOpts = [{ value: "", label: "— root (no parent) —" }].concat(
    data.classes.filter((x) => x.concept_scheme_id === c.cur.concept_scheme_id && x.id !== entity?.id && !descendants.has(x.id))
      .map((x) => ({ value: x.id, label: x.title, description: x.id })));

  const parent = c.cur.parent_class_id ? data.classes.find((x) => x.id === c.cur.parent_class_id) : null;
  const parentMismatch = parent && parent.concept_scheme_id !== c.cur.concept_scheme_id;
  const children = entity ? data.classes.filter((x) => x.parent_class_id === entity.id) : [];
  const indSample = entity ? data.individuals.filter((i) => i.class_ids.includes(entity.id)).slice(0, 5) : [];
  const rels = entity ? data.relationships.filter((r) => r.source_id === entity.id || r.target_id === entity.id) : [];
  const validId = c.isCreate && CSStore.validateIdent("class", c.draft.id) === null && c.draft.title.trim() && c.draft.concept_scheme_id;

  const onScheme = (v) => {
    const s = data.concept_schemes.find((x) => x.id === v);
    const patch = { concept_scheme_id: v, taxonomy_id: s?.taxonomy_id, domain: s?.domain };
    if (c.isCreate) c.setDraft((d) => ({ ...d, ...patch }));
    else CSStore.update("class", entity.id, patch, { field: "scheme" });
  };

  const create = () => { const r = CSStore.create("class", { ...c.draft, individuals: 0 }); onCreated(r.id); };

  return (
    <InlineInspector mode={mode} typeLabel="class" eyebrow={`CLASS · ${c.cur.domain || ""}`}
      title={c.cur.title} id={idVal || "—"} version={entity?.version}
      onEdit={onEnterEdit} onDone={onDone} onCreate={create} onCancel={onCancel} canCreate={validId}
      onDelete={onDelete} onDuplicate={onDuplicate} footerHint={`PUT /classes/${idVal || "…"}`}>
      <InspectorPanel.Section title="Identity">
        <KVGrid keyWidth={130} rows={[
          kvRow("IDENTIFIER", c.isCreate
            ? <EditableField active value={c.draft.id} kind="ident" placeholder="cls_my_class" onChangeLive={(v) => c.setField("id", v)} onSave={(v) => c.setField("id", v)} validate={(v) => CSStore.validateIdent("class", v)} autoFocus />
            : <span style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>{entity.id}</span>),
          kvRow("TITLE", <EditableField active={c.active} value={c.cur.title} onSave={c.saveField("title")} onChangeLive={c.liveField("title")} placeholder="Display title" />),
          kvRow("DESCRIPTION", <SuggestField active={c.active} value={c.cur.description} type="class" entityId={entity?.id} title={c.cur.title} context={sch?.title} onSave={c.saveField("description")} onChangeLive={c.liveField("description")} />),
          kvRow("SCHEME", c.active
            ? <EditableField active kind="select" value={c.cur.concept_scheme_id} options={schemeOpts} onSave={onScheme} placeholder="Select scheme…" />
            : <span>{sch ? <DomainPill domain={sch.domain} label={sch.title} /> : "—"}</span>),
          kvRow("PARENT CLASS", c.active
            ? <EditableField active kind="select" value={c.cur.parent_class_id || ""} options={parentOpts} onSave={c.saveField("parent_class_id")} placeholder="— root —" />
            : (parent ? <DomainPill domain={parent.domain} label={parent.title} /> : <em style={{ color: "rgb(var(--canvas-fg-3))" }}>— root —</em>)),
          kvRow("TAXONOMY", <span>{tax ? <DomainPill domain={tax.domain} label={tax.title} /> : "—"}</span>),
        ]} />
        {c.active && parentMismatch && (
          <div style={{ marginTop: 10 }}><FormCallout variant="warn" icon="alert">Parent `{parent.id}` is in a different scheme. A parent class must share this class's concept scheme.</FormCallout></div>
        )}
      </InspectorPanel.Section>

      {!c.isCreate && (
        <>
          <InspectorPanel.Section title="Children" count={children.length}>
            {children.length === 0 ? <em style={{ fontSize: 12, color: "rgb(var(--canvas-fg-3))" }}>— none —</em> : (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>{children.map((cl) => <DomainPill key={cl.id} domain={cl.domain} label={cl.title} />)}</div>
            )}
          </InspectorPanel.Section>
          <InspectorPanel.Section title="Sample individuals" count={entity.individuals} actions={indSample.length ? <Button variant="link" size="sm">Show all →</Button> : null}>
            {indSample.length === 0 ? <em style={{ fontSize: 12, color: "rgb(var(--canvas-fg-3))" }}>— none yet —</em> : (
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {indSample.map((i) => (
                  <div key={i.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "3px 0" }}>
                    <span style={{ flex: 1, fontSize: 12.5 }}>{i.title}</span>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "rgb(var(--canvas-fg-3))" }}>{i.id}</span>
                  </div>
                ))}
              </div>
            )}
          </InspectorPanel.Section>
          <InspectorPanel.Section title="Relationships" count={rels.length}>
            {rels.length === 0 ? <em style={{ fontSize: 12, color: "rgb(var(--canvas-fg-3))" }}>— none —</em> : (
              <div style={{ display: "flex", flexDirection: "column", gap: 6, fontFamily: "var(--font-mono)", fontSize: 11.5 }}>
                {rels.map((r) => {
                  const prop = data.property_definitions.find((p) => p.id === r.property_definition_id);
                  const isSrc = r.source_id === entity.id;
                  const other = (isSrc ? r.target_id : r.source_id);
                  const o = data.classes.find((x) => x.id === other) || data.individuals.find((x) => x.id === other);
                  return (
                    <div key={r.id} style={{ display: "flex", gap: 10 }}>
                      <span style={{ flex: 1 }}>{isSrc ? entity.title : (o?.title || "?")}<span style={{ color: "rgb(var(--canvas-fg-3))" }}> — {prop?.identifier} → </span>{isSrc ? (o?.title || "?") : entity.title}</span>
                    </div>
                  );
                })}
              </div>
            )}
            {c.isEdit && <RelationshipSuggester node={entity} />}
          </InspectorPanel.Section>

          <GroundingSection type="class" node={entity} active={c.isEdit} />
        </>
      )}
    </InlineInspector>
  );
}

// ---- Property definition ----------------------------------------------
function PropertyInspector({ entity, mode, initialDraft, onEnterEdit, onDone, onCreated, onCancel, onDelete, onDuplicate }) {
  const data = useCS();
  const c = useEntityEdit("property", entity, mode, initialDraft);
  const idVal = c.isCreate ? c.draft.identifier : entity.identifier;
  const usedIn = entity ? data.relationships.filter((r) => r.property_definition_id === entity.id) : [];
  const validId = c.isCreate && CSStore.validateIdent("property", c.draft.identifier) === null && c.draft.title.trim();

  const relevanceVal = c.cur.is_relevant === true ? "true" : c.cur.is_relevant === false ? "false" : "null";
  const setRelevance = (v) => {
    const val = v === "true" ? true : v === "false" ? false : null;
    if (c.isCreate) c.setField("is_relevant", val); else CSStore.update("property", entity.id, { is_relevant: val }, { field: "relevance" });
  };
  const relChip = (r) => r === true ? <Chip variant="emerald">relevant</Chip> : r === false ? <Chip variant="rose">irrelevant</Chip> : <Chip variant="neutral">unevaluated</Chip>;

  const create = () => { const r = CSStore.create("property", { ...c.draft, id: "prop_" + c.draft.identifier }); onCreated(r.id); };

  return (
    <InlineInspector mode={mode} typeLabel="property" eyebrow="PROPERTY · predicate"
      title={c.cur.title} id={idVal || "—"} version={entity?.version}
      onEdit={onEnterEdit} onDone={onDone} onCreate={create} onCancel={onCancel} canCreate={validId}
      onDelete={onDelete} onDuplicate={onDuplicate} footerHint={`PUT /property_definitions/${entity?.id || "…"}`}>
      <InspectorPanel.Section title="Identity">
        <KVGrid keyWidth={120} rows={[
          kvRow("IDENTIFIER", c.isCreate
            ? <EditableField active value={c.draft.identifier} kind="ident" placeholder="has_part" onChangeLive={(v) => c.setField("identifier", v)} onSave={(v) => c.setField("identifier", v)} validate={(v) => CSStore.validateIdent("property", v)} autoFocus />
            : <span style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>{entity.identifier}</span>),
          kvRow("TITLE", <EditableField active={c.active} value={c.cur.title} onSave={c.saveField("title")} onChangeLive={c.liveField("title")} placeholder="Display title" />),
          kvRow("DESCRIPTION", <SuggestField active={c.active} value={c.cur.description} type="property" entityId={entity?.id} title={c.cur.title} onSave={c.saveField("description")} onChangeLive={c.liveField("description")} rows={2} />),
          kvRow("RELEVANCE", c.active
            ? <SegmentedControl value={relevanceVal} onChange={setRelevance} options={[{ value: "true", label: "relevant" }, { value: "null", label: "unevaluated" }, { value: "false", label: "irrelevant" }]} />
            : relChip(c.cur.is_relevant)),
          kvRow("ORIGIN", <span style={{ fontFamily: "var(--font-mono)", fontSize: 11.5, color: "rgb(var(--canvas-fg-3))" }}>{c.cur.origin}</span>),
        ]} />
      </InspectorPanel.Section>
      {!c.isCreate && (
        <InspectorPanel.Section title="Used by relationships" count={usedIn.length}>
          {usedIn.length === 0 ? <em style={{ fontSize: 12, color: "rgb(var(--canvas-fg-3))" }}>— not yet used —</em> : (
            <div style={{ display: "flex", flexDirection: "column", gap: 4, fontFamily: "var(--font-mono)", fontSize: 11.5 }}>
              {usedIn.slice(0, 8).map((r) => <div key={r.id} style={{ color: "rgb(var(--canvas-fg-2))" }}>{r.id}</div>)}
            </div>
          )}
        </InspectorPanel.Section>
      )}
    </InlineInspector>
  );
}

// ---- Individual --------------------------------------------------------
function IndividualInspector({ entity, mode, initialDraft, onEnterEdit, onDone, onCreated, onCancel, onDelete, onDuplicate }) {
  const data = useCS();
  const c = useEntityEdit("individual", entity, mode, initialDraft);
  const idVal = c.isCreate ? c.draft.id : entity.id;
  const classChips = (c.cur.class_ids || []).map((cid) => data.classes.find((x) => x.id === cid)).filter(Boolean);
  const rels = entity ? data.relationships.filter((r) => r.source_id === entity.id || r.target_id === entity.id) : [];
  const validId = c.isCreate && CSStore.validateIdent("individual", c.draft.id) === null && c.draft.title.trim() && (c.draft.class_ids || []).length;

  const create = () => { const r = CSStore.create("individual", { ...c.draft, confidence: parseFloat(c.draft.confidence) || 1 }); onCreated(r.id); };

  return (
    <InlineInspector mode={mode} typeLabel="individual" eyebrow="INDIVIDUAL · instance"
      title={c.cur.title} id={idVal || "—"} version={entity?.version}
      onEdit={onEnterEdit} onDone={onDone} onCreate={create} onCancel={onCancel} canCreate={validId}
      onDelete={onDelete} onDuplicate={onDuplicate} footerHint={`PUT /individuals/${idVal || "…"}`}>
      <InspectorPanel.Section title="Identity">
        <KVGrid keyWidth={110} rows={[
          kvRow("IDENTIFIER", c.isCreate
            ? <EditableField active value={c.draft.id} kind="ident" placeholder="ind_brca1" onChangeLive={(v) => c.setField("id", v)} onSave={(v) => c.setField("id", v)} validate={(v) => CSStore.validateIdent("individual", v)} autoFocus />
            : <span style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>{entity.id}</span>),
          kvRow("TITLE", <EditableField active={c.active} value={c.cur.title} onSave={c.saveField("title")} onChangeLive={c.liveField("title")} placeholder="Display title" />),
          kvRow("DESCRIPTION", <SuggestField active={c.active} value={c.cur.description} type="individual" entityId={entity?.id} title={c.cur.title} onSave={c.saveField("description")} onChangeLive={c.liveField("description")} rows={2} />),
          kvRow("CLASSES", c.active
            ? <Select multiple values={c.cur.class_ids || []} placeholder="Assign classes…"
                onValuesChange={(vals) => { if (c.isCreate) c.setField("class_ids", vals); else CSStore.update("individual", entity.id, { class_ids: vals }, { field: "classes" }); }}>
                {data.classes.map((cl) => <Select.CheckboxItem key={cl.id} value={cl.id} description={cl.id}>{cl.title}</Select.CheckboxItem>)}
              </Select>
            : (classChips.length ? <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>{classChips.map((cl) => <Chip key={cl.id} variant="neutral">{cl.title}</Chip>)}</div> : "—")),
          kvRow("SOURCE", <EditableField active={c.active} value={c.cur.source} onSave={c.saveField("source")} onChangeLive={c.liveField("source")} mono placeholder="NCBI" />),
          kvRow("CONFIDENCE", c.active
            ? <ParamSlider active label="" value={parseFloat(c.cur.confidence) || 0} min={0} max={1} step={0.01} fmt={(v) => v.toFixed(2)} onChange={(v) => { if (c.isCreate) c.setField("confidence", v); else CSStore.update("individual", entity.id, { confidence: v }, { field: "confidence" }); }} />
            : <span style={{ fontFamily: "var(--font-mono)" }}>{(c.cur.confidence ?? 0).toFixed ? c.cur.confidence.toFixed(2) : c.cur.confidence}</span>),
        ]} />
      </InspectorPanel.Section>
      {!c.isCreate && (
        <InspectorPanel.Section title="Relationships" count={rels.length}>
          {rels.length === 0 ? <em style={{ fontSize: 12, color: "rgb(var(--canvas-fg-3))" }}>— none —</em> : (
            <div style={{ display: "flex", flexDirection: "column", gap: 6, fontFamily: "var(--font-mono)", fontSize: 11.5 }}>
              {rels.map((r) => {
                const prop = data.property_definitions.find((p) => p.id === r.property_definition_id);
                const isSrc = r.source_id === entity.id;
                const o = data.classes.find((x) => x.id === (isSrc ? r.target_id : r.source_id)) || data.individuals.find((x) => x.id === (isSrc ? r.target_id : r.source_id));
                return <div key={r.id}>{isSrc ? entity.title : (o?.title || "?")}<span style={{ color: "rgb(var(--canvas-fg-3))" }}> — {prop?.identifier} → </span>{isSrc ? (o?.title || "?") : entity.title}</div>;
              })}
            </div>
          )}
        </InspectorPanel.Section>
      )}
    </InlineInspector>
  );
}

// ---- Relationship (triple) --------------------------------------------
function RelationshipInspector({ entity, mode, initialDraft, onEnterEdit, onDone, onCreated, onCancel, onDelete, onDuplicate }) {
  const data = useCS();
  const isCreate = mode === "create";
  const isEdit = mode === "edit";
  const active = isCreate || isEdit;

  const nodeById = (id) => data.classes.find((x) => x.id === id) || data.individuals.find((x) => x.id === id);
  const toResult = (n) => n ? { id: n.id, label: n.title, domain: n.domain, domainColor: domainColorOf(n.domain) } : undefined;

  const seed = initialDraft || (entity ? { source_id: entity.source_id, target_id: entity.target_id, property_definition_id: entity.property_definition_id, confidence: entity.confidence, source: entity.source } : newDraft("relationship"));
  const [draft, setDraft] = useState(seed);
  const cur = isCreate ? draft : (entity || {});

  const [srcQ, setSrcQ] = useState(""); const [tgtQ, setTgtQ] = useState("");
  const search = (q) => { const Q = q.toLowerCase(); return [...data.classes, ...data.individuals].filter((n) => n.title.toLowerCase().includes(Q) || n.id.toLowerCase().includes(Q)).slice(0, 8).map(toResult); };

  const predicates = data.property_definitions.map((p) => p.identifier);
  const predById = (id) => data.property_definitions.find((p) => p.id === id);
  const predByIdent = (ident) => data.property_definitions.find((p) => p.identifier === ident);

  const builderValue = {
    source: toResult(nodeById(cur.source_id)),
    target: toResult(nodeById(cur.target_id)),
    predicate: predById(cur.property_definition_id)?.identifier || "",
  };
  const onBuilder = (v) => {
    const patch = {
      source_id: v.source?.id || "",
      target_id: v.target?.id || "",
      property_definition_id: v.predicate ? (predByIdent(v.predicate)?.id || cur.property_definition_id) : cur.property_definition_id,
    };
    if (isCreate) setDraft((d) => ({ ...d, ...patch }));
    else CSStore.update("relationship", entity.id, patch, { field: "triple" });
  };

  const src = nodeById(cur.source_id); const tgt = nodeById(cur.target_id); const prop = predById(cur.property_definition_id);
  const validNew = isCreate && cur.source_id && cur.target_id && cur.property_definition_id;
  const create = () => {
    const id = "rel_" + Math.random().toString(36).slice(2, 6);
    const r = CSStore.create("relationship", { ...draft, id, created: "now", confidence: parseFloat(draft.confidence) || 1 });
    onCreated(r.id);
  };

  return (
    <InlineInspector mode={mode} typeLabel="relationship" eyebrow="RELATIONSHIP · triple"
      title={src && tgt ? `${src.title} → ${tgt.title}` : "New relationship"} id={isCreate ? "—" : entity.id}
      onEdit={onEnterEdit} onDone={onDone} onCreate={create} onCancel={onCancel} canCreate={validNew}
      onDelete={onDelete} onDuplicate={onDuplicate} footerHint={`PUT /relationships/${entity?.id || "…"}`}>
      <InspectorPanel.Section title="Triple">
        {active ? (
          <RelationshipBuilder
            value={builderValue} onChange={onBuilder}
            sourceQuery={srcQ} onSourceQueryChange={setSrcQ} sourceResults={search(srcQ)}
            targetQuery={tgtQ} onTargetQueryChange={setTgtQ} targetResults={search(tgtQ)}
            predicates={predicates}
            onSourceClear={() => onBuilder({ ...builderValue, source: undefined })}
            onTargetClear={() => onBuilder({ ...builderValue, target: undefined })}
          />
        ) : (
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", fontSize: 13 }}>
            {src ? <DomainPill domain={src.domain} label={src.title} /> : "?"}
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 11.5, color: "rgb(var(--canvas-fg-3))" }}>— {prop?.identifier} →</span>
            {tgt ? <DomainPill domain={tgt.domain} label={tgt.title} /> : "?"}
          </div>
        )}
      </InspectorPanel.Section>
      <InspectorPanel.Section title="Provenance">
        <KVGrid keyWidth={110} rows={[
          kvRow("CONFIDENCE", active
            ? <ParamSlider active label="" value={parseFloat(cur.confidence) || 0} min={0} max={1} step={0.01} fmt={(v) => v.toFixed(2)} onChange={(v) => { if (isCreate) setDraft((d) => ({ ...d, confidence: v })); else CSStore.update("relationship", entity.id, { confidence: v }, { field: "confidence" }); }} />
            : <span style={{ fontFamily: "var(--font-mono)" }}>{(cur.confidence ?? 0).toFixed ? cur.confidence.toFixed(2) : cur.confidence}</span>),
          kvRow("SOURCE", <EditableField active={active} value={cur.source} mono placeholder="manual"
            onSave={(v) => { if (isCreate) setDraft((d) => ({ ...d, source: v })); else CSStore.update("relationship", entity.id, { source: v }, { field: "source" }); }}
            onChangeLive={isCreate ? (v) => setDraft((d) => ({ ...d, source: v })) : undefined} />),
          ...(isCreate ? [] : [kvRow("CREATED", <span style={{ fontFamily: "var(--font-mono)", fontSize: 11.5, color: "rgb(var(--canvas-fg-3))" }}>{entity.created}</span>)]),
        ]} />
      </InspectorPanel.Section>
    </InlineInspector>
  );
}

Object.assign(window, { EntityInspector, newDraft });
