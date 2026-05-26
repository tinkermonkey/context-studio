import React, { useCallback, useRef } from 'react'
import './SegmentedControl.css'

export interface SegmentedControlOption {
  value: string | number
  label: React.ReactNode
  disabled?: boolean
}

export interface SegmentedControlProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'onChange'> {
  value: string | number
  onChange: (value: string | number) => void
  options: SegmentedControlOption[]
  disabled?: boolean
}

export const SegmentedControl = React.forwardRef<HTMLDivElement, SegmentedControlProps>(
  ({ value, onChange, options, disabled = false, className = '', ...props }, ref) => {
    const classNames = ['segmented-control', disabled ? 'segmented-control--disabled' : '', className]
      .filter(Boolean)
      .join(' ')

    const buttonRefs = useRef<(HTMLButtonElement | null)[]>([])

    const handleKeyDown = useCallback(
      (e: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
        const enabledIndices = options
          .map((o, i) => (o.disabled ? null : i))
          .filter((i): i is number => i !== null)

        const currentPos = enabledIndices.indexOf(index)
        let nextPos: number | undefined

        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
          e.preventDefault()
          nextPos = enabledIndices[(currentPos + 1) % enabledIndices.length]
        } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
          e.preventDefault()
          nextPos = enabledIndices[(currentPos - 1 + enabledIndices.length) % enabledIndices.length]
        }

        if (nextPos !== undefined) {
          buttonRefs.current[nextPos]?.focus()
          onChange(options[nextPos].value)
        }
      },
      [options, onChange]
    )

    const hasMatch = options.some((o) => o.value === value)
    const firstEnabledIndex = options.findIndex((o) => !o.disabled)

    return (
      <div ref={ref} className={classNames} role="radiogroup" {...props}>
        {options.map((option, index) => {
          const isActive = value === option.value
          const tabIndex = isActive ? 0 : (!hasMatch && index === firstEnabledIndex ? 0 : -1)
          return (
            <button
              key={option.value}
              ref={(el) => { buttonRefs.current[index] = el }}
              className={`segmented-control__segment ${isActive ? 'segmented-control__segment--active' : ''}`}
              onClick={() => !disabled && !option.disabled && onChange(option.value)}
              onKeyDown={(e) => handleKeyDown(e, index)}
              type="button"
              role="radio"
              aria-checked={isActive}
              disabled={disabled || option.disabled}
              tabIndex={tabIndex}
            >
              {option.label}
            </button>
          )
        })}
      </div>
    )
  }
)

SegmentedControl.displayName = 'SegmentedControl'

export default SegmentedControl
