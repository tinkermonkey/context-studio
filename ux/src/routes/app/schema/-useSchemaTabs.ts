import { useNavigate } from "@tanstack/react-router";
import { useEntityCounts } from "@/api/hooks/ontology/useEntityCounts";

const SCHEMA_ROUTES: Record<string, string> = {
  taxonomies: "/app/schema/taxonomies",
  schemes: "/app/schema/schemes",
  classes: "/app/schema/classes",
  properties: "/app/schema/properties",
  relationships: "/app/schema/relationships",
};

/**
 * Tabs shared by the schema list pages, with unfiltered totals from
 * `limit=1` count requests, plus the tab-navigation handler and the counts.
 */
export function useSchemaTabs() {
  const navigate = useNavigate();
  const counts = useEntityCounts({ schemaOnly: true });
  const tabs = [
    { id: "taxonomies", label: "Taxonomies", count: counts.taxonomies },
    { id: "schemes", label: "Schemes", count: counts.schemes },
    { id: "classes", label: "Classes", count: counts.classes },
    { id: "properties", label: "Properties", count: counts.properties },
    { id: "relationships", label: "Relationships", count: counts.relationships },
  ];
  function onSelectTab(tabId: string) {
    navigate({ to: SCHEMA_ROUTES[tabId] as any });
  }
  return { tabs, onSelectTab, counts };
}
