import React from 'react'
import { Icon, type IconName } from './Icon'
import './NavItem.css'

export interface NavItemProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  icon?: IconName
  label: string
  count?: number
  active?: boolean
  depth?: 0 | 1
}

export const NavItem = React.forwardRef<HTMLButtonElement, NavItemProps>(
  ({ icon, label, count, active = false, depth = 0, onClick, className = '', type = 'button', ...props }, ref) => {
    const classNames = [
      'nav-item',
      active && 'nav-item--active',
      depth === 1 && 'nav-item--depth-1',
      className,
    ]
      .filter(Boolean)
      .join(' ')

    return (
      <button
        ref={ref}
        type={type} // eslint-disable-line react/button-has-type
        className={classNames}
        onClick={onClick}
        aria-current={active ? 'page' : undefined}
        {...props}
      >
        {depth === 0 && icon && <Icon name={icon} size={16} className="nav-item__icon" />}
        <span className="nav-item__label">{label}</span>
        {count !== undefined && <span className="nav-item__count">{count}</span>}
      </button>
    )
  }
)

NavItem.displayName = 'NavItem'

export default NavItem
