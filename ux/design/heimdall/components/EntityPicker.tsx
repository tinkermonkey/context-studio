import React, { useEffect, useImperativeHandle, useRef, useState } from 'react'
import './EntityPicker.css'
import { Icon } from './Icon'
import { Chip } from './Chip'
import type { StatusColor } from './statusColors'

export interface EntityPickerResult {
  id: string
  label: string
  domain?: string
  domainColor?: StatusColor
}

export interface EntityPickerProps
  extends Omit<
    React.HTMLAttributes<HTMLDivElement>,
    'onChange' | 'onSelect' | 'results'
  > {
  query: string
  onQueryChange: (query: string) => void
  results?: EntityPickerResult[]
  onSelect: (result: EntityPickerResult) => void
  onClear: () => void
  placeholder?: string
  disabled?: boolean
  inputId?: string
}

export const EntityPicker = React.forwardRef<HTMLDivElement, EntityPickerProps>(
  ({
    query,
    onQueryChange,
    results = [],
    onSelect,
    onClear,
    placeholder = 'Search entities...',
    disabled = false,
    inputId,
    className,
    ...props
  }, ref) => {
    const [isOpen, setIsOpen] = useState(false)
    const [selectedIndex, setSelectedIndex] = useState(0)
    const inputRef = useRef<HTMLInputElement>(null)
    const containerRef = useRef<HTMLDivElement>(null)
    const listboxId = React.useId()
    const getOptionId = (id: string) => `${listboxId}-option-${id}`

    useEffect(() => {
      if (results.length === 0) {
        setSelectedIndex(0)
      } else {
        setSelectedIndex((prev) =>
          prev >= results.length ? results.length - 1 : prev
        )
      }
    }, [results])

    useEffect(() => {
      const container = containerRef.current
      const handleClickOutside = (e: MouseEvent) => {
        if (container && !container.contains(e.target as Node)) {
          setIsOpen(false)
        }
      }

      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }, [])

    useEffect(() => {
      const container = containerRef.current
      if (!container || !isOpen) return

      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          e.preventDefault()
          setIsOpen(false)
        } else if (e.key === 'ArrowDown') {
          e.preventDefault()
          if (results.length > 0) {
            setSelectedIndex((i) => (i + 1) % results.length)
          }
        } else if (e.key === 'ArrowUp') {
          e.preventDefault()
          if (results.length > 0) {
            setSelectedIndex((i) => (i - 1 + results.length) % results.length)
          }
        } else if (e.key === 'Enter') {
          e.preventDefault()
          if (results[selectedIndex]) {
            onSelect(results[selectedIndex])
            setIsOpen(false)
          }
        }
      }

      container.addEventListener('keydown', handleKeyDown)
      return () => container.removeEventListener('keydown', handleKeyDown)
    }, [isOpen, results, selectedIndex, onSelect])

    useImperativeHandle(ref, () => containerRef.current as HTMLDivElement)

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      if (disabled) return
      onQueryChange(e.target.value)
      setIsOpen(true)
      setSelectedIndex(0)
    }

    const handleInputFocus = () => {
      if (disabled) return
      if (query.length > 0 && results.length > 0) {
        setIsOpen(true)
      }
    }

    const handleClear = () => {
      onClear()
      setIsOpen(false)
      inputRef.current?.focus()
    }

    const handleResultClick = (result: EntityPickerResult) => {
      onSelect(result)
      setIsOpen(false)
    }

    return (
      <div ref={containerRef} className={['entity-picker', disabled && 'entity-picker--disabled', className].filter(Boolean).join(' ')} {...props}>
        <div className="entity-picker__input-wrapper">
          <input
            ref={inputRef}
            id={inputId}
            type="text"
            role="combobox"
            aria-autocomplete="list"
            aria-expanded={isOpen && results.length > 0}
            aria-controls={listboxId}
            aria-activedescendant={isOpen && results[selectedIndex] ? getOptionId(results[selectedIndex].id) : undefined}
            className="entity-picker__input"
            placeholder={placeholder}
            value={query}
            disabled={disabled}
            onChange={handleInputChange}
            onFocus={handleInputFocus}
            data-testid="entity-picker-input"
          />
          {query && !disabled && (
            <button
              type="button"
              className="entity-picker__clear"
              onClick={handleClear}
              aria-label="Clear search"
              data-testid="entity-picker-clear"
            >
              <Icon name="x" size={16} />
            </button>
          )}
        </div>

        {isOpen && results.length > 0 && (
          <div
            id={listboxId}
            role="listbox"
            className="entity-picker__dropdown"
            data-testid="entity-picker-dropdown"
          >
            {results.map((result, index) => (
              <div
                key={result.id}
                id={getOptionId(result.id)}
                role="option"
                aria-selected={index === selectedIndex}
                className={[
                  'entity-picker__result',
                  index === selectedIndex && 'entity-picker__result--selected',
                ]
                  .filter(Boolean)
                  .join(' ')}
                onMouseDown={(e) => { e.preventDefault(); handleResultClick(result) }}
                data-testid={`entity-picker-result-${result.id}`}
              >
                {result.domain && result.domainColor && (
                  <Chip variant={result.domainColor} className="entity-picker__badge">
                    {result.domain}
                  </Chip>
                )}
                <span className="entity-picker__label">{result.label}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }
)

EntityPicker.displayName = 'EntityPicker'

export default EntityPicker
