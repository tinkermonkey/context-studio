import { createRootRoute, Outlet } from "@tanstack/react-router";
import { ApiProvider } from "@/api/ApiProvider";
import { CommandPalette } from "@/components/shell/CommandPalette";
import { ToastProvider, ToastViewport, useToasts } from "@/components/ui/Toast";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";

export const Route = createRootRoute({
  component: Root,
});

function RootContent() {
  const { toasts, dismiss } = useToasts();

  return (
    <ErrorBoundary>
      <Outlet />
      <CommandPalette />
      <ToastViewport toasts={toasts} onDismiss={dismiss} />
    </ErrorBoundary>
  );
}

function Root() {
  return (
    <ApiProvider>
      <ToastProvider>
        <RootContent />
      </ToastProvider>
    </ApiProvider>
  );
}
