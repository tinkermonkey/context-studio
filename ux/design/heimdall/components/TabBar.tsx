import React, { useCallback, useRef } from 'react'
import './TabBar.css'
import { Chip } from './Chip'

export interface Tab {
  id: string
  label: string
  count?: number
  disabled?: boolean
}

export interface TabBarProps extends React.HTMLAttributes<HTMLDivElement> {
  tabs?: Tab[]
  activeTabId?: string
  onSelectTab?: (tabId: string) => void
}

export const TabBar = React.forwardRef<HTMLDivElement, TabBarProps>(
  ({ tabs = [], activeTabId = '', onSelectTab, className = '', ...props }, ref) => {
    const classNames = ['tab-bar', className].filter(Boolean).join(' ')
    const tabRefs = useRef<(HTMLButtonElement | null)[]>([])

    const handleKeyDown = useCallback(
      (e: React.KeyboardEvent, index: number) => {
        const enabledIndexes = tabs
          .map((t, i) => (t.disabled ? -1 : i))
          .filter(i => i !== -1)
        const posInEnabled = enabledIndexes.indexOf(index)

        let nextPos: number | undefined
        if (e.key === 'ArrowRight') {
          nextPos = enabledIndexes[(posInEnabled + 1) % enabledIndexes.length]
        } else if (e.key === 'ArrowLeft') {
          nextPos =
            enabledIndexes[
              (posInEnabled - 1 + enabledIndexes.length) % enabledIndexes.length
            ]
        } else if (e.key === 'Home') {
          nextPos = enabledIndexes[0]
        } else if (e.key === 'End') {
          nextPos = enabledIndexes[enabledIndexes.length - 1]
        }

        if (nextPos !== undefined) {
          e.preventDefault()
          tabRefs.current[nextPos]?.focus()
          onSelectTab?.(tabs[nextPos].id)
        }
      },
      [tabs, onSelectTab]
    )

    return (
      <div ref={ref} className={classNames} role="tablist" {...props}>
        <div className="tab-bar__tabs">
          {tabs.map((tab, index) => (
            <button
              key={tab.id}
              type="button"
              ref={el => { tabRefs.current[index] = el }}
              role="tab"
              aria-selected={activeTabId === tab.id}
              aria-disabled={tab.disabled}
              tabIndex={tab.disabled ? -1 : activeTabId === tab.id ? 0 : -1}
              className={[
                'tab-bar__tab',
                activeTabId === tab.id ? 'tab-bar__tab--active' : '',
                tab.disabled ? 'tab-bar__tab--disabled' : '',
              ]
                .filter(Boolean)
                .join(' ')}
              onClick={() => !tab.disabled && onSelectTab?.(tab.id)}
              onKeyDown={e => handleKeyDown(e, index)}
            >
              <span className="tab-bar__tab-label">{tab.label}</span>
              {tab.count !== undefined && (
                <Chip form="id-tag">{tab.count}</Chip>
              )}
            </button>
          ))}
        </div>
      </div>
    )
  }
)

TabBar.displayName = 'TabBar'

export default TabBar
