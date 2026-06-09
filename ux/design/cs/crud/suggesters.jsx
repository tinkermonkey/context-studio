// =========================================================================
// Context Studio — AI suggesters for schema nodes
// RelationshipSuggester  → proposes typed triples to other schema nodes
// GroundingSection       → lists grounding refs + proposes external sources
// Both follow the same affordance as the description "Suggest" button:
//   ✨ button → shimmer → reviewable proposals with Accept / Dismiss.
// =========================================================================

function ConfBar({ value }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
      <span style={{ width: 34, height: 4, borderRadius: 999, background: "rgb(var(--canvas-border-strong))", overflow: "hidden", display: "inline-block" }}>
        <span style={{ display: "block", height: "100%", width: `${Math.round(value * 100)}%`, background: "rgb(var(--status-emerald))" }} />
      </span>
      <span style={{ fontFamily: "var(--font-mono)", fontSize: 10.5, color: "rgb(var(--canvas-fg-3))" }}>{value.toFixed(2)}</span>
    </span>
  );
}

// ---- Relationships ----------------------------------------------------
function RelationshipSuggester({ node }) {
  const [busy, setBusy] = useState(false);
  const [props, setProps] = useState(null);

  const run = () => {
    setBusy(true); setProps(null);
    CSStore.suggestRelationships(node).then((r) => { setBusy(false); setProps(r); });
  };
  const accept = (p) => {
    const id = "rel_" + Math.random().toString(36).slice(2, 6);
    CSStore.create("relationship", { id, source_id: node.id, target_id: p.target_id, property_definition_id: p.property_definition_id, source: "ai-suggested", confidence: p.confidence, created: "now" });
    setProps((ps) => ps.filter((x) => x !== p));
  };
  const dismiss = (p) => setProps((ps) => ps.filter((x) => x !== p));

  return (
    <div style={{ marginTop: 10 }}>
      <button type="button" className="ce-suggest-btn" onClick={run} disabled={busy}>
        <Icon name={busy ? "loading" : "zap"} size={11} className={busy ? "ce-spin" : ""} />
        {busy ? "Finding relationships…" : "Suggest relationships"}
      </button>
      {(busy || (props && props.length > 0)) && (
        <div className="ce-suggest-panel" style={{ marginTop: 8 }}>
          <div className="ce-suggest-panel__label"><Icon name="zap" size={11} /> Suggested relationships</div>
          {busy ? (
            <><div className="ce-shimmer" style={{ width: "100%" }} /><div className="ce-shimmer" style={{ width: "80%" }} /></>
          ) : (
            <div className="ce-sg-list">
              {props.map((p, i) => (
                <div key={i} className="ce-sg-card">
                  <div className="ce-sg-triple">
                    <span className="ce-sg-node">{node.title}</span>
                    <span className="ce-sg-pred">— {p.predicate} →</span>
                    <span className="ce-sg-node"><span className="cs-domain-dot" style={{ background: `var(--dom-${p.target_domain || "default"})` }} /> {p.target_label}</span>
                  </div>
                  <div className="ce-sg-rationale">{p.rationale}</div>
                  <div className="ce-sg-foot">
                    <ConfBar value={p.confidence} />
                    <div style={{ display: "flex", gap: 6, marginLeft: "auto" }}>
                      <Button variant="primary" size="sm" onClick={() => accept(p)}>Accept</Button>
                      <Button variant="ghost" size="sm" onClick={() => dismiss(p)}>Dismiss</Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
      {props && props.length === 0 && !busy && (
        <div style={{ fontSize: 11.5, color: "rgb(var(--canvas-fg-3))", marginTop: 8, fontStyle: "italic" }}>No new relationships to suggest — existing ones are already captured.</div>
      )}
    </div>
  );
}

// ---- Grounding references ---------------------------------------------
function GroundingSection({ type, node, active }) {
  const [busy, setBusy] = useState(false);
  const [props, setProps] = useState(null);
  const refs = node.grounding || [];

  const run = () => {
    setBusy(true); setProps(null);
    CSStore.suggestGrounding(node).then((r) => { setBusy(false); setProps(r); });
  };
  const accept = (p) => { CSStore.addGrounding(type, node, p); setProps((ps) => ps.filter((x) => x !== p)); };
  const dismiss = (p) => setProps((ps) => ps.filter((x) => x !== p));

  return (
    <InspectorPanel.Section title="Grounding references" count={refs.length}>
      {refs.length === 0 ? (
        <em style={{ fontSize: 12, color: "rgb(var(--canvas-fg-3))" }}>— not grounded to any source —</em>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {refs.map((g) => (
            <div key={g.id} className="ce-ground-row">
              <Icon name="link" size={12} style={{ color: "rgb(var(--canvas-fg-3))", flex: "none" }} />
              <span style={{ fontSize: 12.5, fontWeight: 500 }}>{g.name}</span>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 10.5, color: "rgb(var(--canvas-fg-3))" }}>{g.url}</span>
              {active && <button type="button" className="ce-ground-x" onClick={() => CSStore.removeGrounding(type, node, g.id)} aria-label="Remove"><Icon name="x" size={11} /></button>}
            </div>
          ))}
        </div>
      )}

      {active && (
        <div style={{ marginTop: 10 }}>
          <button type="button" className="ce-suggest-btn" onClick={run} disabled={busy}>
            <Icon name={busy ? "loading" : "zap"} size={11} className={busy ? "ce-spin" : ""} />
            {busy ? "Searching sources…" : "Suggest grounding"}
          </button>
          {(busy || (props && props.length > 0)) && (
            <div className="ce-suggest-panel" style={{ marginTop: 8 }}>
              <div className="ce-suggest-panel__label"><Icon name="zap" size={11} /> Suggested reference sources</div>
              {busy ? (
                <><div className="ce-shimmer" style={{ width: "100%" }} /><div className="ce-shimmer" style={{ width: "72%" }} /></>
              ) : (
                <div className="ce-sg-list">
                  {props.map((p, i) => (
                    <div key={i} className="ce-sg-card">
                      <div className="ce-sg-triple">
                        <Icon name="link" size={12} style={{ color: "rgb(var(--canvas-fg-3))" }} />
                        <span className="ce-sg-node">{p.name}</span>
                        <span style={{ fontFamily: "var(--font-mono)", fontSize: 10.5, color: "rgb(var(--canvas-fg-3))" }}>{p.url}</span>
                      </div>
                      <div className="ce-sg-rationale">{p.rationale}</div>
                      <div className="ce-sg-foot">
                        <ConfBar value={p.confidence} />
                        <div style={{ display: "flex", gap: 6, marginLeft: "auto" }}>
                          <Button variant="primary" size="sm" onClick={() => accept(p)}>Add</Button>
                          <Button variant="ghost" size="sm" onClick={() => dismiss(p)}>Dismiss</Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
          {props && props.length === 0 && !busy && (
            <div style={{ fontSize: 11.5, color: "rgb(var(--canvas-fg-3))", marginTop: 8, fontStyle: "italic" }}>No new sources to suggest for this domain.</div>
          )}
        </div>
      )}
    </InspectorPanel.Section>
  );
}

Object.assign(window, { RelationshipSuggester, GroundingSection, ConfBar });
