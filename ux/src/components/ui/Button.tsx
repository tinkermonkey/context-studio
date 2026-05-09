import { type ButtonHTMLAttributes, forwardRef } from "react";

type Variant = "primary" | "accent" | "ghost" | "danger" | "icon";
type Size = "sm" | "md";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "ghost", size, className = "", children, ...props }, ref) => {
    const classes = ["btn", `btn-${variant}`, size === "sm" && "btn-sm", className]
      .filter(Boolean)
      .join(" ");

    return (
      <button ref={ref} className={classes} type="button" {...props}>
        {children}
      </button>
    );
  },
);

Button.displayName = "Button";
