import React from 'react'
import './VersionPill.css'

export interface VersionPillProps extends React.HTMLAttributes<HTMLSpanElement> {
  children: React.ReactNode
}

export const VersionPill = React.forwardRef<HTMLSpanElement, VersionPillProps>(
  ({ className = '', children, ...props }, ref) => {
    const classNames = ['version-pill', className]
      .filter(Boolean)
      .join(' ')

    return (
      <span ref={ref} className={classNames} {...props}>
        {children}
      </span>
    )
  }
)

VersionPill.displayName = 'VersionPill'

export default VersionPill
