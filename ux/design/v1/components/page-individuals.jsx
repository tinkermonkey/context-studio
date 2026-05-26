// =========================================================================
// Individuals page — master list + detail inspector
//   • Filter bar: search, class filter, parent-count seg
//   • Master list with mono id, class chip, version pill
//   • Detail: identity, membership (with primary/conflict-winner mark),
//     inherited properties, own data values, relationships, audit
// =========================================================================

function IndividualsPage({ onNav }) {
  const D = window.CS_DATA;
  const [search, setSearch] = useState("");
  const [classFilter, setClassFilter] = useState("all");
  const [parents, setParents] = useState("any");
  const [selectedId, setSelectedId] = useState(D.individuals[0].id);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return D.individuals.filter((i) => {
      if (classFilter !== "all" && !i.class_ids.includes(classFilter)) return false;
      if (parents === "one"  && i.class_ids.length !== 1) return false;
      if (parents === "many" && i.class_ids.length < 2) return false;
      if (!q) return true;
      return i.title.toLowerCase().includes(q)
          || (i.description || "").toLowerCase().includes(q)
          || i.id.toLowerCase().includes(q);
    });
  }, [search, classFilter, parents]);

  const selected = D.individuals.find((i) => i.id === selectedId) || null;

  return (
    <div className="canvas-inner" data-screen-label="07 Data · Individuals">
      <div className="page-head">
        <div>
          <div className="page-head-meta">
            <span className="chip emerald"><span className="dot"></span>data</span>
            <span className="id-tag">node_type · individual</span>
            <span className="muted mono" style={{fontSize:11}}>{filtered.length} of {D.individuals.length}</span>
          </div>
          <h1>Individuals <span className="id-tag">/data/individuals</span></h1>
          <div className="subtitle">
            Concrete data nodes. Membership in parent classes is an ordered list —
            the first parent wins on inherited-property conflicts.
          </div>
        </div>
        <div className="page-actions">
          <button className="btn"><Icon name="ext" size={13} /> Export CSV</button>
          <button className="btn btn-primary"><Icon name="plus" size={13} /> New individual</button>
        </div>
      </div>

      <div className="filter-bar">
        <div className="search-input-wrap">
          <Icon name="search" size={13}/>
          <input className="input with-icon" placeholder="Search title, description, or id…"
            value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <select className="select" value={classFilter} onChange={(e) => setClassFilter(e.target.value)}>
          <option value="all">Any class</option>
          {D.classes.map((c) => (<option key={c.id} value={c.id}>{c.title}</option>))}
        </select>
        <div className="seg">
          {[["any","Any parents"],["one","Single"],["many","Multi"]].map(([v,l]) => (
            <button key={v} className={"seg-btn" + (parents === v ? " active" : "")} onClick={() => setParents(v)}>{l}</button>
          ))}
        </div>
        {classFilter !== "all" && (
          <span className="mono muted" style={{fontSize: 11}}>
            GET /classes/<b style={{color:"var(--accent-primary)"}}>{classFilter}</b>/individuals
          </span>
        )}
      </div>

      <div className="split-master-detail" style={{minHeight: 600}}>
        <IndividualsList items={filtered} selectedId={selectedId} onSelect={setSelectedId} />
        <IndividualDetail individual={selected} />
      </div>
    </div>
  );
}
window.IndividualsPage = IndividualsPage;

function IndividualsList({ items, selectedId, onSelect }) {
  const D = window.CS_DATA;
  return (
    <div className="panel" style={{display: "flex", flexDirection: "column"}}>
      <div className="panel-head" style={{padding: "10px 14px"}}>
        <div className="panel-title" style={{fontSize: 12, fontFamily: "var(--font-mono)", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--canvas-fg-3)", fontWeight: 500}}>
          INDIVIDUAL · CLASSES · VER
        </div>
        <span className="muted mono" style={{fontSize: 11}}>{items.length}</span>
      </div>
      <div style={{overflow: "auto", flex: 1, maxHeight: 580}}>
        {items.map((i) => {
          const primary = D.classes.find((c) => c.id === i.class_ids[0]);
          const extras = i.class_ids.length - 1;
          return (
            <div key={i.id}
              className={"activity-item" + (i.id === selectedId ? " " : "")}
              onClick={() => onSelect(i.id)}
              style={{
                gridTemplateColumns: "1fr auto auto",
                cursor: "pointer",
                background: i.id === selectedId ? "rgba(251,191,36,0.06)" : "transparent",
                borderLeft: i.id === selectedId ? "2px solid var(--accent-primary)" : "2px solid transparent",
                paddingLeft: 14,
              }}>
              <div>
                <div style={{fontSize: 13, fontWeight: 500}}>{i.title}</div>
                <div className="mono muted" style={{fontSize: 11, marginTop: 2}}>{i.id}</div>
              </div>
              <div className="row gap-12">
                {primary && (
                  <span className="kg-node-pill sm" data-domain={primary.domain}>
                    <span className="swatch"></span>{primary.title}
                  </span>
                )}
                {extras > 0 && <span className="mono muted" style={{fontSize: 11}}>+{extras}</span>}
              </div>
              <span className="version-pill">v{i.version}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function IndividualDetail({ individual }) {
  const D = window.CS_DATA;
  if (!individual) {
    return (
      <div className="inspector" style={{display:"flex", alignItems:"center", justifyContent:"center", minHeight: 400}}>
        <div className="empty">
          <div className="ic"><Icon name="data" size={22} /></div>
          <div className="t">Select an individual</div>
          <div className="d">Click a row to inspect identity, membership, inherited properties, and relationships.</div>
        </div>
      </div>
    );
  }

  const primary = D.classes.find((c) => c.id === individual.class_ids[0]);
  const allMembership = individual.class_ids.map((cid) => D.classes.find((c) => c.id === cid)).filter(Boolean);
  const rels = D.relationships.filter((r) => r.source_id === individual.id || r.target_id === individual.id);
  // mock "inherited" properties — pull from primary class's slice
  const inherited = D.property_definitions.slice(0, 3).map((p) => ({
    identifier: p.identifier,
    datatype: ["xsd:string", "xsd:decimal", "xsd:integer"][Math.floor(Math.random() * 3)],
    inherited_from: primary?.title || "—",
    default: "—",
  }));

  return (
    <div className="inspector">
      <div className="inspector-head">
        <div style={{minWidth: 0, flex: 1}}>
          <div className="eyebrow">individual · {primary?.domain}</div>
          <div className="title">{individual.title}</div>
          <div className="mono-id">{individual.id}</div>
        </div>
        <div className="row gap-12">
          <span className="version-pill">v{individual.version}</span>
          <button className="btn btn-ghost btn-icon" title="Edit"><Icon name="edit" size={13}/></button>
          <button className="btn btn-ghost btn-icon" title="More"><Icon name="more" size={13}/></button>
        </div>
      </div>

      <div className="inspector-body">
        {/* Identity */}
        <div className="kv-grid">
          <div className="k">Description</div>
          <div className="v">{individual.description}</div>
          <div className="k">Source</div>
          <div className="v mono">{individual.source}</div>
          <div className="k">Confidence</div>
          <div className="v"><span className="version-pill">{individual.confidence.toFixed(2)}</span></div>
          <div className="k">Updated</div>
          <div className="v mono">{individual.updated}</div>
        </div>

        {/* Membership */}
        <div style={{padding: "14px 16px", borderBottom: "1px solid var(--canvas-border)"}}>
          <div className="between" style={{marginBottom: 10}}>
            <div className="row gap-12">
              <strong style={{fontSize: 13}}>Class membership</strong>
              <span className="muted mono" style={{fontSize: 11}}>{individual.class_ids.length}</span>
            </div>
            <button className="btn btn-ghost btn-xs"><Icon name="plus" size={11}/> Add parent</button>
          </div>
          <div style={{display: "flex", flexDirection: "column", gap: 6}}>
            {allMembership.map((c, idx) => (
              <div key={c.id} className="row gap-12" style={{padding: "6px 8px", background: idx === 0 ? "rgba(251,191,36,0.05)" : "transparent", borderRadius: 4, border: idx === 0 ? "1px solid rgba(251,191,36,0.22)" : "1px solid transparent"}}>
                <span className="mono muted" style={{fontSize: 11, width: 16}}>{idx + 1}</span>
                <span className="kg-node-pill sm" data-domain={c.domain}><span className="swatch"></span>{c.title}</span>
                {idx === 0 && <span className="mono" style={{fontSize: 10, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--accent-primary)"}}>primary · wins on conflict</span>}
                <span style={{flex: 1}}></span>
                <span className="mono muted" style={{fontSize: 11}}>{c.id}</span>
                <button className="btn btn-ghost btn-icon" disabled={individual.class_ids.length === 1}><Icon name="x" size={10}/></button>
              </div>
            ))}
          </div>
        </div>

        {/* Inherited properties */}
        <div style={{padding: "14px 16px", borderBottom: "1px solid var(--canvas-border)"}}>
          <div className="between" style={{marginBottom: 10}}>
            <div className="row gap-12">
              <strong style={{fontSize: 13}}>Inherited properties</strong>
              <span className="muted mono" style={{fontSize: 11}}>{inherited.length}</span>
            </div>
            <span className="muted mono" style={{fontSize: 10.5}}>GET /individuals/{individual.id}/inherited-properties</span>
          </div>
          <table className="tbl" style={{fontSize: 12}}>
            <thead><tr><th>Identifier</th><th>Datatype</th><th>Inherited from</th><th>Default</th></tr></thead>
            <tbody>
              {inherited.map((p, i) => (
                <tr key={i}>
                  <td className="mono">{p.identifier}</td>
                  <td className="mono muted">{p.datatype}</td>
                  <td><span className="kg-node-pill sm" data-domain={primary?.domain || "default"}><span className="swatch"></span>{p.inherited_from}</span></td>
                  <td className="mono muted">{p.default}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Relationships */}
        <div style={{padding: "14px 16px"}}>
          <div className="between" style={{marginBottom: 10}}>
            <div className="row gap-12">
              <strong style={{fontSize: 13}}>Relationships</strong>
              <span className="muted mono" style={{fontSize: 11}}>{rels.length}</span>
            </div>
            <span className="muted mono" style={{fontSize: 10.5}}>cascade-deleted with this individual</span>
          </div>
          {rels.length === 0 ? (
            <em className="muted" style={{fontSize: 12}}>— not used in any relationships —</em>
          ) : (
            <div style={{display:"flex", flexDirection:"column", gap: 8, fontFamily: "var(--font-mono)", fontSize: 11.5}}>
              {rels.map((r) => {
                const prop = D.property_definitions.find((p) => p.id === r.property_definition_id);
                const isSource = r.source_id === individual.id;
                const other = isSource
                  ? D.classes.find((c) => c.id === r.target_id) || D.individuals.find((i) => i.id === r.target_id)
                  : D.classes.find((c) => c.id === r.source_id) || D.individuals.find((i) => i.id === r.source_id);
                return (
                  <div key={r.id} className="row gap-12" style={{padding: "6px 0", borderBottom: "1px solid var(--canvas-border)"}}>
                    <span style={{color: isSource ? "var(--accent-primary)" : "var(--canvas-fg-1)"}}>{isSource ? individual.title : other?.title}</span>
                    <span className="muted">— {prop?.identifier} →</span>
                    <span style={{color: !isSource ? "var(--accent-primary)" : "var(--canvas-fg-1)"}}>{!isSource ? individual.title : other?.title}</span>
                    <span style={{flex: 1}}></span>
                    <span className="muted">{r.id}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
