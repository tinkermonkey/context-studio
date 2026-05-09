// Configuration page — wired to the admin endpoints described in
// /api/v1/admin/. Covers: aggregate health (SystemHealthResponse) plus the
// five granular component checks; the eight configuration sections with
// per-section PATCH semantics and credential masking; the in-memory
// background-task surface with its strict state machine.
//
// All data here is mock — the shape mirrors the response models so the
// surfaces stay honest.

// ---------------------------------------------------------------------------
// Mock state — modeled exactly on the response shapes
// ---------------------------------------------------------------------------

const CREDENTIAL_FIELD_NAMES = [
  "openai_api_key",
  "anthropic_api_key",
  "s3_access_key",
  "s3_secret_key",
];

const INITIAL_HEALTH = {
  status: "degraded",
  database_connected: true,
  nlp_pipeline_ready: true,
  embedding_model_loaded: true,
  llm_providers_available: ["openai", "anthropic"],
  uptime_seconds: 1234567, // ~14d 6h
  issues: [
    "reference_source eia_energy: auth failed (401 from upstream)",
    "1 background task failed: extract_pubmed_v3",
  ],
  checked_at: "2026-05-08T14:32:11Z",
};

const INITIAL_CONFIG = {
  server: {
    host: "0.0.0.0",
    port: 8080,
    cors_origins: ["http://localhost:3000", "https://studio.context.local"],
    request_timeout_seconds: 30,
  },
  database: {
    local_db_path: "/var/lib/context-studio/store.db",
    operations_db_path: "/var/lib/context-studio/ops.db",
    pool_size: 8,
    statement_timeout_ms: 5000,
  },
  llm: {
    openai_api_key: "***K91p",
    anthropic_api_key: "***qx3a",
    default_provider: "anthropic",
    default_model: "claude-3-5-sonnet-20241022",
    request_timeout_seconds: 60,
  },
  nlp: {
    model_name: "en_core_web_sm",
    batch_size: 64,
    enable_pretrained_ner: true,
  },
  embedding: {
    model_name: "sentence-transformers/all-MiniLM-L6-v2",
    device: "cuda:0",
    batch_size: 32,
    normalize: true,
  },
  reference_sources: {
    enabled_sources: ["pubmed", "ncbi_gene", "uniprot", "reactome", "arxiv", "ipcc_ar6"],
    rate_limits: {
      pubmed: 10,
      arxiv: 5,
      uniprot: 8,
      ncbi_gene: 10,
      reactome: 6,
      ipcc_ar6: 0, // local corpus, no rate limit
    },
    cache_ttl_seconds: 86400,
  },
  logging: {
    level: "INFO",
    json_output: true,
    file_path: "/var/log/context-studio/app.log",
    max_file_mb: 100,
  },
  sync: {
    s3_bucket: "cs-snapshots-prod",
    s3_region: "us-east-2",
    s3_access_key: "***Z42x",
    s3_secret_key: "***h9Lp",
    schedule_cron: "0 3 * * *",
  },
};

const INITIAL_TASKS = [
  {
    id: "4f1c6a9b-7e2d-4c1f-9b1a-0a8e1c6c9c01",
    name: "extract_pubmed_v3",
    status: "failed",
    created_at: "2026-05-08T13:11:42Z",
    started_at: "2026-05-08T13:11:43Z",
    completed_at: "2026-05-08T13:14:08Z",
    error: "OpenAI API: rate_limit_exceeded — retry budget exhausted after 4 attempts",
    result: null,
  },
  {
    id: "8c0d12e4-2a17-4b3f-8c19-77da82c6e2bd",
    name: "resolve_uniprot_aliases",
    status: "running",
    created_at: "2026-05-08T14:24:01Z",
    started_at: "2026-05-08T14:24:03Z",
    completed_at: null,
    error: null,
    result: null,
  },
  {
    id: "a7b3f0c1-9e54-4d28-a1c2-cb1d6f7e8901",
    name: "index_arxiv_cs_se",
    status: "pending",
    created_at: "2026-05-08T14:31:55Z",
    started_at: null,
    completed_at: null,
    error: null,
    result: null,
  },
  {
    id: "6d2f1810-44a7-4e0a-9f31-21cf8c3e44b7",
    name: "snapshot_to_s3",
    status: "completed",
    created_at: "2026-05-08T03:00:00Z",
    started_at: "2026-05-08T03:00:01Z",
    completed_at: "2026-05-08T03:11:24Z",
    error: null,
    result: { snapshot_id: "snap_2026_05_08", size_mb: 512.4, classes: 22, individuals: 524 },
  },
  {
    id: "3e9d4a01-1f6b-4c83-9c21-1a0b0d3a99e2",
    name: "extract_ipcc_corpus",
    status: "completed",
    created_at: "2026-05-07T22:16:08Z",
    started_at: "2026-05-07T22:16:09Z",
    completed_at: "2026-05-07T22:48:37Z",
    error: null,
    result: { documents: 420, individuals_added: 1834, classes_seen: 7 },
  },
];

// ---------------------------------------------------------------------------
// Section schema — drives the rail and the form rendering
// ---------------------------------------------------------------------------

const SECTIONS = [
  { id: "server", name: "Server", icon: "globe", desc: "Host, port and CORS origins." },
  {
    id: "database",
    name: "Database",
    icon: "database",
    desc: "Local store and operations DB paths.",
  },
  { id: "llm", name: "LLM providers", icon: "brain", desc: "API keys and default routing." },
  { id: "nlp", name: "NLP pipeline", icon: "sparkle", desc: "spaCy model and tokeniser config." },
  {
    id: "embedding",
    name: "Embedding model",
    icon: "layers",
    desc: "Vector model and inference device.",
  },
  {
    id: "reference_sources",
    name: "Reference sources",
    icon: "reference",
    desc: "External corpora — toggles & rate limits.",
  },
  { id: "logging", name: "Logging", icon: "doc", desc: "Verbosity and log destination." },
  { id: "sync", name: "Sync (S3)", icon: "ext", desc: "Optional snapshot target. May be unset." },
];

const NAV = [
  { id: "overview", name: "Overview", icon: "dashboard", kind: "special" },
  ...SECTIONS.map((s) => ({ ...s, kind: "section" })),
  { id: "__sep1", kind: "sep" },
  { id: "tasks", name: "Background tasks", icon: "workflow", kind: "special" },
  { id: "danger", name: "Reset to defaults", icon: "alert", kind: "special", tone: "danger" },
];

// ---------------------------------------------------------------------------
// Small presentational helpers
// ---------------------------------------------------------------------------

function EndpointPill({ method, path }) {
  const cls = "ep-method ep-" + method.toLowerCase();
  return (
    <span className="endpoint-pill">
      <span className={cls}>{method}</span>
      <span className="ep-path">{path}</span>
    </span>
  );
}

function StatusBadge({ status }) {
  const map = {
    healthy: { cls: "emerald", label: "healthy" },
    degraded: { cls: "amber", label: "degraded" },
    unhealthy: { cls: "rose", label: "unhealthy" },
  };
  const v = map[status] || map.healthy;
  return (
    <span className={"chip " + v.cls}>
      <span className="dot"></span>
      {v.label}
    </span>
  );
}

function fmtUptime(s) {
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  return `${d}d ${h}h ${m}m`;
}

function fmtRelative(iso) {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  const now = Date.now();
  const diff = Math.max(0, Math.floor((now - t) / 1000));
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ${Math.floor((diff % 3600) / 60)}m ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function fmtDuration(start, end) {
  if (!start || !end) return "—";
  const s = Math.max(0, Math.floor((new Date(end) - new Date(start)) / 1000));
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`;
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
}

// Health pill used in the component grid
function ComponentCheck({ icon, label, ok, detail, tone, endpoint }) {
  return (
    <div className={"health-cell " + (ok ? "ok" : "bad") + (tone || "")}>
      <div className="health-cell-head">
        <span className="ic">
          <Icon name={icon} size={14} />
        </span>
        <span className="lbl">{label}</span>
        <span className={"cell-state " + (ok ? "ok" : "bad")}>
          {ok ? <Icon name="check" size={11} /> : <Icon name="x" size={11} />}
          <span>{ok ? "ok" : "down"}</span>
        </span>
      </div>
      <div className="health-cell-detail">{detail}</div>
      {endpoint && <div className="health-cell-foot mono">{endpoint}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Credential field — masked by default, "Replace" reveals an input.
// Reflects the API contract: write-only credentials, never read the real value.
// ---------------------------------------------------------------------------

function CredentialField({ label, hint, masked, draft, onDraftChange, onClear }) {
  const replacing = draft !== undefined && draft !== null;
  return (
    <Field label={label} hint={hint}>
      {replacing ? (
        <div className="cred-row replacing">
          <input
            type="password"
            className="input mono"
            placeholder="paste new secret"
            value={draft}
            autoComplete="off"
            onChange={(e) => onDraftChange(e.target.value)}
          />
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClear}>
            Cancel
          </button>
        </div>
      ) : (
        <div className="cred-row">
          <span className="cred-mask mono">{masked || "— not set —"}</span>
          <span className="cred-flag">write-only</span>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => onDraftChange("")}>
            <Icon name="edit" size={11} /> Replace
          </button>
        </div>
      )}
    </Field>
  );
}

// ---------------------------------------------------------------------------
// Per-section forms
// ---------------------------------------------------------------------------

function ServerForm({ value, onChange }) {
  return (
    <>
      <div className="form-grid two">
        <Field label="Host" hint="bind address">
          <TextInput mono value={value.host} onChange={(v) => onChange({ host: v })} />
        </Field>
        <Field label="Port">
          <NumberInput
            value={value.port}
            min={1}
            max={65535}
            onChange={(v) => onChange({ port: v })}
          />
        </Field>
      </div>
      <Field label="CORS origins" hint="one per line">
        <TextArea
          rows={3}
          value={(value.cors_origins || []).join("\n")}
          onChange={(v) =>
            onChange({
              cors_origins: v
                .split("\n")
                .map((s) => s.trim())
                .filter(Boolean),
            })
          }
        />
      </Field>
      <Field label="Request timeout" hint="seconds">
        <NumberInput
          value={value.request_timeout_seconds}
          min={1}
          max={600}
          onChange={(v) => onChange({ request_timeout_seconds: v })}
        />
      </Field>
    </>
  );
}

function DatabaseForm({ value, onChange }) {
  return (
    <>
      <Field label="Local DB path" hint="primary store, includes schema + individuals">
        <TextInput
          mono
          value={value.local_db_path}
          onChange={(v) => onChange({ local_db_path: v })}
        />
      </Field>
      <Field label="Operations DB path" hint="task ledger, audit trail">
        <TextInput
          mono
          value={value.operations_db_path}
          onChange={(v) => onChange({ operations_db_path: v })}
        />
      </Field>
      <div className="form-grid two">
        <Field label="Connection pool size">
          <NumberInput
            value={value.pool_size}
            min={1}
            max={64}
            onChange={(v) => onChange({ pool_size: v })}
          />
        </Field>
        <Field label="Statement timeout (ms)">
          <NumberInput
            value={value.statement_timeout_ms}
            min={100}
            max={60000}
            step={100}
            onChange={(v) => onChange({ statement_timeout_ms: v })}
          />
        </Field>
      </div>
    </>
  );
}

function LLMForm({ value, onChange, drafts, setDraft }) {
  const providers = [
    { value: "anthropic", label: "Anthropic" },
    { value: "openai", label: "OpenAI" },
  ];
  const models = {
    anthropic: [
      "claude-3-5-sonnet-20241022",
      "claude-3-5-haiku-20241022",
      "claude-opus-4-1-20250805",
    ],
    openai: ["gpt-4o", "gpt-4o-mini", "o1", "o1-mini"],
  };
  const opts = (models[value.default_provider] || []).map((m) => ({ value: m, label: m }));
  return (
    <>
      <CredentialField
        label="OpenAI API key"
        hint="masked: last 4 chars"
        masked={value.openai_api_key}
        draft={drafts.openai_api_key}
        onDraftChange={(v) => setDraft("openai_api_key", v)}
        onClear={() => setDraft("openai_api_key", undefined)}
      />
      <CredentialField
        label="Anthropic API key"
        hint="masked: last 4 chars"
        masked={value.anthropic_api_key}
        draft={drafts.anthropic_api_key}
        onDraftChange={(v) => setDraft("anthropic_api_key", v)}
        onClear={() => setDraft("anthropic_api_key", undefined)}
      />
      <div className="form-grid two">
        <Field label="Default provider">
          <Select
            value={value.default_provider}
            onChange={(v) => onChange({ default_provider: v })}
            options={providers}
          />
        </Field>
        <Field label="Default model">
          <Select
            value={value.default_model}
            onChange={(v) => onChange({ default_model: v })}
            options={opts}
          />
        </Field>
      </div>
      <Field label="Request timeout" hint="seconds — provider call timeout">
        <NumberInput
          value={value.request_timeout_seconds}
          min={5}
          max={300}
          onChange={(v) => onChange({ request_timeout_seconds: v })}
        />
      </Field>
    </>
  );
}

function NLPForm({ value, onChange }) {
  const models = [
    { value: "en_core_web_sm", label: "en_core_web_sm — small (12 MB)" },
    { value: "en_core_web_md", label: "en_core_web_md — medium (43 MB)" },
    { value: "en_core_web_lg", label: "en_core_web_lg — large (560 MB)" },
    { value: "en_core_web_trf", label: "en_core_web_trf — transformer (438 MB)" },
  ];
  return (
    <>
      <Field label="spaCy model">
        <Select
          value={value.model_name}
          onChange={(v) => onChange({ model_name: v })}
          options={models}
        />
      </Field>
      <div className="form-grid two">
        <Field label="Batch size" hint="docs per spaCy pipe call">
          <NumberInput
            value={value.batch_size}
            min={1}
            max={1024}
            onChange={(v) => onChange({ batch_size: v })}
          />
        </Field>
        <Field label="Pretrained NER" hint="ents from spaCy stats model">
          <ToggleField
            value={value.enable_pretrained_ner}
            onChange={(v) => onChange({ enable_pretrained_ner: v })}
          />
        </Field>
      </div>
    </>
  );
}

function EmbeddingForm({ value, onChange }) {
  const models = [
    "sentence-transformers/all-MiniLM-L6-v2",
    "sentence-transformers/all-mpnet-base-v2",
    "BAAI/bge-large-en-v1.5",
    "jinaai/jina-embeddings-v2-base-en",
  ].map((m) => ({ value: m, label: m }));
  const devices = ["cpu", "cuda:0", "cuda:1", "mps"].map((d) => ({ value: d, label: d }));
  return (
    <>
      <Field label="Embedding model">
        <Select
          value={value.model_name}
          onChange={(v) => onChange({ model_name: v })}
          options={models}
        />
      </Field>
      <div className="form-grid two">
        <Field label="Inference device">
          <Select
            value={value.device}
            onChange={(v) => onChange({ device: v })}
            options={devices}
          />
        </Field>
        <Field label="Batch size">
          <NumberInput
            value={value.batch_size}
            min={1}
            max={512}
            onChange={(v) => onChange({ batch_size: v })}
          />
        </Field>
      </div>
      <Field label="L2 normalise vectors" hint="enable for cosine similarity stores">
        <ToggleField value={value.normalize} onChange={(v) => onChange({ normalize: v })} />
      </Field>
    </>
  );
}

function ReferenceSourcesForm({ value, onChange }) {
  const allSources = [
    { id: "pubmed", label: "PubMed", domain: "life" },
    { id: "ncbi_gene", label: "NCBI Gene", domain: "life" },
    { id: "uniprot", label: "UniProt", domain: "life" },
    { id: "reactome", label: "Reactome", domain: "life" },
    { id: "arxiv", label: "arXiv (cs.SE)", domain: "software" },
    { id: "ipcc_ar6", label: "IPCC AR6 corpus", domain: "climate" },
    { id: "eia_energy", label: "EIA energy API", domain: "climate" },
  ];
  const enabled = new Set(value.enabled_sources || []);
  const limits = value.rate_limits || {};
  const toggle = (id) => {
    const next = new Set(enabled);
    next.has(id) ? next.delete(id) : next.add(id);
    onChange({ enabled_sources: Array.from(next) });
  };
  const setLimit = (id, n) => onChange({ rate_limits: { ...limits, [id]: n } });

  return (
    <>
      <div className="ref-source-list">
        {allSources.map((s) => {
          const on = enabled.has(s.id);
          return (
            <div key={s.id} className={"ref-source-row" + (on ? " on" : "")}>
              <button
                type="button"
                className={"src-toggle " + (on ? "on" : "off")}
                onClick={() => toggle(s.id)}
                aria-label={on ? "disable" : "enable"}
              >
                <span className="src-toggle-dot"></span>
              </button>
              <span className="kg-node" data-domain={s.domain} style={{ height: 24, fontSize: 12 }}>
                <span className="swatch"></span>
                {s.label}
              </span>
              <span className="src-id mono muted">{s.id}</span>
              <div className="src-limit">
                <span className="lim-label mono">rate</span>
                <input
                  type="number"
                  min={0}
                  max={1000}
                  className="input mono"
                  disabled={!on}
                  value={limits[s.id] ?? 0}
                  onChange={(e) => setLimit(s.id, Number(e.target.value))}
                />
                <span className="lim-suffix mono">req/s</span>
              </div>
            </div>
          );
        })}
      </div>
      <Field label="Cache TTL" hint="seconds — applies to all enabled sources">
        <NumberInput
          value={value.cache_ttl_seconds}
          min={0}
          max={2592000}
          step={60}
          onChange={(v) => onChange({ cache_ttl_seconds: v })}
        />
      </Field>
    </>
  );
}

function LoggingForm({ value, onChange }) {
  const levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"];
  return (
    <>
      <Field label="Level">
        <div className="seg">
          {levels.map((lv) => (
            <button
              key={lv}
              type="button"
              className={"seg-pill" + (value.level === lv ? " active" : "")}
              onClick={() => onChange({ level: lv })}
            >
              {lv}
            </button>
          ))}
        </div>
      </Field>
      <Field label="Log file path">
        <TextInput mono value={value.file_path} onChange={(v) => onChange({ file_path: v })} />
      </Field>
      <div className="form-grid two">
        <Field label="JSON output" hint="structured logs for ingestion">
          <ToggleField value={value.json_output} onChange={(v) => onChange({ json_output: v })} />
        </Field>
        <Field label="Max file size (MB)" hint="rotate at threshold">
          <NumberInput
            value={value.max_file_mb}
            min={1}
            max={10000}
            onChange={(v) => onChange({ max_file_mb: v })}
          />
        </Field>
      </div>
    </>
  );
}

function SyncForm({ value, onChange, drafts, setDraft, configured, onConfigure }) {
  if (!configured) {
    return (
      <div className="empty-section">
        <div className="empty-section-icon">
          <Icon name="ext" size={20} />
        </div>
        <div className="empty-section-title">Sync is not configured</div>
        <div className="empty-section-body">
          The <span className="mono">sync</span> section is optional. PATCH against it returns
          <span className="mono"> 400</span> until it is initialised. Configure it once and a
          nightly snapshot will be uploaded to your S3 bucket.
        </div>
        <button type="button" className="btn btn-primary btn-sm" onClick={onConfigure}>
          <Icon name="plus" size={12} /> Configure S3 sync
        </button>
      </div>
    );
  }
  return (
    <>
      <div className="form-grid two">
        <Field label="S3 bucket">
          <TextInput mono value={value.s3_bucket} onChange={(v) => onChange({ s3_bucket: v })} />
        </Field>
        <Field label="Region">
          <TextInput mono value={value.s3_region} onChange={(v) => onChange({ s3_region: v })} />
        </Field>
      </div>
      <CredentialField
        label="S3 access key"
        hint="masked: last 4 chars"
        masked={value.s3_access_key}
        draft={drafts.s3_access_key}
        onDraftChange={(v) => setDraft("s3_access_key", v)}
        onClear={() => setDraft("s3_access_key", undefined)}
      />
      <CredentialField
        label="S3 secret key"
        hint="masked: last 4 chars"
        masked={value.s3_secret_key}
        draft={drafts.s3_secret_key}
        onDraftChange={(v) => setDraft("s3_secret_key", v)}
        onClear={() => setDraft("s3_secret_key", undefined)}
      />
      <Field label="Schedule" hint="cron expression — UTC">
        <TextInput
          mono
          value={value.schedule_cron}
          onChange={(v) => onChange({ schedule_cron: v })}
        />
      </Field>
    </>
  );
}

function ToggleField({ value, onChange }) {
  return (
    <button
      type="button"
      className={"switch" + (value ? " on" : "")}
      onClick={() => onChange(!value)}
    >
      <span className="switch-knob"></span>
      <span className="switch-label mono">{value ? "on" : "off"}</span>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Section editor — the right pane for any editable section.
// Holds local drafts; flushes via onSave / onReset.
// ---------------------------------------------------------------------------

function SectionEditor({
  section,
  value,
  onSave,
  onResetSection,
  syncConfigured,
  onConfigureSync,
}) {
  const [draft, setDraft] = useState(value);
  const [credDrafts, setCredDrafts] = useState({});
  useEffect(() => {
    setDraft(value);
    setCredDrafts({});
  }, [section.id, value]);

  const dirty = useMemo(() => {
    if (JSON.stringify(draft) !== JSON.stringify(value)) return true;
    return Object.values(credDrafts).some((v) => v !== undefined);
  }, [draft, value, credDrafts]);

  const patch = (p) => setDraft({ ...draft, ...p });
  const setCred = (k, v) => setCredDrafts({ ...credDrafts, [k]: v });

  const handleSave = () => {
    // Build the payload: non-credential keys from draft diff + credential drafts that are non-empty
    const diff = {};
    for (const k of Object.keys(draft)) {
      if (CREDENTIAL_FIELD_NAMES.includes(k)) continue;
      if (JSON.stringify(draft[k]) !== JSON.stringify(value[k])) diff[k] = draft[k];
    }
    for (const k of CREDENTIAL_FIELD_NAMES) {
      const v = credDrafts[k];
      if (v !== undefined && v !== "") diff[k] = v; // empty string discards
    }
    onSave(diff);
  };

  const handleDiscard = () => {
    setDraft(value);
    setCredDrafts({});
  };

  const formProps = { value: draft, onChange: patch };
  let body;
  switch (section.id) {
    case "server":
      body = <ServerForm {...formProps} />;
      break;
    case "database":
      body = <DatabaseForm {...formProps} />;
      break;
    case "llm":
      body = <LLMForm {...formProps} drafts={credDrafts} setDraft={setCred} />;
      break;
    case "nlp":
      body = <NLPForm {...formProps} />;
      break;
    case "embedding":
      body = <EmbeddingForm {...formProps} />;
      break;
    case "reference_sources":
      body = <ReferenceSourcesForm {...formProps} />;
      break;
    case "logging":
      body = <LoggingForm {...formProps} />;
      break;
    case "sync":
      body = (
        <SyncForm
          {...formProps}
          drafts={credDrafts}
          setDraft={setCred}
          configured={syncConfigured}
          onConfigure={onConfigureSync}
        />
      );
      break;
    default:
      body = null;
  }

  return (
    <div className="cfg-pane">
      <div className="cfg-pane-head">
        <div>
          <div className="cfg-pane-title">
            <span className="cfg-pane-icon">
              <Icon name={section.icon} size={14} />
            </span>
            <span>{section.name}</span>
            {!syncConfigured && section.id === "sync" && <span className="chip gray">unset</span>}
          </div>
          <div className="cfg-pane-sub">{section.desc}</div>
        </div>
        <div className="cfg-pane-endpoints">
          <EndpointPill method="PATCH" path={`/api/v1/admin/configuration/${section.id}`} />
        </div>
      </div>

      <div className="cfg-pane-body">{body}</div>

      <div className="cfg-pane-foot">
        <button type="button" className="btn btn-ghost btn-sm" onClick={onResetSection}>
          <Icon name="refresh" size={12} /> Reset section
        </button>
        <span className="grow"></span>
        {dirty && (
          <span className="dirty-flag mono">
            <span className="dot"></span>unsaved changes
          </span>
        )}
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          disabled={!dirty}
          onClick={handleDiscard}
        >
          Discard
        </button>
        <button
          type="button"
          className="btn btn-primary btn-sm"
          disabled={!dirty}
          onClick={handleSave}
        >
          Save changes
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Health overview — banner + component grid + issues list
// ---------------------------------------------------------------------------

function HealthOverview({ health, tasks, onRefresh, onJump }) {
  const taskCounts = useMemo(() => {
    const c = { pending: 0, running: 0, completed: 0, failed: 0 };
    tasks.forEach((t) => {
      c[t.status] += 1;
    });
    return c;
  }, [tasks]);

  return (
    <>
      <div className={"health-banner banner-" + health.status}>
        <div className="health-banner-l">
          <div className="health-banner-icon">
            <span className={"pulse-ring tone-" + health.status}></span>
            <Icon
              name={
                health.status === "healthy" ? "check" : health.status === "degraded" ? "alert" : "x"
              }
              size={20}
            />
          </div>
          <div>
            <div className="health-banner-status">
              <StatusBadge status={health.status} />
              <span className="health-banner-up mono">
                uptime {fmtUptime(health.uptime_seconds)}
              </span>
              <span className="health-banner-checked mono muted">
                checked {fmtRelative(health.checked_at)}
              </span>
            </div>
            <div className="health-banner-title">
              {health.status === "healthy" && "All components are operating normally."}
              {health.status === "degraded" &&
                `${health.issues.length} ${health.issues.length === 1 ? "issue" : "issues"} — service is up but functionality is reduced.`}
              {health.status === "unhealthy" && "Database is unreachable. Nothing can function."}
            </div>
          </div>
        </div>
        <div className="health-banner-r">
          <EndpointPill method="GET" path="/api/v1/admin/health" />
          <button type="button" className="btn btn-ghost btn-sm" onClick={onRefresh}>
            <Icon name="refresh" size={12} /> Re-check
          </button>
        </div>
      </div>

      <div className="health-grid">
        <ComponentCheck
          icon="database"
          label="Database"
          ok={health.database_connected}
          detail={health.database_connected ? "connected · pool 8/8 healthy" : "connection refused"}
          endpoint="GET /health/database"
        />
        <ComponentCheck
          icon="sparkle"
          label="NLP pipeline"
          ok={health.nlp_pipeline_ready}
          detail={
            health.nlp_pipeline_ready
              ? "spaCy model 'en_core_web_sm' loaded"
              : "pipeline not initialised"
          }
          endpoint="GET /health/nlp"
        />
        <ComponentCheck
          icon="layers"
          label="Embedding model"
          ok={health.embedding_model_loaded}
          detail={health.embedding_model_loaded ? "all-MiniLM-L6-v2 on cuda:0" : "not loaded"}
          endpoint="GET /health/embedding"
        />
        <ComponentCheck
          icon="brain"
          label="LLM providers"
          ok={health.llm_providers_available.length > 0}
          detail={
            health.llm_providers_available.length > 0
              ? health.llm_providers_available.join(" · ") + " configured"
              : "no providers configured"
          }
          endpoint="GET /health/services"
        />
        <ComponentCheck
          icon="workflow"
          label="Background tasks"
          ok={taskCounts.failed === 0}
          tone={taskCounts.failed > 0 ? "warn" : ""}
          detail={
            <span className="task-mini">
              <span className="t-mini pending">{taskCounts.pending} pending</span>
              <span className="t-mini running">{taskCounts.running} running</span>
              <span className="t-mini completed">{taskCounts.completed} completed</span>
              <span className="t-mini failed">{taskCounts.failed} failed</span>
            </span>
          }
          endpoint="GET /health/tasks"
        />
      </div>

      {health.issues.length > 0 && (
        <div className="issues-panel">
          <div className="issues-head">
            <Icon name="alert" size={13} />
            <span>
              {health.issues.length} active {health.issues.length === 1 ? "issue" : "issues"}
            </span>
            <span className="muted mono" style={{ fontSize: 11 }}>
              safe to surface · from <code>SystemHealthResponse.issues</code>
            </span>
          </div>
          <ul className="issues-list">
            {health.issues.map((iss, i) => (
              <li key={i} className="issue-row">
                <span className="issue-bullet">!</span>
                <span className="issue-text">{iss}</span>
                {/^reference_source/.test(iss) && (
                  <button className="issue-jump" onClick={() => onJump("reference_sources")}>
                    Open Reference sources <Icon name="arrow" size={11} />
                  </button>
                )}
                {/background task/.test(iss) && (
                  <button className="issue-jump" onClick={() => onJump("tasks")}>
                    Open Tasks <Icon name="arrow" size={11} />
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Background tasks — list + state-machine indicator + drawer
// ---------------------------------------------------------------------------

const TASK_STATES = ["pending", "running", "completed", "failed"];

function TaskStateLine({ status }) {
  // The legal state machine, visualised as a small flow strip.
  // pending → running → completed
  //                  ↘ failed
  // pending may skip directly to completed or failed.
  const reached = (s) => {
    if (s === "pending") return true;
    if (status === "pending") return false;
    if (s === "running") return status === "running";
    if (s === "completed") return status === "completed";
    if (s === "failed") return status === "failed";
    return false;
  };
  return (
    <div className="task-state-line">
      {TASK_STATES.map((s, i) => (
        <React.Fragment key={s}>
          <span
            className={
              "tsl-node " + s + (reached(s) ? " reached" : "") + (status === s ? " current" : "")
            }
          >
            <span className="dot"></span>
            <span className="lbl">{s}</span>
          </span>
          {i < TASK_STATES.length - 1 && (
            <span
              className={
                "tsl-edge " +
                (status === "failed" && s === "running" ? "fork-down" : "") +
                (reached(TASK_STATES[i + 1]) ? " reached" : "")
              }
            ></span>
          )}
        </React.Fragment>
      ))}
    </div>
  );
}

function TaskDetailDrawer({ task, onClose }) {
  if (!task) return null;
  return (
    <div className="task-drawer">
      <div className="task-drawer-head">
        <div>
          <div className="task-drawer-title">{task.name}</div>
          <div className="task-drawer-id mono">{task.id}</div>
        </div>
        <button className="modal-x" onClick={onClose}>
          <Icon name="x" size={14} />
        </button>
      </div>
      <div className="task-drawer-body">
        <div className="task-drawer-row">
          <div className="td-label mono">status</div>
          <div className="td-val">
            <span className={"task-status-pill " + task.status}>
              <span className="dot"></span>
              {task.status}
            </span>
          </div>
        </div>
        <div className="task-drawer-row">
          <div className="td-label mono">state machine</div>
          <div className="td-val">
            <TaskStateLine status={task.status} />
          </div>
        </div>
        <div className="task-drawer-row">
          <div className="td-label mono">created_at</div>
          <div className="td-val mono">
            {task.created_at} <span className="muted">· {fmtRelative(task.created_at)}</span>
          </div>
        </div>
        <div className="task-drawer-row">
          <div className="td-label mono">started_at</div>
          <div className="td-val mono">
            {task.started_at || <span className="muted">null</span>}
          </div>
        </div>
        <div className="task-drawer-row">
          <div className="td-label mono">completed_at</div>
          <div className="td-val mono">
            {task.completed_at || <span className="muted">null</span>}
          </div>
        </div>
        <div className="task-drawer-row">
          <div className="td-label mono">duration</div>
          <div className="td-val mono">{fmtDuration(task.started_at, task.completed_at)}</div>
        </div>
        {task.error && (
          <div className="task-drawer-row">
            <div className="td-label mono">error</div>
            <div className="td-val">
              <pre className="task-pre err">{task.error}</pre>
            </div>
          </div>
        )}
        {task.result && (
          <div className="task-drawer-row">
            <div className="td-label mono">result</div>
            <div className="td-val">
              <pre className="task-pre">{JSON.stringify(task.result, null, 2)}</pre>
            </div>
          </div>
        )}
      </div>
      <div className="task-drawer-foot">
        <EndpointPill method="GET" path={`/api/v1/admin/tasks/${task.id}`} />
      </div>
    </div>
  );
}

function TasksPane({ tasks }) {
  const [filter, setFilter] = useState("all");
  const [picked, setPicked] = useState(null);
  const counts = useMemo(() => {
    const c = { all: tasks.length, pending: 0, running: 0, completed: 0, failed: 0 };
    tasks.forEach((t) => {
      c[t.status] += 1;
    });
    return c;
  }, [tasks]);
  const list = filter === "all" ? tasks : tasks.filter((t) => t.status === filter);

  return (
    <div className="cfg-pane">
      <div className="cfg-pane-head">
        <div>
          <div className="cfg-pane-title">
            <span className="cfg-pane-icon">
              <Icon name="workflow" size={14} />
            </span>
            <span>Background tasks</span>
            <span className="chip gray">in-memory</span>
          </div>
          <div className="cfg-pane-sub">
            Tasks live for the lifetime of the server process — they are not persisted and are lost
            on restart. Created server-side by long-running operations; there is no API to start or
            cancel from the client.
          </div>
        </div>
        <div className="cfg-pane-endpoints">
          <EndpointPill method="GET" path="/api/v1/admin/tasks" />
        </div>
      </div>

      <div className="task-tabs">
        {["all", "pending", "running", "completed", "failed"].map((f) => (
          <button
            key={f}
            className={"task-tab" + (filter === f ? " active" : "")}
            onClick={() => setFilter(f)}
          >
            <span className={"task-tab-dot " + f}></span>
            <span className="task-tab-name">{f}</span>
            <span className="task-tab-count mono">{counts[f]}</span>
          </button>
        ))}
      </div>

      <div className="task-list-wrap">
        <table className="t task-table">
          <thead>
            <tr>
              <th>Task</th>
              <th>State</th>
              <th>Created</th>
              <th>Duration</th>
              <th>Result / Error</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {list.map((t) => (
              <tr
                key={t.id}
                className={picked?.id === t.id ? "picked" : ""}
                onClick={() => setPicked(t)}
              >
                <td>
                  <div className="task-name">{t.name}</div>
                  <div className="task-id mono">
                    {t.id.slice(0, 8)}…{t.id.slice(-4)}
                  </div>
                </td>
                <td>
                  <span className={"task-status-pill " + t.status}>
                    <span className="dot"></span>
                    {t.status}
                  </span>
                </td>
                <td className="mono muted" style={{ fontSize: 11.5 }}>
                  {fmtRelative(t.created_at)}
                </td>
                <td className="mono" style={{ fontSize: 12 }}>
                  {fmtDuration(t.started_at, t.completed_at)}
                </td>
                <td>
                  {t.error && <span className="task-cell-err mono">{t.error}</span>}
                  {t.result && (
                    <span className="task-cell-ok mono">
                      {Object.entries(t.result)
                        .slice(0, 2)
                        .map(([k, v]) => `${k}=${v}`)
                        .join(" · ")}
                    </span>
                  )}
                  {!t.error && !t.result && (
                    <span className="muted mono" style={{ fontSize: 11.5 }}>
                      —
                    </span>
                  )}
                </td>
                <td className="row-actions">
                  <Icon name="arrow" size={12} />
                </td>
              </tr>
            ))}
            {list.length === 0 && (
              <tr>
                <td
                  colSpan={6}
                  style={{ padding: "24px", textAlign: "center", color: "var(--canvas-fg-3)" }}
                >
                  No tasks in this state.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <TaskDetailDrawer task={picked} onClose={() => setPicked(null)} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Danger zone — full reset
// ---------------------------------------------------------------------------

function DangerPane({ onReset }) {
  const [confirm, setConfirm] = useState(false);
  return (
    <div className="cfg-pane">
      <div className="cfg-pane-head">
        <div>
          <div className="cfg-pane-title danger">
            <span className="cfg-pane-icon danger">
              <Icon name="alert" size={14} />
            </span>
            <span>Reset to defaults</span>
          </div>
          <div className="cfg-pane-sub">
            Resets every non-credential value across all sections to factory defaults. The four
            credential fields
            <span className="mono"> openai_api_key</span>,{" "}
            <span className="mono">anthropic_api_key</span>,
            <span className="mono"> s3_access_key</span>,{" "}
            <span className="mono">s3_secret_key</span> are preserved.
          </div>
        </div>
        <div className="cfg-pane-endpoints">
          <EndpointPill method="POST" path="/api/v1/admin/configuration/reset" />
        </div>
      </div>
      <div className="cfg-pane-body">
        <div className="danger-card">
          <div className="danger-card-icon">
            <Icon name="alert" size={18} />
          </div>
          <div className="danger-card-body">
            <div className="danger-card-title">This action affects every section.</div>
            <div className="danger-card-desc">
              Server, database paths, NLP/embedding models, reference-source toggles, logging, and
              sync schedule will all snap back to defaults. Active background tasks are unaffected.
              Credentials are preserved.
            </div>
            <button
              type="button"
              className="btn btn-danger btn-sm"
              onClick={() => setConfirm(true)}
            >
              <Icon name="refresh" size={12} /> Reset all sections
            </button>
          </div>
        </div>
      </div>

      <ConfirmModal
        open={confirm}
        onClose={() => setConfirm(false)}
        onConfirm={() => {
          setConfirm(false);
          onReset();
        }}
        title="Reset all sections to defaults?"
        confirmLabel="Reset configuration"
        body={
          <>
            Eight sections will be rewritten in a single operation. Credentials are preserved.
            Returns the full reset configuration with masked credentials on success.
          </>
        }
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

function SettingsPage() {
  const toast = window.useToast ? window.useToast() : { pushToast: () => {} };
  const [active, setActive] = useState("overview");
  const [health, setHealth] = useState(INITIAL_HEALTH);
  const [config, setConfig] = useState(INITIAL_CONFIG);
  const [tasks, setTasks] = useState(INITIAL_TASKS);
  const [syncConfigured, setSyncConfigured] = useState(true);

  const refreshHealth = () => {
    setHealth({ ...health, checked_at: new Date().toISOString() });
    toast.pushToast?.({
      kind: "success",
      title: "Health re-checked",
      body: "GET /health · all components polled.",
    });
  };

  const savePatch = (sectionId, patch) => {
    setConfig({ ...config, [sectionId]: { ...config[sectionId], ...maskCredentials(patch) } });
    const keys = Object.keys(patch);
    toast.pushToast?.({
      kind: "success",
      title: `Updated ${SECTIONS.find((s) => s.id === sectionId).name}`,
      body: `PATCH /configuration/${sectionId} · ${keys.length} ${keys.length === 1 ? "key" : "keys"} merged.`,
    });
  };

  const resetSection = (sectionId) => {
    setConfig({ ...config, [sectionId]: { ...INITIAL_CONFIG[sectionId] } });
    toast.pushToast?.({
      kind: "success",
      title: "Section reset",
      body: `${SECTIONS.find((s) => s.id === sectionId).name} restored to defaults.`,
    });
  };

  const resetAll = () => {
    // Preserve credentials per the spec
    const next = {};
    for (const k of Object.keys(INITIAL_CONFIG)) {
      next[k] = { ...INITIAL_CONFIG[k] };
      for (const c of CREDENTIAL_FIELD_NAMES) if (c in (config[k] || {})) next[k][c] = config[k][c];
    }
    setConfig(next);
    toast.pushToast?.({
      kind: "success",
      title: "Configuration reset",
      body: "All non-credential values restored. Credentials preserved.",
    });
    setActive("overview");
  };

  const configureSync = () => {
    setSyncConfigured(true);
    toast.pushToast?.({
      kind: "success",
      title: "Sync initialised",
      body: "PATCH /configuration/sync is now valid.",
    });
  };

  // Keep credential masking consistent: any new value goes in masked
  function maskCredentials(patch) {
    const out = { ...patch };
    for (const k of CREDENTIAL_FIELD_NAMES) {
      if (k in out && out[k] && !out[k].startsWith("***")) {
        const v = String(out[k]);
        out[k] = v.length >= 4 ? "***" + v.slice(-4) : "***";
      }
    }
    return out;
  }

  const taskCounts = useMemo(() => {
    const c = { pending: 0, running: 0, completed: 0, failed: 0 };
    tasks.forEach((t) => {
      c[t.status] += 1;
    });
    return c;
  }, [tasks]);

  const activeSection = SECTIONS.find((s) => s.id === active);

  return (
    <div className="canvas-inner cfg-canvas">
      <div className="page-head">
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
            <span className="chip cyan">
              <span className="dot"></span>workspace · default
            </span>
            <StatusBadge status={health.status} />
          </div>
          <h1>
            Configuration <span className="id-tag">/api/v1/admin</span>
          </h1>
          <div className="subtitle">
            System health, eight configuration sections, and the in-memory background-task queue.
          </div>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost">
            <Icon name="ext" /> Export config
          </button>
          <button className="btn btn-ghost" onClick={refreshHealth}>
            <Icon name="refresh" /> Re-check health
          </button>
        </div>
      </div>

      <div className="cfg-layout">
        {/* Left rail */}
        <aside className="cfg-rail">
          <div className="cfg-rail-section">
            {NAV.map((n) => {
              if (n.kind === "sep") return <div key={n.id} className="cfg-rail-sep"></div>;
              const isActive = active === n.id;
              return (
                <button
                  key={n.id}
                  className={
                    "cfg-rail-item" +
                    (isActive ? " active" : "") +
                    (n.tone === "danger" ? " danger" : "")
                  }
                  onClick={() => setActive(n.id)}
                >
                  <span className="cfg-rail-ic">
                    <Icon name={n.icon} size={14} />
                  </span>
                  <span className="cfg-rail-name">{n.name}</span>
                  {n.id === "tasks" && (
                    <span className={"cfg-rail-count " + (taskCounts.failed > 0 ? "bad" : "ok")}>
                      {tasks.length}
                    </span>
                  )}
                  {n.id === "overview" && health.status !== "healthy" && (
                    <span className={"cfg-rail-dot " + health.status}></span>
                  )}
                  {n.id === "sync" && !syncConfigured && (
                    <span className="cfg-rail-tag mono">unset</span>
                  )}
                </button>
              );
            })}
          </div>
        </aside>

        {/* Right pane */}
        <div className="cfg-content">
          {active === "overview" && (
            <HealthOverview
              health={health}
              tasks={tasks}
              onRefresh={refreshHealth}
              onJump={(t) => setActive(t)}
            />
          )}
          {active === "tasks" && <TasksPane tasks={tasks} />}
          {active === "danger" && <DangerPane onReset={resetAll} />}
          {activeSection && (
            <SectionEditor
              section={activeSection}
              value={config[activeSection.id]}
              onSave={(patch) => savePatch(activeSection.id, patch)}
              onResetSection={() => resetSection(activeSection.id)}
              syncConfigured={activeSection.id === "sync" ? syncConfigured : true}
              onConfigureSync={configureSync}
            />
          )}
        </div>
      </div>
    </div>
  );
}

window.SettingsPage = SettingsPage;
