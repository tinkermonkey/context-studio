interface NumberInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  mono?: boolean;
  error?: boolean;
}

const NumberInput = React.forwardRef<HTMLInputElement, NumberInputProps>(
  ({ mono = false, error = false, className = "", ...props }, ref) => {
    const classNames = [
      "number-input",
      mono && "number-input--mono",
      error && "number-input--error",
      className,
    ]
      .filter(Boolean)
      .join(" ");

    return <input ref={ref} type="number" className={classNames} {...props} />;
  },
);

NumberInput.displayName = "NumberInput";

// --- Babel-standalone: expose runtime values to window ---
window.NumberInput = NumberInput;
