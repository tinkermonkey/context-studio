import React from 'react'
import './RelationshipBuilder.css'
import { Select } from './Select'
import { EntityPicker, type EntityPickerResult } from './EntityPicker'

export interface RelationshipBuilderValue {
  source?: EntityPickerResult
  predicate: string
  target?: EntityPickerResult
}

export interface RelationshipBuilderProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, 'onChange'> {
  value: RelationshipBuilderValue
  onChange: (value: RelationshipBuilderValue) => void
  sourceResults?: EntityPickerResult[]
  targetResults?: EntityPickerResult[]
  sourceQuery: string
  onSourceQueryChange: (query: string) => void
  targetQuery: string
  onTargetQueryChange: (query: string) => void
  predicates?: string[]
  onSourceClear: () => void
  onTargetClear: () => void
  disabled?: boolean
}

export const RelationshipBuilder = React.forwardRef<HTMLDivElement, RelationshipBuilderProps>(
  ({
    value,
    onChange,
    sourceResults = [],
    targetResults = [],
    sourceQuery,
    onSourceQueryChange,
    targetQuery,
    onTargetQueryChange,
    predicates = ['contains', 'relates to', 'depends on', 'is used by'],
    onSourceClear,
    onTargetClear,
    disabled = false,
    className,
    ...props
  }, ref) => {
    const id = React.useId()
    const sourceId = `${id}-source`
    const predicateId = `${id}-predicate`
    const targetId = `${id}-target`

    const handleSourceSelect = React.useCallback((result: EntityPickerResult) => {
      onChange({ ...value, source: result })
      onSourceQueryChange('')
    }, [onChange, onSourceQueryChange, value])

    const handleTargetSelect = React.useCallback((result: EntityPickerResult) => {
      onChange({ ...value, target: result })
      onTargetQueryChange('')
    }, [onChange, onTargetQueryChange, value])

    const handlePredicateChange = React.useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
      onChange({ ...value, predicate: e.target.value })
    }, [onChange, value])

    return (
      <div ref={ref} className={['relationship-builder', className].filter(Boolean).join(' ')} data-testid="relationship-builder" {...props}>
        <div className="relationship-builder__column">
          <label htmlFor={sourceId} className="relationship-builder__label">Source</label>
          <EntityPicker
            inputId={sourceId}
            query={sourceQuery}
            onQueryChange={onSourceQueryChange}
            results={sourceResults}
            onSelect={handleSourceSelect}
            onClear={onSourceClear}
            placeholder="Search source entity..."
            disabled={disabled}
          />
          {value.source && (
            <div className="relationship-builder__selected" data-testid="source-selected">
              {value.source.domain && (
                <span className="relationship-builder__domain">{value.source.domain}</span>
              )}
              <span>{value.source.label}</span>
            </div>
          )}
        </div>

        <div className="relationship-builder__column">
          <label htmlFor={predicateId} className="relationship-builder__label">Predicate</label>
          <Select
            id={predicateId}
            value={value.predicate}
            onChange={handlePredicateChange}
            disabled={disabled}
            data-testid="predicate-select"
          >
            <option value="">Select relation type...</option>
            {predicates.map((pred) => (
              <option key={pred} value={pred}>
                {pred}
              </option>
            ))}
          </Select>
        </div>

        <div className="relationship-builder__column">
          <label htmlFor={targetId} className="relationship-builder__label">Target</label>
          <EntityPicker
            inputId={targetId}
            query={targetQuery}
            onQueryChange={onTargetQueryChange}
            results={targetResults}
            onSelect={handleTargetSelect}
            onClear={onTargetClear}
            placeholder="Search target entity..."
            disabled={disabled}
          />
          {value.target && (
            <div className="relationship-builder__selected" data-testid="target-selected">
              {value.target.domain && (
                <span className="relationship-builder__domain">{value.target.domain}</span>
              )}
              <span>{value.target.label}</span>
            </div>
          )}
        </div>
      </div>
    )
  }
)

RelationshipBuilder.displayName = 'RelationshipBuilder'

export default RelationshipBuilder
