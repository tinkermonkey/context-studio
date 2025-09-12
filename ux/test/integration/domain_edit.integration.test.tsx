import React from "react";
import userEvent from "@testing-library/user-event";
import { screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

// Hoistable mocks so router and hooks don't perform network or rely on app RouterProvider
vi.mock("@tanstack/react-router", () => {
  const React = require("react");
  return {
    Link: (props: any) => React.createElement("a", props, props.children),
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
  useTerms: (_params: any) => ({ data: [], isLoading: false }),
}));

import {
  renderWithProviders as render,
  makeTestQueryClient,
} from "@/test/utils/renderWithProviders";
import { DomainDetails } from "@/components/node_details/domain_details";
import { QUERY_KEYS } from "@/api/config";
// Using a service-level mock for deterministic integration test; MSW imports removed
// import { rest } from 'msw';
// import { server } from '../../test/msw/server';
import { domainService } from "@/api/services/domains";

const domain = {
  id: "1",
  title: "Domain 1",
  definition: "A test domain",
  layer_id: "00000000-0000-0000-0000-000000000000",
  created_at: new Date().toISOString(),
  description: "Desc",
};

describe("DomainDetails edit flow", () => {
  it("opens edit modal, submits form, and invalidates queries on success", async () => {
    // create a test QueryClient and spy on invalidateQueries
    const qc = makeTestQueryClient();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");

    // Service-level spy: avoid network calls and return updated domain directly.
    const updatedDomain = { ...domain, title: "Domain 1 edited" };
    const updateSpy = vi
      .spyOn(domainService, "update")
      .mockResolvedValue(updatedDomain as any);

    // With Link, useLayer, and useTerms mocked above, we can render without RouterProvider
    render(<DomainDetails domain={domain} />, { queryClient: qc });

    // no service-level mock in this test; MSW will handle network calls

    // Edit button should be present
    const edit = await screen.findByRole("button", { name: /edit/i });
    await userEvent.click(edit);

    // Wait for modal to appear and get the title input
    const titleInput = await screen.findByLabelText(/title/i);
    await userEvent.clear(titleInput);
    await userEvent.type(titleInput, "Domain 1 edited");

    // Click save/submit button - MSW will handle the PUT and return the updated domain
    const save = screen.getByRole("button", {
      name: /save|save changes|create domain/i,
    });
    await userEvent.click(save);

    // Wait until invalidateQueries has been called for both the per-domain and domains list keys
    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalled();
      // check for list invalidation
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: [QUERY_KEYS.DOMAINS],
      });
      // check for per-domain invalidation
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: [QUERY_KEYS.DOMAINS, domain.id],
      });
      // MSW handled the update; we expect the query invalidation to have been triggered
    });

    // restore spy to avoid leaking into other tests
    updateSpy.mockRestore();
  });
});
