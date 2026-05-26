import React from 'react'
import './GraphInspector.css'

export interface GraphNodeMetadata {
  id: string
  title: string
  kind?: string
  domain?: string
  description?: string
  metadata?: Record<string, string | number | boolean | null | undefined>
}

export interface RelationshipLink {
  id: string
  target: string
  targetTitle: string
  targetDomain?: string
  predicate: string
  direction: 'in' | 'out'
}

export interface GraphInspectorProps extends React.HTMLAttributes<HTMLDivElement> {
  node?: GraphNodeMetadata | null
  relationships?: RelationshipLink[]
  onNodeSelect?: (nodeId: string) => void
  emptyStateText?: string
}

export const GraphInspector = React.forwardRef<HTMLDivElement, GraphInspectorProps>(
  (
    {
      node,
      relationships = [],
      onNodeSelect,
      emptyStateText = 'Select a node to inspect.',
      className = '',
      ...props
    },
    ref
  ) => {
    const classNames = ['graph-inspector', className].filter(Boolean).join(' ')

    if (!node) {
      return (
        <div ref={ref} className={classNames} {...props}>
          <div className="graph-inspector__empty" data-testid="inspector-empty">
            {emptyStateText}
          </div>
        </div>
      )
    }

    const outgoing = relationships.filter((r) => r.direction === 'out')
    const incoming = relationships.filter((r) => r.direction === 'in')

    return (
      <div ref={ref} className={classNames} {...props}>
        <div className="graph-inspector__head">
          <div className="graph-inspector__head-eyebrow">
            {node.kind && <span className="graph-inspector__badge">{node.kind}</span>}
            {node.domain && (
              <span className={`graph-inspector__badge graph-inspector__badge--${node.domain}`}>
                {node.domain}
              </span>
            )}
          </div>
          <div className="graph-inspector__title" data-testid="inspector-title">
            {node.title}
          </div>
          <div className="graph-inspector__id" data-testid="inspector-id">
            {node.id}
          </div>
        </div>

        <div className="graph-inspector__body">
          {node.description && (
            <p className="graph-inspector__description" data-testid="inspector-description">
              {node.description}
            </p>
          )}

          {node.metadata && Object.keys(node.metadata).length > 0 && (
            <dl className="graph-inspector__kv" data-testid="inspector-metadata">
              {Object.entries(node.metadata).map(([key, value]) => (
                <React.Fragment key={key}>
                  <dt>{key}</dt>
                  <dd>{String(value)}</dd>
                </React.Fragment>
              ))}
            </dl>
          )}

          {outgoing.length > 0 && (
            <>
              <div className="graph-inspector__section-label">Outgoing · {outgoing.length}</div>
              <ul className="graph-inspector__rels" data-testid="inspector-outgoing">
                {outgoing.map((rel) => (
                  <li key={rel.id} className="graph-inspector__rel">
                    <span className="graph-inspector__rel-dir graph-inspector__rel-dir--out">
                      →
                    </span>
                    <span className="graph-inspector__rel-pred">{rel.predicate}</span>
                    <button
                      type="button"
                      className="graph-inspector__rel-target"
                      data-domain={rel.targetDomain}
                      onClick={() => onNodeSelect?.(rel.target)}
                      aria-label={`Navigate to ${rel.targetTitle}`}
                      data-testid={`inspector-rel-${rel.id}`}
                    >
                      <span className="graph-inspector__rel-swatch"></span>
                      <span>{rel.targetTitle}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}

          {incoming.length > 0 && (
            <>
              <div className="graph-inspector__section-label">Incoming · {incoming.length}</div>
              <ul className="graph-inspector__rels" data-testid="inspector-incoming">
                {incoming.map((rel) => (
                  <li key={rel.id} className="graph-inspector__rel">
                    <span className="graph-inspector__rel-dir graph-inspector__rel-dir--in">
                      ←
                    </span>
                    <span className="graph-inspector__rel-pred">{rel.predicate}</span>
                    <button
                      type="button"
                      className="graph-inspector__rel-target"
                      data-domain={rel.targetDomain}
                      onClick={() => onNodeSelect?.(rel.target)}
                      aria-label={`Navigate to ${rel.targetTitle}`}
                      data-testid={`inspector-rel-${rel.id}`}
                    >
                      <span className="graph-inspector__rel-swatch"></span>
                      <span>{rel.targetTitle}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}

          {relationships.length === 0 && (
            <div className="graph-inspector__empty-mini">No relationships yet.</div>
          )}
        </div>
      </div>
    )
  }
)

GraphInspector.displayName = 'GraphInspector'

export default GraphInspector
