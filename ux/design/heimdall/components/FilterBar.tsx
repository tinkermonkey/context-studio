import React, { useState } from 'react'
import { Icon } from './Icon'
import { Chip } from './Chip'
import './FilterBar.css'

export interface FilterChip {
  id: string
  label: string
}

export interface FilterBarProps extends React.HTMLAttributes<HTMLDivElement> {
  filters?: FilterChip[]
  value?: string
  defaultValue?: string
  onSearchChange?: (query: string) => void
  onFilterRemove?: (filterId: string) => void
  onClearAll?: () => void
  searchPlaceholder?: string
  children?: React.ReactNode
  showingCount?: number
  totalCount?: number
}

export const FilterBar = React.forwardRef<HTMLDivElement, FilterBarProps>(
  (
    {
      filters = [],
      value,
      defaultValue = '',
      onSearchChange,
      onFilterRemove,
      onClearAll,
      searchPlaceholder = 'Search...',
      children,
      showingCount,
      totalCount,
      className = '',
      ...props
    },
    ref
  ) => {
    const isControlled = value !== undefined
    const [internalValue, setInternalValue] = useState(defaultValue)
    const searchValue = isControlled ? value : internalValue

    const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const next = e.target.value
      if (!isControlled) setInternalValue(next)
      onSearchChange?.(next)
    }

    const handleClearAll = () => {
      if (!isControlled) setInternalValue('')
      onClearAll?.()
    }

    const classNames = ['filter-bar', className].filter(Boolean).join(' ')
    const hasChildren = React.Children.count(children) > 0
    const hasCaption = showingCount !== undefined && totalCount !== undefined

    return (
      <div ref={ref} className={classNames} data-testid="filter-bar" {...props}>
        <div className="filter-bar__controls">
          <div className="filter-bar__search-wrapper" role="search">
            <Icon name="search" size={16} className="filter-bar__search-icon" />
            <input
              type="text"
              aria-label="Search"
              placeholder={searchPlaceholder}
              value={searchValue}
              onChange={handleSearchChange}
              className="filter-bar__search-input"
              data-testid="filter-bar-search"
            />
          </div>
          {hasChildren && (
            <div className="filter-bar__children">
              {children}
            </div>
          )}
          {hasCaption && (
            <div className="filter-bar__caption">
              Showing {showingCount} of {totalCount}
            </div>
          )}
        </div>
        {filters.length > 0 && (
          <div className="filter-bar__chips" data-testid="filter-bar-chips">
            {onClearAll && (
              <button
                type="button"
                className="filter-bar__clear-all"
                onClick={handleClearAll}
                data-testid="filter-bar-clear-all"
              >
                Clear all
              </button>
            )}
            {filters.map(filter => (
              <Chip
                key={filter.id}
                variant="neutral"
                className="filter-bar__chip"
                data-testid={`filter-chip-${filter.id}`}
              >
                <span className="filter-bar__chip-label">{filter.label}</span>
                <button
                  type="button"
                  className="filter-bar__chip-close"
                  onClick={() => onFilterRemove?.(filter.id)}
                  aria-label={`Remove ${filter.label} filter`}
                  data-testid={`filter-chip-close-${filter.id}`}
                >
                  <Icon name="x" size={14} />
                </button>
              </Chip>
            ))}
          </div>
        )}
      </div>
    )
  }
)

FilterBar.displayName = 'FilterBar'

export default FilterBar
