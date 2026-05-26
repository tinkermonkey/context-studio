import React from 'react'
import { QuickAccessTile } from './QuickAccessTile'
import type { IconName } from './Icon'
import './QuickAccessGrid.css'

export interface QuickAccessGridItem {
  id: string
  icon: IconName
  title: string
  description: string
}

export interface QuickAccessGridProps extends React.HTMLAttributes<HTMLDivElement> {
  tiles: QuickAccessGridItem[]
  onAction?: (tileId: string) => void
  columns?: number
}

// Backward compatibility export
export type QuickAccessTile = QuickAccessGridItem

export const QuickAccessGrid = React.forwardRef<HTMLDivElement, QuickAccessGridProps>(
  ({ tiles, onAction, columns = 4, className = '', ...props }, ref) => {
    const classNames = ['quick-access-grid', className].filter(Boolean).join(' ')

    return (
      <div
        ref={ref}
        className={classNames}
        style={{ '--qa-columns': columns } as React.CSSProperties}
        data-testid="quick-access-grid"
        {...props}
      >
        {tiles.map(tile => (
          <QuickAccessTile
            key={tile.id}
            icon={tile.icon}
            title={tile.title}
            description={tile.description}
            onClick={() => onAction?.(tile.id)}
            data-testid={`quick-access-tile-${tile.id}`}
          />
        ))}
      </div>
    )
  }
)

QuickAccessGrid.displayName = 'QuickAccessGrid'

export default QuickAccessGrid
