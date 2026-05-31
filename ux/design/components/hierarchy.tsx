// =========================================================================
// Hierarchy viewer — taxonomy → concept_scheme → class tree with descriptions
// =========================================================================
function HierarchyViewer({ data, selectedId, onSelect, includeSchemes = true }) {
  const D = data || window.CS_DATA;

  const rows = [];
  D.taxonomies.forEach((tax) => {
    rows.push({ kind: "taxonomy", node: tax, depth: 0, domain: tax.domain });
    const schemes = D.concept_schemes.filter((s) => s.taxonomy_id === tax.id);
    schemes.forEach((sch) => {
      if (includeSchemes) {
        rows.push({ kind: "scheme", node: sch, depth: 1, domain: sch.domain });
      }
      const taxClasses = D.classes.filter((c) => c.concept_scheme_id === sch.id);
      const roots = taxClasses.filter((c) => !c.parent_class_id);
      const visit = (cls, depth) => {
        rows.push({ kind: "class", node: cls, depth, domain: cls.domain });
        taxClasses
          .filter((c) => c.parent_class_id === cls.id)
          .forEach((child) => visit(child, depth + 1));
      };
      roots.forEach((r) => visit(r, includeSchemes ? 2 : 1));
    });
  });

  return (
    <div className="kg-tree">
      {rows.map((r) => {
        const id = r.node.id;
        const label = r.node.title;
        const desc = r.node.description;
        return (
          <div key={id} className="hier-row">
            <div className="hier-cell" data-depth={r.depth}>
              <div
                className={"kg-node-pill " + r.kind + (selectedId === id ? " selected" : "")}
                data-domain={r.domain}
                onClick={() => onSelect && onSelect(r.node, r.kind)}
              >
                <span className="swatch"></span>
                <span>{label}</span>
                {r.kind === "taxonomy" && <span className="badge-tiny">{r.node.classes} cls</span>}
                {r.kind === "scheme" && <span className="badge-tiny">{r.node.classes} cls</span>}
                {r.kind === "class" && r.node.individuals != null && (
                  <span className="badge-tiny">{r.node.individuals} ind</span>
                )}
              </div>
            </div>
            <div className="desc">{desc}</div>
          </div>
        );
      })}
    </div>
  );
}

window.HierarchyViewer = HierarchyViewer;
