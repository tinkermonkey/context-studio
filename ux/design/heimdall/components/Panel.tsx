import React from 'react'
import './Panel.css'

export interface PanelProps extends React.HTMLAttributes<HTMLDivElement> {
  title?: string
  subtitle?: string
  headerAction?: React.ReactNode
  footer?: React.ReactNode
  bordered?: boolean
  noPadding?: boolean
  children?: React.ReactNode
}

export const Panel = React.forwardRef<HTMLDivElement, PanelProps>(
  ({ title, subtitle, headerAction, footer, bordered = true, noPadding = false, className = '', children, ...props }, ref) => {
    const classNames = ['panel', !bordered && 'panel--no-border', className]
      .filter(Boolean)
      .join(' ')

    return (
      <div ref={ref} className={classNames} {...props}>
        {(title || subtitle || headerAction) && (
          <div className="panel__header">
            <div className="panel__header-left">
              {title && <div className="panel__title">{title}</div>}
              {subtitle && <div className="panel__subtitle">{subtitle}</div>}
            </div>
            {headerAction && <div className="panel__header-action">{headerAction}</div>}
          </div>
        )}
        {children != null && (
          <div className={noPadding ? 'panel__body panel__body--no-padding' : 'panel__body'}>{children}</div>
        )}
        {footer && <div className="panel__footer">{footer}</div>}
      </div>
    )
  }
)

Panel.displayName = 'Panel'

export default Panel
