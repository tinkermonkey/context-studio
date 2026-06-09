
interface StatGridProps extends React.HTMLAttributes<HTMLDivElement> {
  columns?: number
  children: React.ReactNode
}

const StatGrid = React.forwardRef<HTMLDivElement, StatGridProps>(
  ({ columns = 4, className = '', children, ...props }, ref) => {
    const classNames = ['stat-grid', `stat-grid--cols-${columns}`, className]
      .filter(Boolean)
      .join(' ')

    return (
      <div
        ref={ref}
        className={classNames}
        {...props}
      >
        {children}
      </div>
    )
  }
)

StatGrid.displayName = 'StatGrid'



// --- Babel-standalone: expose runtime values to window ---
window.StatGrid = StatGrid;
