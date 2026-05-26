import React from 'react'
import './Button.css'

export type Variant = 'primary' | 'accent' | 'secondary' | 'ghost' | 'danger' | 'link'
export type Size = 'sm' | 'md'

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  icon?: boolean
  children: React.ReactNode
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', icon, className = '', disabled, type = 'button', ...props }, ref) => {
    const classNames = [
      'btn',
      `btn--${variant}`,
      `btn--${size}`,
      icon ? 'btn--icon' : '',
      className,
    ]
      .filter(Boolean)
      .join(' ')

    return (
      <button
        ref={ref}
        type={type} // eslint-disable-line react/button-has-type
        disabled={disabled}
        className={classNames}
        {...props}
      />
    )
  }
)

Button.displayName = 'Button'

export default Button
