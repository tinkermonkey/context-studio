
interface BreadcrumbItem {
  label: string
  href?: string
  onClick?: () => void
}

interface TopbarProps extends React.HTMLAttributes<HTMLDivElement> {
  breadcrumbs?: BreadcrumbItem[]
  searchPlaceholder?: string
  onSearch?: (query: string) => void
  /** Content rendered before the breadcrumbs (e.g. workspace switcher pill). */
  leadingContent?: React.ReactNode
  /** Optional keyboard-shortcut glyph rendered inside the search box on the right. */
  searchHint?: React.ReactNode
}

const Topbar = React.forwardRef<HTMLDivElement, TopbarProps>(
  (
    {
      breadcrumbs,
      searchPlaceholder = 'Search…',
      onSearch,
      leadingContent,
      searchHint,
      children,
      className = '',
      ...props
    },
    ref
  ) => {
    const classNames = ['topbar', className].filter(Boolean).join(' ')
    const lastIndex = breadcrumbs ? breadcrumbs.length - 1 : -1

    return (
      <div ref={ref} className={classNames} {...props}>
        {leadingContent && <div className="topbar__leading">{leadingContent}</div>}
        <div className="topbar__breadcrumbs">
          {breadcrumbs && breadcrumbs.length > 0 && (
            <nav className="breadcrumbs" aria-label="Breadcrumb">
              {breadcrumbs.map((crumb, index) => (
                <React.Fragment key={index}>
                  {index > 0 && <span className="breadcrumbs__separator" aria-hidden="true">/</span>}
                  {crumb.href ? (
                    <a
                      href={crumb.href}
                      className="breadcrumbs__link"
                      aria-current={index === lastIndex ? 'page' : undefined}
                    >
                      {crumb.label}
                    </a>
                  ) : crumb.onClick ? (
                    <button
                      type="button"
                      className="breadcrumbs__link breadcrumbs__link--button"
                      onClick={crumb.onClick}
                      aria-current={index === lastIndex ? 'page' : undefined}
                    >
                      {crumb.label}
                    </button>
                  ) : (
                    <span
                      className="breadcrumbs__link breadcrumbs__link--static"
                      aria-current={index === lastIndex ? 'page' : undefined}
                    >
                      {crumb.label}
                    </span>
                  )}
                </React.Fragment>
              ))}
            </nav>
          )}
        </div>

        <div className="topbar__actions">
          {onSearch && (
            <div className="topbar__search-wrap">
              <input
                type="search"
                placeholder={searchPlaceholder}
                aria-label={searchPlaceholder}
                className="topbar__search"
                onChange={e => onSearch(e.target.value)}
              />
              {searchHint && <span className="topbar__search-hint">{searchHint}</span>}
            </div>
          )}
          {children}
        </div>
      </div>
    )
  }
)

Topbar.displayName = 'Topbar'



// --- Babel-standalone: expose runtime values to window ---
window.Topbar = Topbar;
