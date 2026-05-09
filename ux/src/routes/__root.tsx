import { createRootRoute, Outlet } from "@tanstack/react-router";
import { ApiProvider } from "@/api/ApiProvider";
import { CommandPalette } from "@/components/shell/CommandPalette";
import { ToastProvider, ToastViewport, useToasts } from "@/components/ui/Toast";

export const Route = createRootRoute({
  component: Root,
});

function RootContent() {
  const { toasts, dismiss } = useToasts();

  return (
    <>
      <Outlet />
      <CommandPalette />
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
