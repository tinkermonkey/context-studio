import { forwardRef, type InputHTMLAttributes, type TextareaHTMLAttributes } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  mono?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ mono, className = "", ...props }, ref) => (
    <input
      ref={ref}
      className={["input", mono && "mono", className].filter(Boolean).join(" ")}
      {...props}
    />
  ),
);
Input.displayName = "Input";

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  mono?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ mono, className = "", ...props }, ref) => (
    <textarea
      ref={ref}
      className={["input textarea", mono && "mono", className].filter(Boolean).join(" ")}
      {...props}
    />
  ),
);
Textarea.displayName = "Textarea";

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  mono?: boolean;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ mono, className = "", children, ...props }, ref) => (
    <select
      ref={ref}
      className={["input", mono && "mono", className].filter(Boolean).join(" ")}
      {...props}
    >
      {children}
    </select>
  ),
);
Select.displayName = "Select";
