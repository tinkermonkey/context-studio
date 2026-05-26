import React from 'react'
import './AppTitle.css'

export interface AppTitleProps extends React.HTMLAttributes<HTMLDivElement> {
  title: string
  version?: string
  collapsed?: boolean
}

export const AppTitle = React.forwardRef<HTMLDivElement, AppTitleProps>(
  ({ title, version, collapsed = false, className = '', 'aria-label': ariaLabel, ...props }, ref) => {
    const classNames = [
      'app-title',
      collapsed && 'app-title--collapsed',
      className,
    ]
      .filter(Boolean)
      .join(' ')

    const computedLabel = ariaLabel ?? (version ? `${title} ${version}` : title)

    return (
      <div ref={ref} className={classNames} aria-label={computedLabel} role="banner" {...props}>
        <div className="app-title__mark" aria-hidden="true" />
        {!collapsed && (
          <div className="app-title__text">
            <div className="app-title__name">{title}</div>
            {version && <span className="app-title__version">{version}</span>}
          </div>
        )}
      </div>
    )
  }
)

AppTitle.displayName = 'AppTitle'

export default AppTitle
