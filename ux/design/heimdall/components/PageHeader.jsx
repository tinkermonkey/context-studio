
interface PageHeaderProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Status context above the title. Accepts arbitrary content (chips, mono spans, health dots),
   *  not just a label string. A plain string renders as the uppercase mono eyebrow. */
  eyebrow?: React.ReactNode
  title: string
  idChip?: string
  subtitle?: string
  actions?: React.ReactNode
}

const PageHeader = React.forwardRef<HTMLDivElement, PageHeaderProps>(
  ({ eyebrow, title, idChip, subtitle, actions, className = '', ...props }, ref) => {
    const classNames = ['page-header', className].filter(Boolean).join(' ')

    return (
      <div ref={ref} className={classNames} role="banner" {...props}>
        <div className="page-header__text">
          {eyebrow && (
            <div className="page-header__eyebrow" data-testid="page-header-eyebrow">
              {eyebrow}
            </div>
          )}
          <h1 className="page-header__title" data-testid="page-header-title">
            {title}
            {idChip && (
              <Chip form="id-tag" className="page-header__id-chip" data-testid="page-header-id-chip">
                {idChip}
              </Chip>
            )}
          </h1>
          {subtitle && (
            <div className="page-header__subtitle" data-testid="page-header-subtitle">
              {subtitle}
            </div>
          )}
        </div>
        {actions && <div className="page-header__actions" data-testid="page-header-actions">{actions}</div>}
      </div>
    )
  }
)

PageHeader.displayName = 'PageHeader'



// --- Babel-standalone: expose runtime values to window ---
window.PageHeader = PageHeader;
