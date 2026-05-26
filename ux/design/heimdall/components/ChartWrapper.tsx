import React from 'react'

export interface ChartWrapperProps {
  /** Required accessible label — maps to aria-label on the SVG element */
  label: string
  width?: number | string
  height?: number | string
  viewBox?: string
  className?: string
  children: React.ReactNode
}

/**
 * ChartWrapper — accessible SVG container for chart components.
 *
 * Renders an <svg> with role="img" and aria-label already set, so
 * individual chart components built on top of it never need to
 * remember to add these attributes manually.
 *
 * Usage:
 *   <ChartWrapper label="Monthly revenue trend" width={480} height={200} viewBox="0 0 480 200">
 *     {SVG content goes here}
 *   </ChartWrapper>
 */
export const ChartWrapper = React.forwardRef<SVGSVGElement, ChartWrapperProps & Omit<React.SVGAttributes<SVGSVGElement>, 'children'>>(
  ({ label, width, height, viewBox, className = '', children, ...rest }, ref) => {
    return (
      <svg
        ref={ref}
        role="img"
        aria-label={label}
        width={width}
        height={height}
        viewBox={viewBox}
        className={className}
        style={{ display: 'block' }}
        {...rest}
      >
        {children}
      </svg>
    )
  }
)

ChartWrapper.displayName = 'ChartWrapper'
export default ChartWrapper
