// The keystone hierarchy viewer — bracket tree style, kept from the original UI
// but refined typographically.

function HierarchyViewer({ data, selectedId, onSelect, scale = 1 }) {
  const D = data || window.CS_DATA;
  const taxonomies = D.taxonomies;
  const classes = D.classes;

  // Build rendered rows: taxonomy headers + their classes (ordered by parent)
  const rows = [];
  taxonomies.forEach((tax) => {
    rows.push({ kind: "tax", node: tax, depth: 0, domain: tax.domain });
    const taxClasses = classes.filter((c) => c.taxonomy === tax.id);
    const roots = taxClasses.filter((c) => !c.parent);
    const visit = (cls, depth) => {
      rows.push({ kind: "class", node: cls, depth, domain: cls.domain });
      taxClasses.filter((c) => c.parent === cls.id).forEach((child) => visit(child, depth + 1));
    };
    roots.forEach((r) => visit(r, 1));
  });

  return (
    <div className="kg-tree" style={{ fontSize: 12.5 * scale }}>
      {rows.map((r, i) => {
        const id = r.node.id;
        const desc = r.kind === "tax" ? r.node.description : r.node.definition;
        const label = r.node.title;
        const isTax = r.kind === "tax";
        return (
          <div key={id} className="kg-row">
            <div className={"kg-cell kg-cell-l"} data-depth={r.depth}>
              <div
                className={"kg-node" + (selectedId === id ? " selected" : "")}
                data-domain={r.domain}
                onClick={() => onSelect && onSelect(r.node, r.kind)}
                style={isTax ? { fontWeight: 600, background: "var(--canvas-bg-2)" } : null}
              >
                <span className="swatch"></span>
                <span>{label}</span>
                {!isTax && r.node.individuals != null && (
                  <span className="badge-tiny">{r.node.individuals}</span>
                )}
                {isTax && <span className="badge-tiny">{r.node.classes} cls</span>}
              </div>
            </div>
            <div className="kg-desc">{desc}</div>
          </div>
        );
      })}
    </div>
  );
}

window.HierarchyViewer = HierarchyViewer;
