import { createFileRoute, Outlet } from "@tanstack/react-router";
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CsNavbar } from "../components/layout/cs_navbar";

export const Route = createFileRoute("/app")({
  component: AppComponent,
});

const queryClient = new QueryClient();

function AppComponent() {
  return (
    <>
      <CsNavbar />
      <div className="mx-auto w-full max-w-7xl lg:flex lg:px-4">
        <QueryClientProvider client={queryClient}>
          <Outlet />
        </QueryClientProvider>
      </div>
    </>
  );
}
