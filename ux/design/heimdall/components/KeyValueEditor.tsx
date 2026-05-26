import React from 'react'
import './KeyValueEditor.css'
import { Button } from './Button'
import { TextInput } from './TextInput'
import { Select } from './Select'
import { Icon } from './Icon'

export interface KeyValueRow {
  id: string
  key: string
  value: string
  datatype?: string
}

export interface KeyValueEditorProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, 'onChange'> {
  rows: KeyValueRow[]
  onChange: (rows: KeyValueRow[]) => void
  datatypeColumn?: boolean
  datatypes?: string[]
  disabled?: boolean
  keyPlaceholder?: string
  valuePlaceholder?: string
  addLabel?: string
}

export const KeyValueEditor = React.forwardRef<HTMLDivElement, KeyValueEditorProps>(
  ({ rows, onChange, datatypeColumn = false, datatypes = ['string', 'number', 'boolean'], disabled = false, keyPlaceholder = 'Key', valuePlaceholder = 'Value', addLabel = 'Add row', className, ...props }, ref) => {
    const rowIdPrefix = React.useId()
    const rowIdCounter = React.useRef(0)

    const handleKeyChange = (id: string, newKey: string) => {
      onChange(
        rows.map((row) =>
          row.id === id ? { ...row, key: newKey } : row
        )
      )
    }

    const handleValueChange = (id: string, newValue: string) => {
      onChange(
        rows.map((row) =>
          row.id === id ? { ...row, value: newValue } : row
        )
      )
    }

    const handleDatatypeChange = (id: string, newDatatype: string) => {
      onChange(
        rows.map((row) =>
          row.id === id ? { ...row, datatype: newDatatype } : row
        )
      )
    }

    const handleRemoveRow = (id: string) => {
      onChange(rows.filter((row) => row.id !== id))
    }

    const handleAddRow = () => {
      const newRow: KeyValueRow = {
        id: `${rowIdPrefix}-${rowIdCounter.current++}`,
        key: '',
        value: '',
        ...(datatypeColumn && { datatype: 'string' }),
      }
      onChange([...rows, newRow])
    }

    return (
      <div ref={ref} className={['key-value-editor', datatypeColumn && 'key-value-editor--has-datatype', disabled && 'key-value-editor--disabled', className].filter(Boolean).join(' ')} data-testid="key-value-editor" {...props}>
        <div className="key-value-editor__table">
          <div className="key-value-editor__header">
            <div className="key-value-editor__col key-value-editor__col--key">Key</div>
            <div className="key-value-editor__col key-value-editor__col--value">Value</div>
            {datatypeColumn && (
              <div className="key-value-editor__col key-value-editor__col--datatype">Type</div>
            )}
            <div className="key-value-editor__col key-value-editor__col--actions" />
          </div>

          {rows.map((row) => (
            <div
              key={row.id}
              className="key-value-editor__row"
              data-testid={`key-value-row-${row.id}`}
            >
              <TextInput
                className="key-value-editor__input"
                placeholder={keyPlaceholder}
                value={row.key}
                onChange={(e) => handleKeyChange(row.id, e.target.value)}
                disabled={disabled}
                data-testid={`key-input-${row.id}`}
              />
              <TextInput
                className="key-value-editor__input"
                placeholder={valuePlaceholder}
                value={row.value}
                onChange={(e) => handleValueChange(row.id, e.target.value)}
                disabled={disabled}
                data-testid={`value-input-${row.id}`}
              />
              {datatypeColumn && (
                <Select
                  className="key-value-editor__input key-value-editor__select"
                  value={row.datatype || 'string'}
                  onChange={(e) => handleDatatypeChange(row.id, e.target.value)}
                  disabled={disabled}
                  data-testid={`datatype-select-${row.id}`}
                >
                  {datatypes.map((dt) => (
                    <option key={dt} value={dt}>
                      {dt}
                    </option>
                  ))}
                </Select>
              )}
              <button
                type="button"
                className="key-value-editor__remove-btn"
                onClick={() => handleRemoveRow(row.id)}
                aria-label="Remove row"
                disabled={disabled}
                data-testid={`remove-row-${row.id}`}
              >
                <Icon name="trash" size={16} />
              </button>
            </div>
          ))}
        </div>

        <Button
          variant="ghost"
          size="sm"
          className="key-value-editor__add-btn"
          onClick={handleAddRow}
          disabled={disabled}
          data-testid="add-row-btn"
        >
          <Icon name="plus" size={16} />
          {addLabel}
        </Button>
      </div>
    )
  }
)

KeyValueEditor.displayName = 'KeyValueEditor'

export default KeyValueEditor
