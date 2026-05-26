import React, { useState, useRef, useEffect } from 'react'
import './Table.css'
import { Icon } from './Icon'

export interface Column<T> {
  key: keyof T
  label: string
  sortable?: boolean
  width?: string
  render?: (value: T[keyof T], row: T, index: number) => React.ReactNode
}

export interface TableProps<T extends Record<string, any>> {
  columns: Column<T>[]
  data: T[]
  rowKey: keyof T | ((row: T, index: number) => string | number)
  selectable?: boolean
  selectedRows?: (string | number)[]
  onSelectRows?: (rowKeys: (string | number)[]) => void
  onRowClick?: (row: T, rowKey: string | number) => void
  onSort?: (key: string, direction: 'asc' | 'desc' | null) => void
  emptyState?: React.ReactNode
  className?: string
}

const TableInner = React.forwardRef(
  <T extends Record<string, any>,>(
    {
      columns,
      data,
      rowKey,
      selectable = false,
      selectedRows = [],
      onSelectRows,
      onRowClick,
      onSort,
      emptyState,
      className = '',
      ...props
    }: TableProps<T>,
    ref: React.Ref<HTMLTableElement>,
  ) => {
    const [sortKey, setSortKey] = useState<string | null>(null)
    const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc')
    const selectAllRef = useRef<HTMLInputElement>(null)

    const allSelected = data.length > 0 && selectedRows.length === data.length
    const someSelected = selectedRows.length > 0 && selectedRows.length < data.length

    useEffect(() => {
      if (selectAllRef.current) {
        selectAllRef.current.indeterminate = someSelected
      }
    }, [someSelected])

    const getRowKey = (row: T, index: number) => {
      if (typeof rowKey === 'function') {
        return rowKey(row, index)
      }
      return row[rowKey as keyof T]
    }

    const handleSelectAll = () => {
      if (allSelected) {
        onSelectRows?.([])
      } else {
        onSelectRows?.(data.map((row, idx) => getRowKey(row, idx)))
      }
    }

    const handleSelectRow = (rowKeyValue: string | number) => {
      if (selectedRows.includes(rowKeyValue)) {
        onSelectRows?.(selectedRows.filter(k => k !== rowKeyValue))
      } else {
        onSelectRows?.([...selectedRows, rowKeyValue])
      }
    }

    const handleSort = (key: string) => {
      if (sortKey === key) {
        if (sortDirection === 'asc') {
          setSortDirection('desc')
          onSort?.(key, 'desc')
        } else {
          setSortKey(null)
          onSort?.(key, null)
        }
      } else {
        setSortKey(key)
        setSortDirection('asc')
        onSort?.(key, 'asc')
      }
    }

    const handleSortKeyDown = (e: React.KeyboardEvent, key: string) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault()
        handleSort(key)
      }
    }

    const classNames = ['table', className].filter(Boolean).join(' ')

    return (
      <table ref={ref} className={classNames} {...props}>
        <thead className="table__head">
          <tr className="table__row">
            {selectable && (
              <th className="table__header table__header--checkbox" style={{ width: '30px' }}>
                <input
                  ref={selectAllRef}
                  type="checkbox"
                  className="table__checkbox"
                  checked={allSelected}
                  onChange={handleSelectAll}
                  aria-label="Select all rows"
                />
              </th>
            )}
            {columns.map(column => {
              const colKey = String(column.key)
              const isSorted = sortKey === colKey
              const ariaSortValue = isSorted
                ? (sortDirection === 'asc' ? 'ascending' : 'descending')
                : (column.sortable ? 'none' : undefined)
              return (
                <th
                  key={colKey}
                  className={`table__header ${column.sortable ? 'table__header--sortable' : ''}`}
                  style={{ width: column.width }}
                  aria-sort={ariaSortValue}
                  tabIndex={column.sortable ? 0 : undefined}
                  onClick={() => column.sortable && handleSort(colKey)}
                  onKeyDown={column.sortable ? (e) => handleSortKeyDown(e, colKey) : undefined}
                >
                  <div className="table__header-content">
                    {column.label}
                    {isSorted && (
                      <Icon
                        name={sortDirection === 'asc' ? 'chevronUp' : 'chevronDown'}
                        size={14}
                        className="table__sort-icon"
                      />
                    )}
                  </div>
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody className="table__body">
          {data.length === 0 && emptyState ? (
            <tr className="table__row">
              <td
                className="table__cell table__cell--empty"
                colSpan={columns.length + (selectable ? 1 : 0)}
              >
                {emptyState}
              </td>
            </tr>
          ) : (
            data.map((row, index) => {
              const rowKeyValue = getRowKey(row, index)
              const isSelected = selectedRows.includes(rowKeyValue)
              const isClickable = !!onRowClick
              return (
                <tr
                  key={rowKeyValue}
                  data-row-key={rowKeyValue}
                  className={[
                    'table__row',
                    isSelected ? 'table__row--selected' : '',
                    isClickable ? 'table__row--clickable' : '',
                  ].filter(Boolean).join(' ')}
                  onClick={isClickable ? () => onRowClick(row, rowKeyValue) : undefined}
                  onKeyDown={isClickable ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onRowClick(row, rowKeyValue) } } : undefined}
                  tabIndex={isClickable ? 0 : undefined}
                >
                  {selectable && (
                    <td className="table__cell table__cell--checkbox">
                      <input
                        type="checkbox"
                        className="table__checkbox"
                        checked={isSelected}
                        aria-label={`Select row ${rowKeyValue}`}
                        onChange={() => handleSelectRow(rowKeyValue)}
                        onClick={(e) => e.stopPropagation()}
                      />
                    </td>
                  )}
                  {columns.map(column => (
                    <td key={`${rowKeyValue}-${String(column.key)}`} className="table__cell">
                      {column.render ? column.render(row[column.key as keyof T], row, index) : row[column.key as keyof T]}
                    </td>
                  ))}
                </tr>
              )
            })
          )}
        </tbody>
      </table>
    )
  }
)

TableInner.displayName = 'Table'

export const Table = TableInner as <T extends Record<string, any>>(
  props: TableProps<T> & React.RefAttributes<HTMLTableElement>
) => React.ReactElement | null

export default Table
