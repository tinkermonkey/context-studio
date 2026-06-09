
type ChipVariant = StatusColor
type ChipForm = 'default' | 'id-tag' | 'version' | 'env'

interface ChipProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: ChipVariant
  form?: ChipForm
  children: React.ReactNode
}

const Chip = React.forwardRef<HTMLSpanElement, ChipProps>(
  ({ variant = 'neutral', form = 'default', className = '', children, ...props }, ref) => {
    const classNames = [
      'chip',
      `chip--${form}`,
      form === 'default' && `chip--${variant}`,
      className,
    ]
      .filter(Boolean)
      .join(' ')

    return (
      <span
        ref={ref}
        className={classNames}
        {...props}
      >
        {form === 'default' && <span className="chip__dot" />}
        {form === 'env' && <span className="chip__dot chip__dot--env" />}
        {children}
      </span>
    )
  }
)

Chip.displayName = 'Chip'



// --- Babel-standalone: expose runtime values to window ---
window.Chip = Chip;
