
interface KVGridRow {
  key: string
  value: React.ReactNode
}

interface KVGridProps extends React.HTMLAttributes<HTMLDListElement> {
  rows?: KVGridRow[]
  keyWidth?: number | string
}

const KVGrid = React.forwardRef<HTMLDListElement, KVGridProps>(
  ({ rows = [], keyWidth, className = '', style, ...props }, ref) => {
    const classNames = ['kv-grid', className].filter(Boolean).join(' ')
    const gridStyle: React.CSSProperties | undefined = keyWidth
      ? { ...style, gridTemplateColumns: `${typeof keyWidth === 'number' ? `${keyWidth}px` : keyWidth} 1fr` }
      : style

    return (
      <dl ref={ref} className={classNames} style={gridStyle} {...props}>
        {rows.map((row) => (
          <React.Fragment key={row.key}>
            <dt className="kv-grid__key">{row.key}</dt>
            <dd className="kv-grid__value">{row.value}</dd>
          </React.Fragment>
        ))}
      </dl>
    )
  }
)

KVGrid.displayName = 'KVGrid'



// --- Babel-standalone: expose runtime values to window ---
window.KVGrid = KVGrid;
