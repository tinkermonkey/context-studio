// Individuals (Data Nodes) — master/detail CRUD.
//
// Each endpoint from the backend memo gets a discrete surface:
//   POST   /individuals                            → "New individual" dialog
//   PUT    /individuals/{id}                       → identity card (title + description)
//   POST   /individuals/{id}/classes               → "Add parent" in membership card
//   DELETE /individuals/{id}/classes/{class_id}    → ✕ on each chip
//   PUT    /individuals/{id}/classes               → reorder via drag handles (full replacement)
//   GET    /individuals/{id}/inherited-properties  → "Inherited properties" panel
//   DELETE /individuals/{id}                       → cascade-aware confirm

const { useState: useS, useEffect: useE, useMemo: useM, useRef: useR } = React;

// ---------------------------------------------------------------------------
// Master list
// ---------------------------------------------------------------------------
function IndividualsPage() {
  const { state, actions } = window.useStore();
  const [search, setSearch] = useS("");
  const [classFilter, setClassFilter] = useS("all");
  const [parentCount, setParentCount] = useS("any"); // any | one | many
  const [selectedId, setSelectedId] = useS(state.individuals[0]?.id || null);
  const [creating, setCreating] = useS(false);
  const [confirmId, setConfirmId] = useS(null);

  // Keep selection valid as the list mutates (e.g. delete)
  useE(() => {
    if (selectedId && !state.individuals.find((i) => i.id === selectedId)) {
      setSelectedId(state.individuals[0]?.id || null);
    }
  }, [state.individuals, selectedId]);

  const filtered = useM(() => {
    const q = search.trim().toLowerCase();
    return state.individuals.filter((i) => {
      if (classFilter !== "all" && !i.class_ids.includes(classFilter)) return false;
      if (parentCount === "one" && i.class_ids.length !== 1) return false;
      if (parentCount === "many" && i.class_ids.length < 2) return false;
      if (!q) return true;
      return (
        i.title.toLowerCase().includes(q) ||
        (i.description || "").toLowerCase().includes(q) ||
        i.id.toLowerCase().includes(q)
      );
    });
  }, [state.individuals, search, classFilter, parentCount]);

  const selected = state.individuals.find((i) => i.id === selectedId) || null;
  const confirmTarget = confirmId ? state.individuals.find((i) => i.id === confirmId) : null;
  const cascadeRels = confirmTarget ? actions.individualRelationships(confirmTarget.id) : [];

  const filterChip = classFilter === "all" ? null : state.classes.find((c) => c.id === classFilter);

  return (
    <div className="canvas-inner ind-page">
      <PageHeader
        title={
          <>
            Individuals{" "}
            <span className="id-tag">
              {filtered.length} of {state.individuals.length}
            </span>
          </>
        }
        subtitle="Concrete data nodes. Membership in parent classes is an ordered list — first parent wins on inherited-property conflicts."
        actions={
          <>
            <button className="btn btn-ghost">
              <Icon name="ext" /> Export CSV
            </button>
            <button className="btn btn-primary" onClick={() => setCreating(true)}>
              <Icon name="plus" /> New individual
            </button>
          </>
        }
      />

      <div className="ind-filters">
        <div className="ind-search">
          <Icon name="search" size={13} />
          <input
            className="ind-search-input"
            placeholder="Search title, description, or id…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {search && (
            <button className="ind-search-x" onClick={() => setSearch("")}>
              <Icon name="x" size={11} />
            </button>
          )}
        </div>
        <div className="ind-filter-group">
          <span className="ind-filter-label">Class</span>
          <select
            className="ind-filter-select"
            value={classFilter}
            onChange={(e) => setClassFilter(e.target.value)}
          >
            <option value="all">Any class</option>
            {state.classes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title}
              </option>
            ))}
          </select>
        </div>
        <div className="ind-filter-group">
          <span className="ind-filter-label">Parents</span>
          <div className="ind-seg">
            {[
              ["any", "Any"],
              ["one", "Single"],
              ["many", "Multi"],
            ].map(([v, l]) => (
              <button
                key={v}
                className={"ind-seg-btn" + (parentCount === v ? " active" : "")}
                onClick={() => setParentCount(v)}
              >
                {l}
              </button>
            ))}
          </div>
        </div>
        {filterChip && (
          <div className="ind-filter-active mono">
            GET /classes/<span className="ind-filter-active-id">{classFilter}</span>/individuals
          </div>
        )}
      </div>

      <div className="ind-split">
        <IndividualsList
          items={filtered}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onDelete={(id) => setConfirmId(id)}
        />
        <IndividualDetail individual={selected} onDelete={(id) => setConfirmId(id)} />
      </div>

      <window.IndividualDialog
        open={creating}
        onClose={() => setCreating(false)}
        defaultClassId={classFilter !== "all" ? classFilter : null}
      />

      <CascadeDeleteConfirm
        open={!!confirmTarget}
        individual={confirmTarget}
        relationships={cascadeRels}
        onClose={() => setConfirmId(null)}
        onConfirm={() => {
          try {
            const r = actions.deleteIndividual(confirmTarget.id);
            if (selectedId === r.id) setSelectedId(null);
            setConfirmId(null);
          } catch {}
        }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// List column
// ---------------------------------------------------------------------------
function IndividualsList({ items, selectedId, onSelect, onDelete }) {
  const { state } = window.useStore();
  return (
    <div className="ind-list panel">
      <div className="ind-list-head">
        <span className="ind-list-head-cell flex">Individual</span>
        <span className="ind-list-head-cell w-cls">Classes</span>
        <span className="ind-list-head-cell w-ver">Ver</span>
      </div>
      <div className="ind-list-scroll">
        {items.length === 0 && (
          <div className="ind-empty">
            <div className="ind-empty-icon">
              <Icon name="search" size={18} />
            </div>
            <div className="ind-empty-title">No individuals match</div>
            <div className="ind-empty-sub">Adjust the filters or create a new individual.</div>
          </div>
        )}
        {items.map((i) => {
          const primary = state.classes.find((c) => c.id === i.class_ids[0]);
          const extras = i.class_ids.length - 1;
          return (
            <div
              key={i.id}
              className={"ind-list-row" + (i.id === selectedId ? " selected" : "")}
              onClick={() => onSelect(i.id)}
            >
              <div className="ind-list-cell flex">
                <div className="ind-list-title">{i.title}</div>
                <div className="ind-list-id mono">{i.id}</div>
              </div>
              <div className="ind-list-cell w-cls">
                {primary && (
                  <span className="kg-node sm" data-domain={primary.domain}>
                    <span className="swatch"></span>
                    {primary.title}
                  </span>
                )}
                {extras > 0 && <span className="ind-extra-count mono">+{extras}</span>}
              </div>
              <div className="ind-list-cell w-ver">
                <span className="version-pill">v{i.version}</span>
                <button
                  type="button"
                  className="ind-row-x"
                  title="Delete"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(i.id);
                  }}
                >
                  <Icon name="x" size={11} />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Detail column
// ---------------------------------------------------------------------------
function IndividualDetail({ individual, onDelete }) {
  if (!individual) {
    return (
      <div className="ind-detail panel ind-detail-empty">
        <div className="ind-detail-empty-mark">
          <Icon name="data" size={20} />
        </div>
        <div className="ind-detail-empty-title">Select an individual</div>
        <div className="ind-detail-empty-sub">Or create a new one to populate this panel.</div>
      </div>
    );
  }

  return (
    <div className="ind-detail">
      <DetailHeader individual={individual} onDelete={onDelete} />
      <IdentityCard individual={individual} />
      <MembershipCard individual={individual} />
      <InheritedCard individual={individual} />
      <OwnValuesCard individual={individual} />
      <RelationshipsCard individual={individual} />
      <AuditCard individual={individual} />
    </div>
  );
}

function DetailHeader({ individual, onDelete }) {
  return (
    <div className="ind-detail-head">
      <div className="ind-detail-head-main">
        <div className="ind-detail-eyebrow mono">individual</div>
        <div className="ind-detail-title">{individual.title}</div>
        <div className="ind-detail-id mono">{individual.id}</div>
      </div>
      <div className="ind-detail-head-actions">
        <span className="version-pill">v{individual.version}</span>
        <button className="btn btn-ghost btn-sm danger" onClick={() => onDelete(individual.id)}>
          <Icon name="x" size={12} /> Delete
        </button>
      </div>
    </div>
  );
}

// ----- Identity (PUT title/description) -----
function IdentityCard({ individual }) {
  const { actions } = window.useStore();
  const [title, setTitle] = useS(individual.title);
  const [desc, setDesc] = useS(individual.description || "");
  const [editing, setEditing] = useS(false);
  useE(() => {
    setTitle(individual.title);
    setDesc(individual.description || "");
    setEditing(false);
  }, [individual.id]);

  const dirty =
    title.trim() !== individual.title || (desc || "") !== (individual.description || "");

  const save = () => {
    try {
      const r = actions.updateIndividual(individual.id, { title, description: desc });
      // r._noop indicates server detected no change — reflect that in UI
      if (!r._noop) setEditing(false);
      else setEditing(false);
    } catch {}
  };

  return (
    <DetailCard
      title="Identity"
      endpoint="PUT /individuals/{id}"
      hint="Only title and description are accepted on this route. No-ops do not bump the version."
    >
      {!editing ? (
        <div className="ind-identity-view">
          <div className="ind-identity-row">
            <span className="ind-identity-label">Title</span>
            <span className="ind-identity-value">{individual.title}</span>
          </div>
          <div className="ind-identity-row">
            <span className="ind-identity-label">Description</span>
            <span className="ind-identity-value">
              {individual.description || <em className="muted">— none —</em>}
            </span>
          </div>
          <div className="ind-identity-actions">
            <button className="btn btn-ghost btn-sm" onClick={() => setEditing(true)}>
              <Icon name="edit" size={12} /> Edit
            </button>
          </div>
        </div>
      ) : (
        <div className="ind-identity-edit">
          <Field label="Title" required hint="Unique within every parent class (409 on conflict)">
            <TextInput value={title} onChange={setTitle} autoFocus />
          </Field>
          <Field label="Description">
            <TextArea value={desc} onChange={setDesc} rows={3} />
          </Field>
          <div className="ind-identity-actions">
            <span className="modal-foot-hint mono">
              {dirty ? "PUT will bump version" : "No changes — server treats as no-op"}
            </span>
            <span style={{ flex: 1 }}></span>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => {
                setTitle(individual.title);
                setDesc(individual.description || "");
                setEditing(false);
              }}
            >
              Cancel
            </button>
            <button className="btn btn-primary btn-sm" onClick={save} disabled={!title.trim()}>
              Save
            </button>
          </div>
        </div>
      )}
    </DetailCard>
  );
}

// ----- Membership (POST add, DELETE remove, PUT reorder) -----
function MembershipCard({ individual }) {
  const { state, actions } = window.useStore();
  const [adding, setAdding] = useS(false);
  const [pickValue, setPickValue] = useS(null);
  const [pendingOrder, setPendingOrder] = useS(null); // null = no draft; array = draft

  // Reset draft when individual changes
  useE(() => {
    setPendingOrder(null);
    setAdding(false);
    setPickValue(null);
  }, [individual.id]);

  const order = pendingOrder || individual.class_ids;
  const isDirty = pendingOrder && pendingOrder.some((c, i) => c !== individual.class_ids[i]);

  const move = (idx, dir) => {
    const next = [...order];
    const target = idx + dir;
    if (target < 0 || target >= next.length) return;
    [next[idx], next[target]] = [next[target], next[idx]];
    setPendingOrder(next);
  };

  const commitOrder = () => {
    try {
      actions.replaceIndividualClasses(individual.id, pendingOrder);
      setPendingOrder(null);
    } catch {}
  };

  const removeClass = (cid) => {
    try {
      actions.removeIndividualClass(individual.id, cid);
    } catch {}
  };

  const addClass = () => {
    if (!pickValue) return;
    try {
      actions.addIndividualClass(individual.id, pickValue);
      setAdding(false);
      setPickValue(null);
    } catch {}
  };

  return (
    <DetailCard
      title={
        <>
          Class membership <span className="ind-card-count">{individual.class_ids.length}</span>
        </>
      }
      endpoint="…/classes (POST · DELETE · PUT)"
      hint="Three sub-resource endpoints. Removing the last parent returns 400. PUT requires the same ID set as the current list — it is reorder, not diff."
    >
      <ol className="ind-membership-list">
        {order.map((cid, idx) => {
          const cls = state.classes.find((c) => c.id === cid);
          const lastOne = order.length === 1;
          return (
            <li key={cid} className={"ind-membership-row" + (idx === 0 ? " primary" : "")}>
              <span className="ind-membership-rank mono">{idx + 1}</span>
              <span className="ind-membership-tag">
                {cls ? (
                  <span className="kg-node" data-domain={cls.domain}>
                    <span className="swatch"></span>
                    {cls.title}
                  </span>
                ) : (
                  <span className="kg-node missing" data-domain="default">
                    <span className="swatch"></span>
                    {cid} · missing
                  </span>
                )}
                {idx === 0 && (
                  <span className="ind-primary-tag mono">primary · wins on conflict</span>
                )}
              </span>
              <span className="ind-membership-handles">
                <button
                  className="ind-icon-btn"
                  disabled={idx === 0}
                  onClick={() => move(idx, -1)}
                  title="Move up"
                >
                  <Icon name="chev-up" size={11} />
                </button>
                <button
                  className="ind-icon-btn"
                  disabled={idx === order.length - 1}
                  onClick={() => move(idx, +1)}
                  title="Move down"
                >
                  <Icon name="chev-down" size={11} />
                </button>
                <button
                  className="ind-icon-btn danger"
                  disabled={lastOne}
                  onClick={() => removeClass(cid)}
                  title={lastOne ? "Cannot remove last parent" : "DELETE /classes/" + cid}
                >
                  <Icon name="x" size={11} />
                </button>
              </span>
            </li>
          );
        })}
      </ol>

      <div className="ind-membership-actions">
        {isDirty && (
          <>
            <button className="btn btn-ghost btn-sm" onClick={() => setPendingOrder(null)}>
              Discard order
            </button>
            <button className="btn btn-primary btn-sm" onClick={commitOrder}>
              <Icon name="check" size={12} /> Save order
            </button>
            <span className="modal-foot-hint mono">PUT /classes</span>
          </>
        )}
        {!isDirty && !adding && (
          <button className="btn btn-ghost btn-sm" onClick={() => setAdding(true)}>
            <Icon name="plus" size={12} /> Add parent class
          </button>
        )}
        {!isDirty && adding && (
          <div className="ind-add-row">
            <EntityPicker
              value={pickValue}
              onChange={setPickValue}
              kinds={["class"]}
              exclude={individual.class_ids}
              placeholder="Pick a class to add…"
            />
            <button className="btn btn-primary btn-sm" disabled={!pickValue} onClick={addClass}>
              Add
            </button>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => {
                setAdding(false);
                setPickValue(null);
              }}
            >
              Cancel
            </button>
            <span className="modal-foot-hint mono">POST /classes</span>
          </div>
        )}
      </div>
    </DetailCard>
  );
}

// ----- Inherited properties -----
function InheritedCard({ individual }) {
  const { state, actions } = window.useStore();
  const { items } = actions.getInheritedProperties(individual.id);
  return (
    <DetailCard
      title={
        <>
          Inherited properties <span className="ind-card-count">{items.length}</span>
        </>
      }
      endpoint="GET /individuals/{id}/inherited-properties"
      hint="Read-only schema fetched from parent classes. On identifier collisions, the first parent wins. Use this to drive a dynamic property form."
    >
      {items.length === 0 ? (
        <div className="empty-mini">No properties inherited from current parent classes.</div>
      ) : (
        <table className="mini-t inh-t">
          <thead>
            <tr>
              <th>Identifier</th>
              <th>Datatype</th>
              <th>Inherited from</th>
              <th>Default</th>
            </tr>
          </thead>
          <tbody>
            {items.map((p) => {
              const ownValue = (individual.data_properties || []).find(
                (d) => d.key === p.identifier,
              );
              return (
                <tr key={p.identifier}>
                  <td className="mono ind-prop-id">{p.identifier}</td>
                  <td className="mono muted">
                    {p.datatype || <span className="ind-prop-untyped">— untyped —</span>}
                  </td>
                  <td>
                    <span
                      className="kg-node sm"
                      data-domain={
                        state.classes.find((c) => c.id === p.inherited_from_class_id)?.domain ||
                        "default"
                      }
                    >
                      <span className="swatch"></span>
                      {p.inherited_from_class_title}
                    </span>
                  </td>
                  <td className="mono muted">
                    {ownValue ? (
                      <span className="ind-prop-overridden">{ownValue.value}</span>
                    ) : (
                      p.value || "—"
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </DetailCard>
  );
}

// ----- Own data_property values (read-only) -----
function OwnValuesCard({ individual }) {
  const props = individual.data_properties || [];
  return (
    <DetailCard
      title={
        <>
          Own values <span className="ind-card-count">{props.length}</span>
        </>
      }
      endpoint="data_properties (read-only)"
      hint="The individual's own literal values. Currently populated via import / interchange workflows — not via main CRUD."
      tone="muted"
    >
      {props.length === 0 ? (
        <div className="empty-mini">
          No own values yet — this individual relies on inherited defaults until an import populates
          literals.
        </div>
      ) : (
        <table className="mini-t">
          <thead>
            <tr>
              <th>Identifier</th>
              <th>Value</th>
              <th>Datatype</th>
            </tr>
          </thead>
          <tbody>
            {props.map((p, i) => (
              <tr key={i}>
                <td className="mono">{p.property_identifier || p.key}</td>
                <td>{p.value}</td>
                <td className="mono muted">{p.datatype || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </DetailCard>
  );
}

// ----- Relationships involving this individual -----
function RelationshipsCard({ individual }) {
  const { state, actions } = window.useStore();
  const rels = actions.individualRelationships(individual.id);
  const propTitle = (id) => state.property_definitions.find((p) => p.id === id)?.title || "?";
  const entityTitle = (id) =>
    state.classes.find((c) => c.id === id)?.title ||
    state.individuals.find((i) => i.id === id)?.title ||
    id;

  return (
    <DetailCard
      title={
        <>
          Relationships <span className="ind-card-count">{rels.length}</span>
        </>
      }
      endpoint="cascade-deleted with the individual"
      hint="Deleting this individual will remove every triple where it appears as either source or target."
      tone="muted"
    >
      {rels.length === 0 ? (
        <div className="empty-mini">Not used in any relationships.</div>
      ) : (
        <ul className="ind-rel-list">
          {rels.map((r) => {
            const isSource = r.source_id === individual.id;
            return (
              <li key={r.id} className="ind-rel-row">
                <span className={"ind-rel-side" + (isSource ? " active" : "")}>
                  {isSource ? individual.title : entityTitle(r.source_id)}
                </span>
                <span className="ind-rel-pred mono">— {propTitle(r.property_definition_id)} →</span>
                <span className={"ind-rel-side" + (!isSource ? " active" : "")}>
                  {!isSource ? individual.title : entityTitle(r.target_id)}
                </span>
                <span className="ind-rel-id mono muted">{r.id}</span>
              </li>
            );
          })}
        </ul>
      )}
    </DetailCard>
  );
}

// ----- Audit -----
function AuditCard({ individual }) {
  const fmt = (iso) => {
    if (!iso) return "—";
    return iso.replace("T", " ").replace(/\..*$/, " UTC");
  };
  return (
    <DetailCard
      title="Audit"
      endpoint="bookkeeping"
      hint="Optimistic concurrency uses the version number; updates that change nothing leave last_modified untouched."
      tone="muted"
    >
      <div className="ind-audit-grid">
        <div>
          <span className="ind-audit-label">created_at</span>
          <span className="mono">{fmt(individual.created_at) || individual.updated || "—"}</span>
        </div>
        <div>
          <span className="ind-audit-label">last_modified</span>
          <span className="mono">{fmt(individual.last_modified) || individual.updated || "—"}</span>
        </div>
        <div>
          <span className="ind-audit-label">version</span>
          <span className="mono">{individual.version}</span>
        </div>
        <div>
          <span className="ind-audit-label">source</span>
          <span className="mono muted">{individual.source}</span>
        </div>
      </div>
    </DetailCard>
  );
}

// ---------------------------------------------------------------------------
// Shared
// ---------------------------------------------------------------------------
function DetailCard({ title, endpoint, hint, children, tone }) {
  return (
    <section className={"ind-card panel" + (tone === "muted" ? " muted" : "")}>
      <header className="ind-card-head">
        <div className="ind-card-head-main">
          <div className="ind-card-title">{title}</div>
          {hint && <div className="ind-card-hint">{hint}</div>}
        </div>
        {endpoint && <div className="ind-card-endpoint mono">{endpoint}</div>}
      </header>
      <div className="ind-card-body">{children}</div>
    </section>
  );
}

function CascadeDeleteConfirm({ open, individual, relationships, onClose, onConfirm }) {
  const { state } = window.useStore();
  if (!individual) return null;
  const propTitle = (id) => state.property_definitions.find((p) => p.id === id)?.title || "?";
  const entityTitle = (id) =>
    state.classes.find((c) => c.id === id)?.title ||
    state.individuals.find((i) => i.id === id)?.title ||
    id;
  const noRels = relationships.length === 0;

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="md"
      title={
        <>
          Delete <em>{individual.title}</em>?
        </>
      }
      subtitle="This is a hard delete. The individual and every relationship it participates in are removed."
      footer={
        <>
          <span className="modal-foot-hint mono">DELETE /individuals/{individual.id}</span>
          <span style={{ flex: 1 }}></span>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-danger btn-sm" onClick={onConfirm}>
            {noRels ? "Delete individual" : "Delete + cascade " + relationships.length}
          </button>
        </>
      }
    >
      <div className={"cascade-callout " + (noRels ? "safe" : "warn")}>
        <Icon name={noRels ? "shield" : "alert"} size={14} />
        <div>
          {noRels ? (
            "No relationships reference this individual. Deletion is clean."
          ) : (
            <span>
              <strong>{relationships.length}</strong> relationship
              {relationships.length === 1 ? "" : "s"} will be cascade-deleted with this individual.
            </span>
          )}
        </div>
      </div>
      {!noRels && (
        <div className="cascade-list">
          <div className="cascade-list-head mono">Triples to be removed</div>
          {relationships.slice(0, 12).map((r) => {
            const isSource = r.source_id === individual.id;
            return (
              <div key={r.id} className="cascade-row">
                <span className={"cascade-side" + (isSource ? " self" : "")}>
                  {isSource ? individual.title : entityTitle(r.source_id)}
                </span>
                <span className="mono cascade-pred">— {propTitle(r.property_definition_id)} →</span>
                <span className={"cascade-side" + (!isSource ? " self" : "")}>
                  {!isSource ? individual.title : entityTitle(r.target_id)}
                </span>
                <span className="mono muted cascade-id">{r.id}</span>
              </div>
            );
          })}
          {relationships.length > 12 && (
            <div className="cascade-row more">…and {relationships.length - 12} more</div>
          )}
        </div>
      )}
    </Modal>
  );
}

window.IndividualsPage = IndividualsPage;
