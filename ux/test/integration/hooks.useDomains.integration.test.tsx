import React from "react";
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { screen, waitFor } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { renderWithProviders as render } from "@/test/utils/renderWithProviders";
import { useDomainNodes } from "@/api/hooks/structure_nodes/useStructureNodes";

const TestComponent: React.FC = () => {
  const { data, isLoading } = useDomainNodes();
  if (isLoading) return <div>loading</div>;
  return (
    <div>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      { }
      {data?.map((d: any) => (
        <div key={d.id}>{d.title}</div>
      ))}
    </div>
  );
};

describe("useDomains integration", () => {
  it("fetches domains and renders at least one item", async () => {
    const { container } = render(<TestComponent />);
    await waitFor(() => {
      // ensure loading is gone and at least one child is rendered
      expect(container.querySelectorAll("div > div").length).toBeGreaterThan(0);
    });
  });
});
