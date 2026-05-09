import { createFileRoute } from "@tanstack/react-router";
import UnifiedSearchPage from "@/components/reference/UnifiedSearchPage";

export const Route = createFileRoute("/app/reference/search")({
  component: ReferenceSearchComponent,
});

function ReferenceSearchComponent() {
  return <UnifiedSearchPage />;
}
