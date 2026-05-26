import React from 'react'
import './HierarchyTree.css'

export interface HierarchyTreeProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
}

export const HierarchyTree = React.forwardRef<HTMLDivElement, HierarchyTreeProps>(
  ({ className = '', children, ...props }, ref) => {
    const classNames = ['hierarchy-tree', className].filter(Boolean).join(' ')

    return (
      <div ref={ref} className={classNames} {...props}>
        {children}
      </div>
    )
  }
)

HierarchyTree.displayName = 'HierarchyTree'

export default HierarchyTree
