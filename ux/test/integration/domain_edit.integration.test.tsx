import React from "react";
import userEvent from "@testing-library/user-event";
import { screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

// Hoistable mocks so router and hooks don't perform network or rely on app RouterProvider
vi.mock("@tanstack/react-router", () => {
  return {
    Link: (props: any) => React.createElement("a", props, props.children),
    useNavigate: () => vi.fn(),
  };
});
vi.mock("@/api/hooks/layers/useLayers", () => ({
  useLayer: (id: string) => ({
    data: { id, title: "Layer 1" },
    isLoading: false,
  }),
  useLayers: () => ({
    data: [{ id: "layer-1", title: "Layer 1" }],
    isLoading: false,
  }),
}));
vi.mock("@/api/hooks/terms/useTerms", () => ({
  useTerms: (_: any) => ({ data: [], isLoading: false }),
}));
vi.mock("@/api/hooks/graph/useGraph", () => ({
  useTermHierarchy: (_: string) => ({
    data: null,
    isLoading: false,
    error: null,
  }),
}));
vi.mock("@/api/hooks/ontologyClasses/useNodeAttributes", () => ({
  useNodeAttributes: () => ({
    data: [],
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useNodeAttributeMutations: () => ({
    setAttributesMutation: { mutateAsync: vi.fn(), isPending: false },
    removeAttributeMutation: { mutateAsync: vi.fn(), isPending: false },
  }),
}));
vi.mock("@/api/hooks/taxonomies/useTaxonomies", () => ({
  useTaxonomies: () => ({
    data: [{ id: "1", title: "Layer 1", description: "Test layer" }],
    isLoading: false,
    error: null,
  }),
  useCreateTaxonomy: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useUpdateTaxonomy: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
}));
vi.mock("@/api/hooks/conceptSchemes/useConceptSchemes", () => ({
  useConceptSchemes: () => ({
    data: [],
    isLoading: false,
    error: null,
  }),
  useCreateConceptScheme: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useUpdateConceptScheme: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
}));
vi.mock("@/api/hooks/ontologyClasses/useOntologyClasses", () => ({
  useOntologyClasses: () => ({
    data: [],
    isLoading: false,
    error: null,
  }),
  useOntologyClass: (_id: string) => ({
    data: null,
    isLoading: false,
    error: null,
  }),
  useCreateOntologyClass: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useUpdateOntologyClass: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
}));

import {
  renderWithProviders as render,
  makeTestQueryClient,
} from "@/test/utils/renderWithProviders";
import { OntologyClassDetails } from "@/components/node_details/structure_node_details";
import { QUERY_KEYS } from "@/api/config";
// Using service-level mocks for deterministic integration test
import { structureNodeService } from "@/api/services/structureNodes";
import { NodeType } from "@/api/types/structureNodes";
import { setupMocks } from "../msw/setupTests";

// Setup MSW for any uncaught network calls
setupMocks();

const domain = {
  id: "1",
  title: "Domain 1",
  definition: "A test domain",
  description: "A test domain",
  node_type: NodeType.DOMAIN,
  parent_node_id: "00000000-0000-0000-0000-000000000000",
  parent_class_id: "00000000-0000-0000-0000-000000000000",
  concept_scheme_id: "1",
  taxonomy_id: "taxonomy-1",
  created_at: new Date().toISOString(),
  last_modified: new Date().toISOString(),
  version: 1,
};

describe("OntologyClassDetails edit flow (Domain)", () => {
  it("opens edit modal, submits form, and invalidates queries on success", async () => {
    // create a test QueryClient and spy on invalidateQueries
    const qc = makeTestQueryClient();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");

    // Service-level spies: mock the actual services being called
    const updatedDomain = {
      ...domain,
      title: "Domain 1 edited",
      version: 2,
      last_modified: new Date().toISOString(),
    };

    // Mock structureNodeService methods that are actually called
    const getSpy = vi
      .spyOn(structureNodeService, "get")

      .mockResolvedValue(domain as any);
    const updateSpy = vi
      .spyOn(structureNodeService, "update")

      .mockResolvedValue(updatedDomain as any);

    // With Link, useLayer, and useTerms mocked above, we can render without RouterProvider
    render(<OntologyClassDetails node={domain} />, { queryClient: qc });

    // Edit button should be present
    const edit = await screen.findByRole("button", { name: /edit/i });
    await userEvent.click(edit);

    // Wait for modal to appear and get the title input
    const titleInput = await screen.findByLabelText(/title/i);
    await userEvent.clear(titleInput);
    await userEvent.type(titleInput, "Domain 1 edited");

    // Click save/submit button - our service mocks will handle the update
    const save = screen.getByRole("button", {
      name: /save|save changes|create domain/i,
    });
    await userEvent.click(save);

    // Wait until invalidateQueries has been called for both the per-node and nodes list keys
    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalled();
      // check for list invalidation
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: [QUERY_KEYS.STRUCTURE_NODES],
      });
      // check for per-node invalidation
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: [QUERY_KEYS.STRUCTURE_NODES, domain.id],
      });
      // Service mocks handled the update; we expect the query invalidation to have been triggered
    });

    // restore spies to avoid leaking into other tests
    getSpy.mockRestore();
    updateSpy.mockRestore();
  });
});
