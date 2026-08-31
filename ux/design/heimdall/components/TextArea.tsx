interface TextAreaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  mono?: boolean;
  error?: boolean;
}

const TextArea = React.forwardRef<HTMLTextAreaElement, TextAreaProps>(
  ({ mono = false, error = false, className = "", ...props }, ref) => {
    const classNames = [
      "text-area",
      mono && "text-area--mono",
      error && "text-area--error",
      className,
    ]
      .filter(Boolean)
      .join(" ");

    return <textarea ref={ref} className={classNames} {...props} />;
  },
);

TextArea.displayName = "TextArea";

// --- Babel-standalone: expose runtime values to window ---
window.TextArea = TextArea;
