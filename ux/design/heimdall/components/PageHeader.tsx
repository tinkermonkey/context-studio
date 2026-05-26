import React from 'react'
import { Chip } from './Chip'
import './PageHeader.css'

export interface PageHeaderProps extends React.HTMLAttributes<HTMLDivElement> {
  eyebrow?: string
  title: string
  idChip?: string
  subtitle?: string
  actions?: React.ReactNode
}

export const PageHeader = React.forwardRef<HTMLDivElement, PageHeaderProps>(
  ({ eyebrow, title, idChip, subtitle, actions, className = '', ...props }, ref) => {
    const classNames = ['page-header', className].filter(Boolean).join(' ')

    return (
      <div ref={ref} className={classNames} role="banner" {...props}>
        {eyebrow && (
          <div className="page-header__eyebrow" data-testid="page-header-eyebrow">
            {eyebrow}
          </div>
        )}
        <div className="page-header__title-row">
          <h1 className="page-header__title" data-testid="page-header-title">
            {title}
            {idChip && (
              <Chip form="id-tag" className="page-header__id-chip" data-testid="page-header-id-chip">
                {idChip}
              </Chip>
            )}
          </h1>
          {actions && <div className="page-header__actions" data-testid="page-header-actions">{actions}</div>}
        </div>
        {subtitle && (
          <div className="page-header__subtitle" data-testid="page-header-subtitle">
            {subtitle}
          </div>
        )}
      </div>
    )
  }
)

PageHeader.displayName = 'PageHeader'

export default PageHeader
