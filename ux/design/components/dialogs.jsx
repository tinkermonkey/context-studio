// CRUD dialogs — Taxonomy, ConceptScheme, Class, PropertyDefinition, Relationship.
// Each dialog handles both create and edit modes.

const DOMAIN_OPTIONS = [
  { value: "life", label: "Life sciences" },
  { value: "climate", label: "Climate" },
  { value: "software", label: "Software" },
  { value: "default", label: "Other" },
];

// ============= Taxonomy =============
function TaxonomyDialog({ open, onClose, initial }) {
  const { actions } = window.useStore();
  const editing = !!initial;
  const [form, setForm] = useState({});
  useEffect(() => {
    if (open) setForm(initial ? { ...initial } : { title: "", description: "", domain: "default" });
  }, [open, initial?.id]);

  const submit = () => {
    try {
      if (editing)
        actions.updateTaxonomy(initial.id, {
          title: form.title,
          description: form.description,
          domain: form.domain,
        });
      else
        actions.createTaxonomy({
          title: form.title,
          description: form.description,
          domain: form.domain,
        });
      onClose();
    } catch {}
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={editing ? "Edit taxonomy" : "New taxonomy"}
      subtitle="Top-level domain. Concept schemes, classes, individuals all live within."
      headerAccessory={editing && <span className="version-pill">v{initial.version}</span>}
      footer={
        <>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary btn-sm" onClick={submit}>
            {editing ? "Save changes" : "Create taxonomy"}
          </button>
        </>
      }
    >
      <Field label="Title" required>
        <TextInput
          value={form.title}
          onChange={(v) => setForm({ ...form, title: v })}
          placeholder="e.g. Life Sciences"
          autoFocus
        />
      </Field>
      <Field label="Description">
        <TextArea
          value={form.description}
          onChange={(v) => setForm({ ...form, description: v })}
          placeholder="What this taxonomy organises"
        />
      </Field>
      <Field label="Domain" hint="Used for color coding only">
        <Select
          value={form.domain}
          onChange={(v) => setForm({ ...form, domain: v })}
          options={DOMAIN_OPTIONS}
        />
      </Field>
    </Modal>
  );
}

// ============= ConceptScheme =============
function ConceptSchemeDialog({ open, onClose, initial, defaultTaxonomyId }) {
  const { state, actions } = window.useStore();
  const editing = !!initial;
  const [form, setForm] = useState({});
  useEffect(() => {
    if (open)
      setForm(
        initial
          ? { ...initial }
          : {
              title: "",
              description: "",
              taxonomy_id: defaultTaxonomyId || state.taxonomies[0]?.id,
            },
      );
  }, [open, initial?.id, defaultTaxonomyId]);

  const submit = () => {
    try {
      if (editing)
        actions.updateScheme(initial.id, { title: form.title, description: form.description });
      else
        actions.createScheme({
          title: form.title,
          description: form.description,
          taxonomy_id: form.taxonomy_id,
        });
      onClose();
    } catch {}
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={editing ? "Edit concept scheme" : "New concept scheme"}
      subtitle="Concept schemes group related classes within a taxonomy."
      headerAccessory={editing && <span className="version-pill">v{initial.version}</span>}
      footer={
        <>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary btn-sm" onClick={submit}>
            {editing ? "Save changes" : "Create scheme"}
          </button>
        </>
      }
    >
      <Field label="Title" required>
        <TextInput
          value={form.title}
          onChange={(v) => setForm({ ...form, title: v })}
          placeholder="e.g. Cellular Biology"
          autoFocus
        />
      </Field>
      <Field label="Description">
        <TextArea value={form.description} onChange={(v) => setForm({ ...form, description: v })} />
      </Field>
      <Field
        label="Taxonomy"
        required
        hint={editing ? "Cannot be changed after creation" : "Required at creation"}
      >
        <Select
          value={form.taxonomy_id}
          onChange={(v) => setForm({ ...form, taxonomy_id: v })}
          options={state.taxonomies.map((t) => ({ value: t.id, label: t.title }))}
        />
      </Field>
      {editing && (
        <div className="form-callout">
          <Icon name="link" size={12} />
          <span>
            To move classes between schemes, use <em>Move</em> on the class itself — only schemes
            within the same taxonomy are valid targets.
          </span>
        </div>
      )}
    </Modal>
  );
}

// ============= Class =============
const XSD_TYPES = [
  "xsd:string",
  "xsd:integer",
  "xsd:decimal",
  "xsd:boolean",
  "xsd:date",
  "xsd:dateTime",
  "xsd:gYear",
  "xsd:anyURI",
];

function ClassDialog({ open, onClose, initial, defaultSchemeId }) {
  const { state, actions } = window.useStore();
  const editing = !!initial;
  const [tab, setTab] = useState("basic");
  const [form, setForm] = useState({});

  useEffect(() => {
    if (!open) return;
    setTab("basic");
    setForm(
      initial
        ? {
            ...initial,
            external_references: initial.external_references || [],
            lexical_senses: initial.lexical_senses || [],
            data_properties: initial.data_properties || [],
          }
        : {
            title: "",
            description: "",
            concept_scheme_id: defaultSchemeId || state.concept_schemes[0]?.id,
            parent_class_id: null,
            structural_property_id: null,
            external_references: [],
            lexical_senses: [],
            data_properties: [],
          },
    );
  }, [open, initial?.id, defaultSchemeId]);

  const scheme = state.concept_schemes.find((s) => s.id === form.concept_scheme_id);
  const parentCandidates = state.classes.filter(
    (c) => c.concept_scheme_id === form.concept_scheme_id && c.id !== form.id,
  );

  const submit = () => {
    try {
      if (editing) {
        actions.updateClass(initial.id, {
          title: form.title,
          description: form.description,
          parent_class_id: form.parent_class_id,
          structural_property_id: form.structural_property_id,
          external_references: form.external_references,
          lexical_senses: form.lexical_senses,
          data_properties: form.data_properties,
        });
      } else {
        actions.createClass({
          title: form.title,
          description: form.description,
          concept_scheme_id: form.concept_scheme_id,
          parent_class_id: form.parent_class_id,
          structural_property_id: form.structural_property_id,
          external_references: form.external_references,
          lexical_senses: form.lexical_senses,
          data_properties: form.data_properties,
        });
      }
      onClose();
    } catch {}
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      title={
        editing ? (
          <>
            Edit class <span className="modal-id mono">{initial.id}</span>
          </>
        ) : (
          "New class"
        )
      }
      subtitle="Classes are the structural backbone — they define what an Individual can be."
      headerAccessory={editing && <span className="version-pill">v{initial.version}</span>}
      footer={
        <>
          <span className="modal-foot-hint mono">
            {editing ? "Updating bumps version" : "Will create a new class node"}
          </span>
          <span style={{ flex: 1 }}></span>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary btn-sm" onClick={submit}>
            {editing ? "Save changes" : "Create class"}
          </button>
        </>
      }
    >
      <div className="modal-tabs">
        {[
          ["basic", "Basic"],
          ["hierarchy", "Hierarchy"],
          ["lexical", "Lexical · " + (form.lexical_senses?.length || 0)],
          ["external", "External refs · " + (form.external_references?.length || 0)],
          ["data", "Data properties · " + (form.data_properties?.length || 0)],
        ].map(([id, label]) => (
          <button
            key={id}
            className={"modal-tab" + (tab === id ? " active" : "")}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "basic" && (
        <>
          <Field label="Title" required>
            <TextInput
              value={form.title}
              onChange={(v) => setForm({ ...form, title: v })}
              placeholder="e.g. Mitochondrion"
              autoFocus
            />
          </Field>
          <Field label="Description">
            <TextArea
              value={form.description}
              onChange={(v) => setForm({ ...form, description: v })}
              placeholder="A definition useful for retrieval"
              rows={4}
            />
          </Field>
          <Field
            label="Structural property"
            hint="The primary relationship type that organises children of this class"
          >
            <Select
              value={form.structural_property_id || ""}
              onChange={(v) => setForm({ ...form, structural_property_id: v || null })}
              options={[
                { value: "", label: "— none —" },
                ...state.property_definitions.map((p) => ({
                  value: p.id,
                  label: p.title + " (" + p.identifier + ")",
                })),
              ]}
            />
          </Field>
        </>
      )}

      {tab === "hierarchy" && (
        <>
          <Field
            label="Concept scheme"
            required
            hint={editing ? "Use Move to change" : "Required at creation"}
          >
            {editing ? (
              <div className="readonly-display">
                <span className="kg-node" data-domain={scheme?.domain}>
                  <span className="swatch"></span>
                  {scheme?.title}
                </span>
              </div>
            ) : (
              <Select
                value={form.concept_scheme_id}
                onChange={(v) => setForm({ ...form, concept_scheme_id: v, parent_class_id: null })}
                options={state.concept_schemes.map((s) => {
                  const t = state.taxonomies.find((x) => x.id === s.taxonomy_id);
                  return { value: s.id, label: (t?.title || "?") + " / " + s.title };
                })}
              />
            )}
          </Field>
          <Field label="Parent class" hint="Forms a tree within this concept scheme">
            <Select
              value={form.parent_class_id || ""}
              onChange={(v) => setForm({ ...form, parent_class_id: v || null })}
              options={[
                { value: "", label: "— root level —" },
                ...parentCandidates.map((c) => ({ value: c.id, label: c.title })),
              ]}
            />
          </Field>
          <div className="form-callout">
            <Icon name="schema" size={12} />
            <span>
              Cross-taxonomy moves are not allowed. To move this class to a different scheme, use
              the <em>Move</em> action on the class card.
            </span>
          </div>
        </>
      )}

      {tab === "lexical" && (
        <Field label="Lexical senses" hint="Word-sense disambiguation entries">
          <LexicalListEditor
            rows={form.lexical_senses}
            onChange={(v) => setForm({ ...form, lexical_senses: v })}
          />
        </Field>
      )}

      {tab === "external" && (
        <Field label="External references" hint="Links to DBpedia, Wikidata, ConceptNet, etc.">
          <RefListEditor
            rows={form.external_references}
            onChange={(v) => setForm({ ...form, external_references: v })}
          />
        </Field>
      )}

      {tab === "data" && (
        <Field label="Data properties" hint="Key-value attributes with optional XSD datatype">
          <KeyValueListEditor
            rows={form.data_properties}
            onChange={(v) => setForm({ ...form, data_properties: v })}
            datatypes={XSD_TYPES}
          />
        </Field>
      )}
    </Modal>
  );
}

// ============= Move Class =============
function MoveClassDialog({ open, onClose, cls }) {
  const { state, actions } = window.useStore();
  const [target, setTarget] = useState(null);
  useEffect(() => {
    if (open) setTarget(null);
  }, [open, cls?.id]);
  if (!cls) return null;

  // Only schemes in the same taxonomy are valid targets
  const candidates = state.concept_schemes.filter(
    (s) => s.taxonomy_id === cls.taxonomy_id && s.id !== cls.concept_scheme_id,
  );
  const taxonomy = state.taxonomies.find((t) => t.id === cls.taxonomy_id);
  const blocked = state.concept_schemes.filter((s) => s.taxonomy_id !== cls.taxonomy_id);

  const submit = () => {
    if (!target) return;
    try {
      actions.moveClass(cls.id, target);
      onClose();
    } catch {}
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="md"
      title={
        <>
          Move <em>{cls.title}</em>
        </>
      }
      subtitle="Reparent this class to another concept scheme. Children move with it."
      footer={
        <>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary btn-sm" disabled={!target} onClick={submit}>
            Move class
          </button>
        </>
      }
    >
      <div className="form-callout">
        <Icon name="shield" size={12} />
        <span>
          Move requests only accept <code>target_scheme_id</code>. Cross-taxonomy moves return{" "}
          <code>400</code> from the API.
        </span>
      </div>
      <Field label="Current location">
        <div className="readonly-display">
          <span className="mono muted">{taxonomy?.title}</span>{" "}
          <span className="mono" style={{ opacity: 0.4 }}>
            ›
          </span>
          <span className="kg-node" data-domain={cls.domain}>
            <span className="swatch"></span>
            {state.concept_schemes.find((s) => s.id === cls.concept_scheme_id)?.title}
          </span>
        </div>
      </Field>
      <Field label="Move to" required hint={"Schemes within " + (taxonomy?.title || "?")}>
        <div className="scheme-radio-list">
          {candidates.length === 0 && (
            <div className="kvle-empty">No other schemes in this taxonomy.</div>
          )}
          {candidates.map((s) => (
            <label key={s.id} className={"scheme-radio" + (target === s.id ? " selected" : "")}>
              <input
                type="radio"
                name="moveTarget"
                value={s.id}
                checked={target === s.id}
                onChange={() => setTarget(s.id)}
              />
              <div className="scheme-radio-main">
                <div className="scheme-radio-title">{s.title}</div>
                <div className="scheme-radio-sub">{s.description}</div>
              </div>
              <span className="mono muted">
                {state.classes.filter((c) => c.concept_scheme_id === s.id).length} classes
              </span>
            </label>
          ))}
        </div>
      </Field>
      {blocked.length > 0 && (
        <details className="blocked-section">
          <summary>{blocked.length} schemes blocked (different taxonomies)</summary>
          <div className="blocked-list">
            {blocked.map((s) => {
              const t = state.taxonomies.find((x) => x.id === s.taxonomy_id);
              return (
                <div key={s.id} className="blocked-row">
                  <span className="mono muted">{t?.title}</span> / {s.title}
                  <span className="chip rose" style={{ marginLeft: "auto" }}>
                    400
                  </span>
                </div>
              );
            })}
          </div>
        </details>
      )}
    </Modal>
  );
}

// ============= Property Definition =============
function PropertyDialog({ open, onClose, initial }) {
  const { actions } = window.useStore();
  const editing = !!initial;
  const [form, setForm] = useState({});
  useEffect(() => {
    if (open)
      setForm(
        initial
          ? { ...initial }
          : { identifier: "", title: "", description: "", is_relevant: null },
      );
  }, [open, initial?.id]);

  const submit = () => {
    try {
      if (editing)
        actions.updatePropertyDefinition(initial.id, {
          title: form.title,
          description: form.description,
          is_relevant: form.is_relevant,
        });
      else
        actions.createPropertyDefinition({
          identifier: form.identifier,
          title: form.title || form.identifier,
          description: form.description,
          is_relevant: form.is_relevant,
        });
      onClose();
    } catch {}
  };

  // Auto-derive identifier from title while creating
  const onTitle = (v) => {
    if (!editing && (!form.identifier || form.identifier === window.snakeify(form.title))) {
      setForm({ ...form, title: v, identifier: window.snakeify(v) });
    } else {
      setForm({ ...form, title: v });
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={editing ? "Edit property" : "New property definition"}
      subtitle="Properties name the relationships between schema or data nodes."
      headerAccessory={editing && <span className="version-pill">v{initial.version}</span>}
      footer={
        <>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary btn-sm" onClick={submit}>
            {editing ? "Save changes" : "Create property"}
          </button>
        </>
      }
    >
      <Field label="Title" hint="Human display name" required>
        <TextInput value={form.title} onChange={onTitle} placeholder="e.g. Has Part" autoFocus />
      </Field>
      <Field
        label="Identifier"
        required
        mono
        hint={editing ? "Immutable after creation" : "Machine-readable, snake_case"}
      >
        {editing ? (
          <div className="readonly-display mono">{form.identifier}</div>
        ) : (
          <TextInput
            value={form.identifier}
            onChange={(v) => setForm({ ...form, identifier: window.snakeify(v) })}
            placeholder="has_part"
            mono
          />
        )}
      </Field>
      <Field label="Description">
        <TextArea value={form.description} onChange={(v) => setForm({ ...form, description: v })} />
      </Field>
      <Field label="Relevance" hint="Tri-state — null, relevant, irrelevant">
        <TriState value={form.is_relevant} onChange={(v) => setForm({ ...form, is_relevant: v })} />
      </Field>
    </Modal>
  );
}

// ============= Relationship =============
function RelationshipDialog({ open, onClose, prefill }) {
  const { state, actions } = window.useStore();
  const [form, setForm] = useState({});
  const [autoMode, setAutoMode] = useState(false); // false = pick existing, true = type a new identifier

  useEffect(() => {
    if (!open) return;
    setForm({
      source_id: prefill?.source_id || null,
      target_id: prefill?.target_id || null,
      property_definition_id:
        prefill?.property_definition_id || state.property_definitions[0]?.id || null,
      relationship_type: "",
      source: "manual",
      confidence: 1.0,
    });
    setAutoMode(false);
  }, [open, prefill?.source_id, prefill?.target_id]);

  // Real-time validation
  const issues = [];
  if (form.source_id && form.target_id && form.source_id === form.target_id)
    issues.push({ code: "400", text: "Self-loops are not allowed (source_id == target_id)" });
  const propId = !autoMode ? form.property_definition_id : null;
  if (form.source_id && form.target_id && propId) {
    const dup = state.relationships.find(
      (r) =>
        r.source_id === form.source_id &&
        r.target_id === form.target_id &&
        r.property_definition_id === propId,
    );
    if (dup) issues.push({ code: "409", text: "Triple already exists (" + dup.id + ")" });
  }
  if (autoMode && form.relationship_type) {
    const ident = window.snakeify(form.relationship_type);
    const exists = state.property_definitions.find((p) => p.identifier === ident);
    if (exists)
      issues.push({
        code: "200",
        text: 'Will reuse existing "' + exists.identifier + '" — no new property created',
        hint: true,
      });
    else
      issues.push({ code: "200", text: 'Will auto-create property "' + ident + '"', hint: true });
  }

  const submit = () => {
    try {
      const payload = {
        source_id: form.source_id,
        target_id: form.target_id,
        source: form.source,
        confidence: form.confidence,
      };
      if (autoMode) payload.relationship_type = form.relationship_type;
      else payload.property_definition_id = form.property_definition_id;
      actions.createRelationship(payload);
      onClose();
    } catch {}
  };

  const valid =
    form.source_id &&
    form.target_id &&
    form.source_id !== form.target_id &&
    (autoMode ? !!form.relationship_type : !!form.property_definition_id) &&
    !issues.some((i) => i.code === "409");

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      title="New relationship"
      subtitle="Typed directed edge between any two Class or Individual nodes. Mixed endpoints allowed."
      footer={
        <>
          <span className="modal-foot-hint mono">
            {valid ? "POST /relationships" : "Resolve issues to continue"}
          </span>
          <span style={{ flex: 1 }}></span>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary btn-sm" disabled={!valid} onClick={submit}>
            Create relationship
          </button>
        </>
      }
    >
      <div className="rel-builder">
        <div className="rel-pos">
          <div className="rel-label">
            Subject <span className="req">*</span>
          </div>
          <EntityPicker
            value={form.source_id}
            onChange={(v) => setForm({ ...form, source_id: v })}
            placeholder="Search class or individual…"
            exclude={form.target_id ? [form.target_id] : []}
          />
        </div>
        <div className="rel-arrow">
          <div className="rel-arrow-line"></div>
          <div className="rel-arrow-tip">▶</div>
        </div>
        <div className="rel-pos">
          <div className="rel-label">
            Object <span className="req">*</span>
          </div>
          <EntityPicker
            value={form.target_id}
            onChange={(v) => setForm({ ...form, target_id: v })}
            placeholder="Search class or individual…"
            exclude={form.source_id ? [form.source_id] : []}
          />
        </div>
      </div>

      <Field label="Predicate" required>
        <div className="predicate-toggle">
          <button
            type="button"
            className={"pred-tab" + (!autoMode ? " active" : "")}
            onClick={() => setAutoMode(false)}
          >
            Pick property
          </button>
          <button
            type="button"
            className={"pred-tab" + (autoMode ? " active" : "")}
            onClick={() => setAutoMode(true)}
          >
            Type identifier
          </button>
        </div>
        {!autoMode ? (
          <Select
            value={form.property_definition_id}
            onChange={(v) => setForm({ ...form, property_definition_id: v })}
            options={state.property_definitions.map((p) => ({
              value: p.id,
              label:
                p.title +
                "  ·  " +
                p.identifier +
                (p.is_relevant === false ? "  (irrelevant)" : ""),
            }))}
          />
        ) : (
          <>
            <TextInput
              value={form.relationship_type}
              onChange={(v) => setForm({ ...form, relationship_type: v })}
              placeholder="e.g. interacts_with"
              mono
            />
            <div className="field-hint" style={{ marginTop: 6 }}>
              If no property has this identifier, the API auto-creates one with a placeholder title.
            </div>
          </>
        )}
      </Field>

      <div className="form-row-2">
        <Field label="Source">
          <TextInput
            value={form.source}
            onChange={(v) => setForm({ ...form, source: v })}
            placeholder="manual / pipeline / etc."
          />
        </Field>
        <Field label="Confidence" hint="0.0 – 1.0">
          <NumberInput
            value={form.confidence}
            onChange={(v) => setForm({ ...form, confidence: v })}
            min={0}
            max={1}
            step={0.01}
          />
        </Field>
      </div>

      {issues.length > 0 && (
        <div className="validation-list">
          {issues.map((iss, i) => (
            <div
              key={i}
              className={"val-row " + (iss.code === "409" || iss.code === "400" ? "err" : "hint")}
            >
              <span className="val-code mono">{iss.code}</span>
              <span>{iss.text}</span>
            </div>
          ))}
        </div>
      )}
    </Modal>
  );
}

// ============= Individual (CREATE only — PUT only takes title+description) =============
function IndividualDialog({ open, onClose, defaultClassId }) {
  const { state, actions } = window.useStore();
  const [form, setForm] = useState({});
  useEffect(() => {
    if (!open) return;
    setForm({
      title: "",
      description: "",
      class_ids: defaultClassId ? [defaultClassId] : state.classes[0] ? [state.classes[0].id] : [],
    });
  }, [open, defaultClassId]);

  // Real-time title-uniqueness check across the proposed parent classes
  const issues = [];
  if (form.title && form.class_ids?.length) {
    const t = form.title.trim().toLowerCase();
    for (const cid of form.class_ids) {
      const cls = state.classes.find((c) => c.id === cid);
      const dup = state.individuals.find(
        (i) => i.class_ids.includes(cid) && (i.title || "").trim().toLowerCase() === t,
      );
      if (dup)
        issues.push({
          code: "409",
          text: '"' + form.title + '" already exists in ' + (cls?.title || cid),
        });
    }
  }

  const valid = form.title?.trim() && form.class_ids?.length && issues.length === 0;

  const submit = () => {
    try {
      actions.createIndividual({
        title: form.title,
        description: form.description,
        class_ids: form.class_ids,
      });
      onClose();
    } catch {}
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      title="New individual"
      subtitle="Concrete instance of one or more classes. POST /individuals only accepts title, description, and class_ids."
      footer={
        <>
          <span className="modal-foot-hint mono">
            {valid ? "POST /individuals" : "Resolve issues to continue"}
          </span>
          <span style={{ flex: 1 }}></span>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary btn-sm" disabled={!valid} onClick={submit}>
            Create individual
          </button>
        </>
      }
    >
      <Field label="Title" required hint="Unique within every parent class">
        <TextInput
          value={form.title}
          onChange={(v) => setForm({ ...form, title: v })}
          placeholder="e.g. BRCA1"
          autoFocus
        />
      </Field>
      <Field label="Description">
        <TextArea
          value={form.description}
          onChange={(v) => setForm({ ...form, description: v })}
          placeholder="Optional — what this instance refers to"
        />
      </Field>
      <Field
        label="Class membership"
        required
        hint="Ordered list — first parent wins on inherited-property conflicts"
      >
        <OrderedClassList
          classIds={form.class_ids || []}
          onChange={(v) => setForm({ ...form, class_ids: v })}
        />
      </Field>
      <div className="form-callout">
        <Icon name="shield" size={12} />
        <span>
          <em>data_properties</em> and <em>external_references</em> aren't accepted at creation —
          they begin empty and are populated by import workflows. Use the detail panel to view
          inherited schema.
        </span>
      </div>
      {issues.length > 0 && (
        <div className="validation-list">
          {issues.map((iss, i) => (
            <div key={i} className="val-row err">
              <span className="val-code mono">{iss.code}</span>
              <span>{iss.text}</span>
            </div>
          ))}
        </div>
      )}
    </Modal>
  );
}

window.TaxonomyDialog = TaxonomyDialog;
window.ConceptSchemeDialog = ConceptSchemeDialog;
window.ClassDialog = ClassDialog;
window.MoveClassDialog = MoveClassDialog;
window.PropertyDialog = PropertyDialog;
window.RelationshipDialog = RelationshipDialog;
window.IndividualDialog = IndividualDialog;
