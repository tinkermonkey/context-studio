import React, { useCallback } from 'react'
import './OrderedList.css'
import { Button } from './Button'
import { Icon } from './Icon'

export interface OrderedItem {
  id: string
  label: string
}

export interface OrderedListProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, 'onChange'> {
  items: OrderedItem[]
  onChange: (items: OrderedItem[]) => void
  primaryItemId?: string
  disabled?: boolean
}

export const OrderedList = React.forwardRef<HTMLDivElement, OrderedListProps>(
  ({ items, onChange, primaryItemId, disabled = false, className, ...props }, ref) => {
    const handleMoveUp = useCallback((index: number) => {
      if (index > 0) {
        const newItems = [...items]
        ;[newItems[index - 1], newItems[index]] = [newItems[index], newItems[index - 1]]
        onChange(newItems)
      }
    }, [items, onChange])

    const handleMoveDown = useCallback((index: number) => {
      if (index < items.length - 1) {
        const newItems = [...items]
        ;[newItems[index], newItems[index + 1]] = [newItems[index + 1], newItems[index]]
        onChange(newItems)
      }
    }, [items, onChange])

    return (
      <div
        ref={ref}
        className={['ordered-list', disabled && 'ordered-list--disabled', className].filter(Boolean).join(' ')}
        role="list"
        aria-disabled={disabled || undefined}
        data-testid="ordered-list"
        {...props}
      >
        {items.map((item, index) => (
          <div
            key={item.id}
            className={[
              'ordered-list__item',
              primaryItemId === item.id && 'ordered-list__item--primary',
            ]
              .filter(Boolean)
              .join(' ')}
            role="listitem"
            data-testid={`ordered-item-${item.id}`}
          >
            <div className="ordered-list__rank">
              {primaryItemId === item.id && (
                <div className="ordered-list__primary-badge" title="Primary item">
                  <Icon name="star" size={10} />
                </div>
              )}
              <div className="ordered-list__index">{index + 1}</div>
            </div>

            <span className="ordered-list__label">{item.label}</span>

            <div className="ordered-list__controls">
              <Button
                variant="ghost"
                size="sm"
                disabled={disabled || index === 0}
                onClick={() => handleMoveUp(index)}
                aria-label="Move up"
                data-testid={`move-up-${item.id}`}
              >
                <Icon name="arrowUp" size={16} />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={disabled || index === items.length - 1}
                onClick={() => handleMoveDown(index)}
                aria-label="Move down"
                data-testid={`move-down-${item.id}`}
              >
                <Icon name="arrowDown" size={16} />
              </Button>
            </div>
          </div>
        ))}
      </div>
    )
  }
)

OrderedList.displayName = 'OrderedList'

export default OrderedList
