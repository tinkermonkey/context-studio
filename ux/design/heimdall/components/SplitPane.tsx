import React, { useState, useRef, useCallback } from 'react'
import './SplitPane.css'

export interface SplitPaneProps extends React.HTMLAttributes<HTMLDivElement> {
  direction?: 'horizontal' | 'vertical'
  initialSplitPercent?: number
  splitPercent?: number
  onSplitChange?: (percent: number) => void
  minSize?: number
  maxSize?: number
  first: React.ReactNode
  second: React.ReactNode
  dividerLabel?: string
}

export const SplitPane = React.forwardRef<HTMLDivElement, SplitPaneProps>(
  ({
    direction = 'horizontal',
    initialSplitPercent = 50,
    splitPercent: controlledPercent,
    onSplitChange,
    minSize = 200,
    maxSize = 800,
    first,
    second,
    dividerLabel,
    className = '',
    ...props
  }, ref) => {
    const [internalPercent, setInternalPercent] = useState(initialSplitPercent)
    const containerRef = useRef<HTMLDivElement>(null)

    const isControlled = controlledPercent !== undefined
    const splitPercent = isControlled ? controlledPercent! : internalPercent

    const clampPercent = useCallback((rawPercent: number, containerSize: number): number => {
      const minPercent = (minSize / containerSize) * 100
      const maxPercent = (maxSize / containerSize) * 100
      return Math.max(minPercent, Math.min(rawPercent, maxPercent))
    }, [minSize, maxSize])

    const setSplit = useCallback((newPercent: number) => {
      if (!isControlled) setInternalPercent(newPercent)
      onSplitChange?.(newPercent)
    }, [isControlled, onSplitChange])

    const mergeRefs = useCallback((refs: Array<React.Ref<HTMLDivElement>>) => {
      return (element: HTMLDivElement | null) => {
        refs.forEach(r => {
          if (typeof r === 'function') {
            r(element)
          } else if (r) {
            (r as React.MutableRefObject<HTMLDivElement | null>).current = element
          }
        })
      }
    }, [])

    const handleMouseDown = useCallback(() => {
      const handleMouseMove = (e: MouseEvent) => {
        if (!containerRef.current) return

        const rect = containerRef.current.getBoundingClientRect()
        const isHorizontal = direction === 'horizontal'

        const position = isHorizontal
          ? e.clientX - rect.left
          : e.clientY - rect.top

        const size = isHorizontal ? rect.width : rect.height
        const rawPercent = (position / size) * 100
        setSplit(clampPercent(rawPercent, size))
      }

      const handleMouseUp = () => {
        document.removeEventListener('mousemove', handleMouseMove)
        document.removeEventListener('mouseup', handleMouseUp)
      }

      document.addEventListener('mousemove', handleMouseMove)
      document.addEventListener('mouseup', handleMouseUp)
    }, [direction, clampPercent, setSplit])

    const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
      if (!containerRef.current) return
      const step = e.shiftKey ? 10 : 2
      const isHorizontal = direction === 'horizontal'
      const rect = containerRef.current.getBoundingClientRect()
      const size = isHorizontal ? rect.width : rect.height

      if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        e.preventDefault()
        setSplit(clampPercent(splitPercent - step, size))
      } else if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        e.preventDefault()
        setSplit(clampPercent(splitPercent + step, size))
      }
    }, [direction, splitPercent, clampPercent, setSplit])

    const classNames = ['split-pane', `split-pane--${direction}`, className]
      .filter(Boolean)
      .join(' ')

    return (
      <div
        ref={mergeRefs([containerRef, ref])}
        className={classNames}
        {...props}
      >
        <div
          className="split-pane__first"
          style={direction === 'horizontal' ? { width: `${splitPercent}%` } : { height: `${splitPercent}%` }}
        >
          {first}
        </div>

        <div
          role="separator"
          aria-orientation={direction === 'horizontal' ? 'vertical' : 'horizontal'}
          aria-valuenow={Math.round(splitPercent)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={dividerLabel ?? (direction === 'horizontal' ? 'Horizontal divider' : 'Vertical divider')}
          tabIndex={0}
          className={`split-pane__divider split-pane__divider--${direction}`}
          onMouseDown={handleMouseDown}
          onKeyDown={handleKeyDown}
        />

        <div
          className="split-pane__second"
          style={direction === 'horizontal' ? { width: `${100 - splitPercent}%` } : { height: `${100 - splitPercent}%` }}
        >
          {second}
        </div>
      </div>
    )
  }
)

SplitPane.displayName = 'SplitPane'

export default SplitPane
