import React, { useState } from 'react'
import { Icon, type IconName } from './Icon'
import './Sidebar.css'

export interface SidebarItem {
  id: string
  label: string
  icon?: IconName
  count?: number
  children?: Array<{
    id: string
    label: string
    count?: number
  }>
}

export interface SidebarSection {
  title: string
  items: SidebarItem[]
}

export interface SidebarProps extends React.HTMLAttributes<HTMLDivElement> {
  sections: SidebarSection[]
  activeItemId?: string
  collapsed?: boolean
  onCollapse?: (collapsed: boolean) => void
  onSelectItem?: (itemId: string) => void
}

export const Sidebar = React.forwardRef<HTMLDivElement, SidebarProps>(
  (
    {
      sections,
      activeItemId,
      collapsed = false,
      onCollapse,
      onSelectItem,
      className = '',
      ...props
    },
    ref
  ) => {
    const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set())

    const toggleExpanded = (id: string) => {
      setExpandedItems(prev => {
        const next = new Set(prev)
        if (next.has(id)) {
          next.delete(id)
        } else {
          next.add(id)
        }
        return next
      })
    }

    const classNames = [
      'sidebar',
      collapsed && 'sidebar--collapsed',
      className
    ]
      .filter(Boolean)
      .join(' ')

    return (
      <div ref={ref} className={classNames} {...props}>
        <button
          type="button"
          className="sidebar__toggle"
          onClick={() => onCollapse?.(!collapsed)}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <Icon name={collapsed ? 'chevronRight' : 'chevronLeft'} size={16} />
        </button>

        <nav className="sidebar__nav" aria-label="Sidebar navigation">
          {sections.map(section => (
            <div key={section.title} className="sidebar__section">
              {!collapsed && <div className="sidebar__section-title">{section.title}</div>}
              <div className="sidebar__items">
                {section.items.map(item => {
                  const hasChildren = item.children && item.children.length > 0
                  const isExpanded = expandedItems.has(item.id)
                  const isActive = activeItemId === item.id

                  return (
                    <React.Fragment key={item.id}>
                      <button
                        type="button"
                        className={`sidebar__item ${isActive ? 'sidebar__item--active' : ''}`}
                        onClick={() => {
                          if (hasChildren) {
                            toggleExpanded(item.id)
                          } else {
                            onSelectItem?.(item.id)
                          }
                        }}
                        title={collapsed ? item.label : undefined}
                        aria-current={isActive ? 'page' : undefined}
                        aria-expanded={hasChildren ? isExpanded : undefined}
                      >
                        {item.icon && (
                          <Icon name={item.icon} size={18} className="sidebar__item-icon" />
                        )}
                        {!collapsed && (
                          <span className="sidebar__item-label">{item.label}</span>
                        )}
                        {!collapsed && item.count !== undefined && (
                          <span className="sidebar__item-count">{item.count}</span>
                        )}
                        {!collapsed && hasChildren && (
                          <Icon
                            name="chevronRight"
                            size={14}
                            className={`sidebar__item-chevron ${isExpanded ? 'sidebar__item-chevron--open' : ''}`}
                          />
                        )}
                      </button>

                      {!collapsed && hasChildren && isExpanded && item.children!.map(child => (
                        <button
                          key={child.id}
                          type="button"
                          className={`sidebar__item sidebar__item--child ${activeItemId === child.id ? 'sidebar__item--active' : ''}`}
                          onClick={() => onSelectItem?.(child.id)}
                          aria-current={activeItemId === child.id ? 'page' : undefined}
                        >
                          <span className="sidebar__item-label">{child.label}</span>
                          {child.count !== undefined && (
                            <span className="sidebar__item-count">{child.count}</span>
                          )}
                        </button>
                      ))}
                    </React.Fragment>
                  )
                })}
              </div>
            </div>
          ))}
        </nav>
      </div>
    )
  }
)

Sidebar.displayName = 'Sidebar'

export default Sidebar
