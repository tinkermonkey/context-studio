import { describe, it, expect } from "vitest";
import { render } from "@/test/test-utils";
import { HierarchyTree } from "@/components/ontology/HierarchyTree";
import type { components } from "@/api/types";

type ClassResponse = components["schemas"]["ClassResponse"];

const mockClasses: ClassResponse[] = [
  {
    id: "class-1",
    title: "Root Class",
    concept_scheme_id: "scheme-1",
    taxonomy_id: "taxonomy-1",
    parent_class_id: null,
    created_at: new Date().toISOString(),
    version: 1,
    status: "draft",
  },
];

describe("Debug Test", () => {
  it("should render HierarchyTree", () => {
    const { debug } = render(<HierarchyTree classes={mockClasses} />);
    debug();
  });
});
