import React from 'react'
import './HierarchyRow.css'

export type HierarchyKind = 'taxonomy' | 'scheme' | 'class'
export type HierarchyDomain = 'life' | 'climate' | 'software' | 'default' | (string & {})

export interface HierarchyRowProps extends React.HTMLAttributes<HTMLDivElement> {
  depth?: number
  domain: HierarchyDomain
  kind: HierarchyKind
  label: string
  meta?: string
  description?: string
  selected?: boolean
  onSelect?: () => void
  showKind?: boolean
}

const domainColorMap: Record<string, string> = {
  life: 'var(--dom-life)',
  climate: 'var(--dom-climate)',
  software: 'var(--dom-software)',
  default: 'var(--dom-default)',
}

export const HierarchyRow = React.forwardRef<HTMLDivElement, HierarchyRowProps>(
  (
    {
      depth = 0,
      domain,
      kind,
      label,
      meta,
      description,
      selected = false,
      onSelect,
      showKind = true,
      className = '',
      ...props
    },
    ref
  ) => {
    const domainColor = domainColorMap[domain] || domainColorMap.default
    const classNames = ['hierarchy-row', selected && 'selected', onSelect && 'interactive', className]
      .filter(Boolean)
      .join(' ')

    const handleKeyDown = React.useCallback(
      (event: React.KeyboardEvent<HTMLDivElement>) => {
        if ((event.key === 'Enter' || event.key === ' ') && onSelect) {
          event.preventDefault()
          onSelect()
        }
      },
      [onSelect]
    )

    return (
      <div
        ref={ref}
        className={classNames}
        role={onSelect ? 'button' : undefined}
        tabIndex={onSelect ? 0 : undefined}
        aria-pressed={onSelect ? selected : undefined}
        onClick={onSelect}
        onKeyDown={onSelect ? handleKeyDown : undefined}
        style={{
          '--hierarchy-depth': depth,
          '--domain-color': domainColor,
        } as React.CSSProperties & { '--hierarchy-depth': number; '--domain-color': string }}
        {...props}
      >
        <div className="hierarchy-row__left">
          {depth > 0 && <div className="hierarchy-row__connector" />}
          <div className="hierarchy-row__pill">
            <div className="hierarchy-row__swatch" />
            {showKind && <span className="hierarchy-row__kind">{kind}</span>}
            <span className="hierarchy-row__label">{label}</span>
            {meta && <span className="hierarchy-row__meta">{meta}</span>}
          </div>
        </div>
        {description && (
          <div className="hierarchy-row__right">
            <span className="hierarchy-row__description">{description}</span>
          </div>
        )}
      </div>
    )
  }
)

HierarchyRow.displayName = 'HierarchyRow'

export default HierarchyRow
