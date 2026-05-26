
interface VersionPillProps extends React.HTMLAttributes<HTMLSpanElement> {
  children: React.ReactNode
}

const VersionPill = React.forwardRef<HTMLSpanElement, VersionPillProps>(
  ({ className = '', children, ...props }, ref) => {
    const classNames = ['version-pill', className]
      .filter(Boolean)
      .join(' ')

    return (
      <span ref={ref} className={classNames} {...props}>
        {children}
      </span>
    )
  }
)

VersionPill.displayName = 'VersionPill'



// --- Babel-standalone: expose runtime values to window ---
window.VersionPill = VersionPill;
