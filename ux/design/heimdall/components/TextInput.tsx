interface TextInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  mono?: boolean;
  error?: boolean;
}

const TextInput = React.forwardRef<HTMLInputElement, TextInputProps>(
  ({ mono = false, error = false, className = "", ...props }, ref) => {
    const classNames = [
      "text-input",
      mono && "text-input--mono",
      error && "text-input--error",
      className,
    ]
      .filter(Boolean)
      .join(" ");

    return <input type="text" ref={ref} className={classNames} {...props} />;
  },
);

TextInput.displayName = "TextInput";

// --- Babel-standalone: expose runtime values to window ---
window.TextInput = TextInput;
