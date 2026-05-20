import { TextInput as HeimdallTextInput, TextArea as HeimdallTextarea, Select as HeimdallSelect } from "@tinkermonkey/heimdall-ui";
import { forwardRef, type InputHTMLAttributes, type TextareaHTMLAttributes, type SelectHTMLAttributes } from "react";

interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "className"> {
  mono?: boolean;
  className?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ mono = false, className = "", ...props }, ref) => {
    const classes = ["input", mono && "mono", className].filter(Boolean).join(" ");

    return <HeimdallTextInput ref={ref} className={classes} {...props} />;
  },
);

Input.displayName = "Input";

interface TextareaProps extends Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "className"> {
  mono?: boolean;
  className?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ mono = false, className = "", ...props }, ref) => {
    const classes = ["input", "textarea", mono && "mono", className].filter(Boolean).join(" ");

    return <HeimdallTextarea ref={ref} className={classes} {...props} />;
  },
);

Textarea.displayName = "Textarea";

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  mono?: boolean;
  className?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ mono = false, className = "", children, ...props }, ref) => {
    const classes = ["input", mono && "mono", className].filter(Boolean).join(" ");

    return (
      <HeimdallSelect ref={ref} className={classes} {...props}>
        {children}
      </HeimdallSelect>
    );
  },
);

Select.displayName = "Select";
