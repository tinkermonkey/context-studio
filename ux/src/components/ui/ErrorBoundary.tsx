import React, { ReactNode } from "react";
import { Button } from "@tinkermonkey/heimdall-ui";
import { getActiveSpan } from "@/telemetry";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error): void {
    console.error("Error boundary caught:", error);

    const span = getActiveSpan();
    if (span) {
      span.recordException(error);
      span.addEvent("error_boundary_catch", {
        error_message: error.message,
        error_stack: error.stack || "no stack trace",
      });
    }
  }

  private handleReset = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            height: "100%",
            width: "100%",
          }}
        >
          <div
            style={{
              padding: "var(--space-6)",
              maxWidth: "500px",
              textAlign: "center",
              background: "rgb(var(--canvas-surface))",
              border: "1px solid rgb(var(--canvas-border))",
              borderRadius: "var(--radius-md)",
            }}
          >
            <h1 style={{ marginBottom: "var(--space-3)", color: "rgb(var(--status-error))" }}>
              Something went wrong
            </h1>
            <p
              style={{
                marginBottom: "var(--space-4)",
                color: "rgb(var(--canvas-fg-2))",
                fontSize: "var(--text-sm)",
                fontFamily: "var(--font-mono)",
                wordBreak: "break-word",
              }}
            >
              {this.state.error?.message || "An unexpected error occurred"}
            </p>
            <Button onClick={this.handleReset}>Try again</Button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
