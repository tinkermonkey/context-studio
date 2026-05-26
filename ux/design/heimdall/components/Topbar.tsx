import React from 'react'
import './Topbar.css'

export interface BreadcrumbItem {
  label: string
  href?: string
  onClick?: () => void
}

export interface TopbarProps extends React.HTMLAttributes<HTMLDivElement> {
  breadcrumbs?: BreadcrumbItem[]
  searchPlaceholder?: string
  onSearch?: (query: string) => void
}

export const Topbar = React.forwardRef<HTMLDivElement, TopbarProps>(
  (
    {
      breadcrumbs,
      searchPlaceholder = 'Search…',
      onSearch,
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
            <input
              type="search"
              placeholder={searchPlaceholder}
              aria-label={searchPlaceholder}
              className="topbar__search"
              onChange={e => onSearch(e.target.value)}
            />
          )}
          {children}
        </div>
      </div>
    )
  }
)

Topbar.displayName = 'Topbar'

export default Topbar
