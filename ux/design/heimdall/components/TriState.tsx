import React from 'react'
import './TriState.css'

export interface TriStateProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> {
  indeterminate?: boolean
}

export const TriState = React.forwardRef<HTMLInputElement, TriStateProps>(
  ({ indeterminate = false, className = '', 'aria-checked': ariaChecked, ...props }, ref) => {
    const internalRef: React.MutableRefObject<HTMLInputElement | null> =
      React.useRef<HTMLInputElement>(null)

    const mergedRef = React.useCallback(
      (node: HTMLInputElement | null) => {
        internalRef.current = node
        if (typeof ref === 'function') {
          ref(node)
        } else if (ref) {
          ref.current = node
        }
      },
      [ref]
    )

    React.useEffect(() => {
      if (internalRef.current) {
        internalRef.current.indeterminate = indeterminate
      }
    }, [indeterminate])

    const classNames = [
      'tri-state',
      indeterminate && 'tri-state--indeterminate',
      className,
    ]
      .filter(Boolean)
      .join(' ')

    return (
      <input
        ref={mergedRef}
        type="checkbox"
        className={classNames}
        {...props}
        aria-checked={ariaChecked ?? (indeterminate ? 'mixed' : props.checked !== undefined ? Boolean(props.checked) : undefined)}
      />
    )
  }
)

TriState.displayName = 'TriState'

export default TriState
