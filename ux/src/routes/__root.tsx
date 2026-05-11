import { useEffect } from "react";
import { createRootRoute, Outlet } from "@tanstack/react-router";
import { ApiProvider } from "@/api/ApiProvider";
import { CommandPalette } from "@/components/shell/CommandPalette";
import { ToastProvider, ToastViewport, useToasts } from "@/components/ui/Toast";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { setGlobalErrorHandler } from "@/api/utils/queryClient";

export const Route = createRootRoute({
  component: Root,
});

function RootContent() {
  const { toasts, dismiss, toast } = useToasts();

  useEffect(() => {
    setGlobalErrorHandler(toast);
  }, [toast]);

  return (
    <>
      <ErrorBoundary>
        <Outlet />
        <CommandPalette />
      </ErrorBoundary>
      <ToastViewport toasts={toasts} onDismiss={dismiss} />
    </>
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
