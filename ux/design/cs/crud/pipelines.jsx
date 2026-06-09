// =========================================================================
// Context Studio — Pipelines › Pipeline types & Configurations
// Pipeline Type = a python module implementing a pipeline (system-defined,
// read-only). Configuration (formerly "Flavor") = the user-editable layer:
// provider / model / prompts / parameters. Master (types) → detail (a type's
// configurations + a full inline editor).
// =========================================================================

const PROVIDERS = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
];
const MODELS = {
  openai: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
  anthropic: ["claude-3-5-sonnet", "claude-3-opus", "claude-3-sonnet", "claude-3-haiku"],
};
const PT_ICON = (n) => (window.ICONS && window.ICONS[n]) ? n : "pipeline";

function slugifyCfg(name) {
  return "cfg_" + (name || "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 28);
}

// ---- Configuration editor (view / edit / create) ----------------------
function ConfigEditor({ ptype, config, mode, onEnterEdit, onDone, onCreated, onCancel, onDelete, onDuplicate }) {
  const isCreate = mode === "create";
  const isEdit = mode === "edit";
  const active = isCreate || isEdit;

  const seed = config || {
    id: "", pipeline_type_id: ptype.id, name: "", description: "",
    provider: "openai", model: "gpt-4o", system_prompt: "", user_prompt_template: "",
    parameters: { temperature: 0.4, max_tokens: 800, top_p: 0.9 }, enabled: true,
  };
  const [draft, setDraft] = useState(seed);
  const cur = isCreate ? draft : config;

  const setField = (k, v) => setDraft((d) => ({ ...d, [k]: v }));
  const setParam = (k, v) => {
    if (isCreate) setDraft((d) => ({ ...d, parameters: { ...d.parameters, [k]: v } }));
    else CSStore.update("configuration", config.id, { parameters: { ...config.parameters, [k]: v } }, { field: "params" });
  };
  const save = (k) => (v) => { if (isCreate) setField(k, v); else CSStore.update("configuration", config.id, { [k]: v }, { field: k }); };
  const live = (k) => (isCreate ? (v) => setField(k, v) : undefined);

  const modelOpts = (MODELS[cur.provider] || []).map((m) => ({ value: m, label: m }));
  const onProvider = (v) => {
    const m = MODELS[v][0];
    if (isCreate) setDraft((d) => ({ ...d, provider: v, model: m }));
    else CSStore.update("configuration", config.id, { provider: v, model: m }, { field: "provider" });
  };

  const params = cur.parameters || {};
  const validNew = isCreate && draft.name.trim() && draft.user_prompt_template.trim();
  const create = () => {
    const id = slugifyCfg(draft.name) || ("cfg_" + Math.random().toString(36).slice(2, 6));
    const r = CSStore.create("configuration", { ...draft, id, execution_count: 0, average_duration_ms: 0, average_cost: 0 });
    onCreated(r.id);
  };

  const insertVar = (v) => {
    const t = cur.user_prompt_template || "";
    const next = t + (t.endsWith(" ") || t === "" ? "" : " ") + `{{${v}}}`;
    save("user_prompt_template")(next);
  };

  const headerActions = isCreate ? null : isEdit ? (
    <Button variant="primary" size="sm" onClick={onDone}><Icon name="check" size={13} /> Done</Button>
  ) : (
    <div className="ce-inspector-actions">
      <Button variant="ghost" size="sm" icon onClick={onEnterEdit} title="Edit"><Icon name="edit" size={13} /></Button>
      <RowMenu placement="bottom-end"
        actions={[{ id: "edit", label: "Edit", icon: "edit" }, { id: "duplicate", label: "Duplicate", icon: "copy" }, { type: "separator" }, { id: "delete", label: "Delete…", icon: "trash", danger: true }]}
        onAction={(a) => { if (a === "edit") onEnterEdit(); if (a === "duplicate") onDuplicate(); if (a === "delete") onDelete(); }} />
    </div>
  );

  return (
    <Panel
      title={isCreate ? "New configuration" : cur.name}
      subtitle={isCreate ? `Under ${ptype.name}` : undefined}
      headerAction={
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {!isCreate && (cur.enabled ? <Chip variant="emerald">enabled</Chip> : <Chip variant="neutral">disabled</Chip>)}
          {!isCreate && <VersionPill>{cur.version}</VersionPill>}
          {headerActions}
        </div>
      }
    >
      <div className="cfg-editor">
        {isEdit && <FormCallout variant="info" icon="info">Editing — changes save automatically on blur. Saving bumps the configuration version.</FormCallout>}

        {/* Identity */}
        <div>
          <div className="cfg-section-title">Identity</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <Field label="Name" required={isCreate}>
              <EditableField active={active} value={cur.name} onSave={save("name")} onChangeLive={live("name")} placeholder="Configuration name" autoFocus={isCreate} />
            </Field>
            <Field label="Description">
              <SuggestField active={active} value={cur.description} type="configuration" entityId={config?.id} title={cur.name} context={ptype.name} onSave={save("description")} onChangeLive={live("description")} rows={2} />
            </Field>
            <div className="cfg-editor__grid2">
              <Field label="Provider">
                {active ? <Select value={cur.provider} onChange={onProvider}>{PROVIDERS.map((p) => <Select.Item key={p.value} value={p.value}>{p.label}</Select.Item>)}</Select>
                  : <span style={{ fontFamily: "var(--font-mono)", fontSize: 12.5 }}>{cur.provider}</span>}
              </Field>
              <Field label="Model">
                {active ? <Select value={cur.model} onChange={save("model")}>{modelOpts.map((m) => <Select.Item key={m.value} value={m.value}>{m.label}</Select.Item>)}</Select>
                  : <span style={{ fontFamily: "var(--font-mono)", fontSize: 12.5 }}>{cur.model}</span>}
              </Field>
            </div>
            <Field label="Status">
              {active ? <SegmentedControl value={cur.enabled ? "on" : "off"} onChange={(v) => save("enabled")(v === "on")} options={[{ value: "on", label: "Enabled" }, { value: "off", label: "Disabled" }]} />
                : (cur.enabled ? <Chip variant="emerald">enabled</Chip> : <Chip variant="neutral">disabled</Chip>)}
            </Field>
          </div>
        </div>

        {/* Prompts */}
        <div>
          <div className="cfg-section-title">Prompts</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <Field label="System prompt">
              {active ? <TextArea className="cfg-prompt" mono value={cur.system_prompt || ""} rows={3} onChange={(e) => save("system_prompt")(e.target.value)} onBlur={(e) => save("system_prompt")(e.target.value)} />
                : <pre style={{ margin: 0, whiteSpace: "pre-wrap", fontFamily: "var(--font-mono)", fontSize: 12, color: "rgb(var(--canvas-fg-2))", lineHeight: 1.55 }}>{cur.system_prompt || "—"}</pre>}
            </Field>
            <Field label="User prompt template" hint="Jinja2 · {{variables}}">
              {active ? <TextArea className="cfg-prompt" mono value={cur.user_prompt_template || ""} rows={4} onChange={(e) => save("user_prompt_template")(e.target.value)} onBlur={(e) => save("user_prompt_template")(e.target.value)} />
                : <pre style={{ margin: 0, whiteSpace: "pre-wrap", fontFamily: "var(--font-mono)", fontSize: 12, color: "rgb(var(--canvas-fg-2))", lineHeight: 1.55 }}>{cur.user_prompt_template || "—"}</pre>}
              <VariableChips template={cur.user_prompt_template} onInsert={active ? insertVar : undefined} />
            </Field>
          </div>
        </div>

        {/* Parameters */}
        <div>
          <div className="cfg-section-title">Parameters</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 18 }}>
            <ParamSlider active={active} label="Temperature" value={params.temperature ?? 0.4} min={0} max={2} step={0.05} fmt={(v) => v.toFixed(2)} onChange={(v) => setParam("temperature", v)} />
            <ParamSlider active={active} label="Max tokens" value={params.max_tokens ?? 800} min={64} max={4096} step={32} fmt={(v) => Math.round(v)} onChange={(v) => setParam("max_tokens", Math.round(v))} />
            <ParamSlider active={active} label="Top-p" value={params.top_p ?? 0.9} min={0} max={1} step={0.01} fmt={(v) => v.toFixed(2)} onChange={(v) => setParam("top_p", v)} />
          </div>
        </div>

        {/* Usage (read-only) */}
        {!isCreate && (
          <div>
            <div className="cfg-section-title">Usage</div>
            <div className="cfg-stat-row">
              <div><div className="cfg-stat__k">executions</div><div className="cfg-stat__v">{(cur.execution_count || 0).toLocaleString()}</div></div>
              <div><div className="cfg-stat__k">avg duration</div><div className="cfg-stat__v">{cur.average_duration_ms ? (cur.average_duration_ms / 1000).toFixed(2) + "s" : "—"}</div></div>
              <div><div className="cfg-stat__k">avg cost</div><div className="cfg-stat__v">{cur.average_cost ? "$" + cur.average_cost.toFixed(4) : "—"}</div></div>
              <div><div className="cfg-stat__k">updated</div><div className="cfg-stat__v" style={{ fontSize: 12 }}>{cur.updated}</div></div>
            </div>
          </div>
        )}

        {isCreate && (
          <div style={{ display: "flex", gap: 8 }}>
            <Button variant="primary" onClick={create} disabled={!validNew}><Icon name="check" size={13} /> Create configuration</Button>
            <Button variant="ghost" onClick={onCancel}>Cancel</Button>
          </div>
        )}
        {!isCreate && (
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "rgb(var(--canvas-fg-3))" }}>PUT /api/pipeline_configurations/{config.id}</div>
        )}
      </div>
    </Panel>
  );
}

// ---- Page --------------------------------------------------------------
function CSPipelineTypes({ route, onNav, surfaceRef }) {
  const data = useCS();
  const types = data.pipeline_types;
  const [typeId, setTypeId] = useState(types[0]?.id);
  const [cfgId, setCfgId] = useState(null);
  const [mode, setMode] = useState("view");
  const [draftKey, setDraftKey] = useState(0);
  const [del, setDel] = useState(null);

  const ptype = types.find((t) => t.id === typeId) || types[0];
  const configs = data.configurations.filter((c) => c.pipeline_type_id === ptype.id);
  const config = cfgId ? data.configurations.find((c) => c.id === cfgId) : null;

  // expose create to the page header / palette
  useImperativeHandle(surfaceRef, () => ({
    startCreate: () => { setCfgId(null); setMode("create"); setDraftKey((k) => k + 1); },
  }), [ptype]);

  // command-palette "New configuration" lands here
  useEffect(() => {
    const p = window.__CS_PENDING;
    if (p && p.type === "configuration") { window.__CS_PENDING = null; const t = setTimeout(() => { setCfgId(null); setMode("create"); setDraftKey((k) => k + 1); }, 30); return () => clearTimeout(t); }
  }, []); // eslint-disable-line

  const selectType = (id) => { setTypeId(id); setCfgId(null); setMode("view"); };
  const selectCfg = (id) => { setCfgId(id); setMode("view"); };
  const newCfg = () => { setCfgId(null); setMode("create"); setDraftKey((k) => k + 1); };
  const onCreated = (id) => { setCfgId(id); setMode("view"); };
  const duplicate = (cfg) => { setDup(cfg); };
  const [dup, setDup] = useState(null);

  const confirmDelete = () => { CSStore.remove("configuration", del.id); if (cfgId === del.id) setCfgId(null); setDel(null); };

  return (
    <div data-screen-label="08 Pipelines · Pipeline types">
      <PageHeader
        eyebrow="PIPELINES · pipeline_type"
        title="Pipeline types"
        idChip="/pipelines/types"
        subtitle="A pipeline type is a python module implementing one stage of graph construction. Types are system-defined; you curate their Configurations — provider, model, prompts and parameters."
        actions={<><Button variant="ghost" onClick={() => onNav("pipelines/all")}><Icon name="pipeline" size={13} /> All pipelines</Button><Button variant="primary" onClick={newCfg}><Icon name="plus" size={13} /> New configuration</Button></>}
      />
      <div style={{ height: 18 }} />

      <div className="pt-grid">
        {/* master: pipeline types */}
        <div className="pt-list">
          {types.map((t) => {
            const n = data.configurations.filter((c) => c.pipeline_type_id === t.id).length;
            return (
              <button key={t.id} className={["pt-card", t.id === ptype.id ? "pt-card--active" : ""].join(" ")} onClick={() => selectType(t.id)}>
                <span className="pt-card__icon"><Icon name={PT_ICON(t.icon)} size={17} /></span>
                <span className="pt-card__body">
                  <span className="pt-card__name">{t.name}<Icon name="lock" size={11} style={{ color: "rgb(var(--canvas-fg-4))" }} /></span>
                  <span className="pt-card__desc">{t.description}</span>
                  <span className="pt-card__meta"><span>{n} config{n === 1 ? "" : "s"}</span></span>
                </span>
              </button>
            );
          })}
        </div>

        {/* detail */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {/* type summary (read-only / system) */}
          <Panel>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 14 }}>
              <span className="pt-card__icon" style={{ width: 40, height: 40 }}><Icon name={PT_ICON(ptype.icon)} size={20} /></span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: "rgb(var(--canvas-fg-1))" }}>{ptype.name}</h3>
                  <Chip variant="neutral"><Icon name="lock" size={10} /> system</Chip>
                </div>
                <p style={{ margin: "5px 0 0", fontSize: 12.5, color: "rgb(var(--canvas-fg-2))", lineHeight: 1.55 }}>{ptype.description}</p>
              </div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14, marginTop: 14 }}>
              <div><div className="cfg-stat__k">module</div><div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "rgb(var(--canvas-fg-1))", marginTop: 3 }}>{ptype.module}</div></div>
              <div><div className="cfg-stat__k">input</div><div style={{ fontSize: 12.5, color: "rgb(var(--canvas-fg-2))", marginTop: 3 }}>{ptype.inputs}</div></div>
              <div><div className="cfg-stat__k">output</div><div style={{ fontSize: 12.5, color: "rgb(var(--canvas-fg-2))", marginTop: 3 }}>{ptype.outputs}</div></div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 14, flexWrap: "wrap" }}>
              <span className="cfg-stat__k" style={{ marginRight: 4 }}>stages</span>
              {ptype.stages.map((s, i) => (
                <React.Fragment key={s}>
                  <Chip variant="neutral">{s}</Chip>
                  {i < ptype.stages.length - 1 && <Icon name="arrowRight" size={11} style={{ color: "rgb(var(--canvas-fg-4))" }} />}
                </React.Fragment>
              ))}
            </div>
          </Panel>

          {/* configurations master + editor */}
          <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: 14, alignItems: "start" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <div className="cs-between" style={{ marginBottom: 2 }}>
                <span className="cfg-section-title" style={{ margin: 0 }}>Configurations · {configs.length}</span>
                <Button variant="ghost" size="sm" icon onClick={newCfg} title="New configuration"><Icon name="plus" size={13} /></Button>
              </div>
              {configs.length === 0 && <div style={{ fontSize: 12, color: "rgb(var(--canvas-fg-3))", padding: "8px 2px" }}>No configurations yet.</div>}
              {configs.map((cfg) => (
                <button key={cfg.id} className={["cfg-row", cfg.id === cfgId && mode !== "create" ? "cfg-row--active" : ""].join(" ")} onClick={() => selectCfg(cfg.id)} style={{ textAlign: "left", cursor: "pointer" }}>
                  <span className="cfg-row__dot" style={{ background: cfg.enabled ? "rgb(var(--status-emerald))" : "rgb(var(--canvas-fg-4))" }} />
                  <span style={{ flex: 1, minWidth: 0 }}>
                    <span className="cfg-row__name">{cfg.name}</span>
                    <span className="cfg-row__model">{cfg.provider} · {cfg.model}</span>
                  </span>
                  <VersionPill>{cfg.version}</VersionPill>
                </button>
              ))}
            </div>

            <div>
              {mode === "create" ? (
                <ConfigEditor key={`cfg-create-${draftKey}`} ptype={ptype} config={null} mode="create" onCreated={onCreated} onCancel={() => setMode("view")} />
              ) : config ? (
                <ConfigEditor key={`${config.id}-${mode}`} ptype={ptype} config={config} mode={mode}
                  onEnterEdit={() => setMode("edit")} onDone={() => setMode("view")}
                  onDelete={() => setDel(config)} onDuplicate={() => duplicate(config)} />
              ) : (
                <EmptyInspector icon="settings" title="Select a configuration"
                  sub={`Pick a configuration under ${ptype.name}, or create a new one.`} />
              )}
            </div>
          </div>
        </div>
      </div>

      {del && (
        <ConfirmDialog isOpen onClose={() => setDel(null)} onConfirm={confirmDelete}
          variant="danger" title={`Delete “${del.name}”?`}
          subtitle="This configuration will be removed. Pipeline runs already executed with it keep their traceability records."
          message={<span style={{ fontSize: 12.5, color: "rgb(var(--canvas-fg-2))" }}>Configuration <code>{del.id}</code> under <strong>{ptype.name}</strong> will be deleted.</span>}
          confirmLabel="Delete configuration" />
      )}

      {/* duplicate: open create pre-filled */}
      {dup && <ConfigDuplicator dup={dup} ptype={ptype} onClose={() => setDup(null)} onCreated={(id) => { setDup(null); onCreated(id); }} />}
    </div>
  );
}

// duplicate helper — commits a copy immediately then selects it
function ConfigDuplicator({ dup, onClose, onCreated }) {
  useEffect(() => {
    const id = slugifyCfg(dup.name + " copy");
    const r = CSStore.create("configuration", {
      ...dup, id: id || ("cfg_" + Math.random().toString(36).slice(2, 6)),
      name: dup.name + " (copy)", version: 1, execution_count: 0, average_duration_ms: 0, average_cost: 0,
    });
    onCreated(r.id);
  }, []); // eslint-disable-line
  return null;
}

Object.assign(window, { CSPipelineTypes });
