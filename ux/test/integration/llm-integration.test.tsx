/**
 * LLM Service Integration Test
 *
 * Basic test to verify LLM service and hooks are properly integrated
 */

import { describe, it, expect } from "vitest";
import { llmService } from "../../src/api/services/llm";
import {
  useLLMHealth,
  useSimpleDefinition,
  useSuggestDefinitionMutation,
  type DefinitionSuggestionRequest,
  type ComponentTerm,
} from "../../src/api/hooks/llm";

describe("LLM Service Integration", () => {
  it("should export LLM service with all methods", () => {
    expect(llmService).toBeDefined();
    expect(llmService.suggestTermDefinition).toBeInstanceOf(Function);
    expect(llmService.healthCheck).toBeInstanceOf(Function);
    expect(llmService.generateSimpleDefinition).toBeInstanceOf(Function);
    expect(llmService.generateDefinitionWithDomain).toBeInstanceOf(Function);
    expect(llmService.generateDefinitionWithParent).toBeInstanceOf(Function);
    expect(llmService.generateDefinitionWithComponents).toBeInstanceOf(
      Function,
    );
    expect(llmService.generateDefinitionWithReferences).toBeInstanceOf(
      Function,
    );
    expect(llmService.generateComprehensiveDefinition).toBeInstanceOf(Function);
  });

  it("should export LLM hooks", () => {
    expect(useLLMHealth).toBeInstanceOf(Function);
    expect(useSimpleDefinition).toBeInstanceOf(Function);
    expect(useSuggestDefinitionMutation).toBeInstanceOf(Function);
  });

  it("should export TypeScript types", () => {
    // Just verify types can be imported without error
    const request: DefinitionSuggestionRequest = { term: "test" };
    const componentTerm: ComponentTerm = { text: "test" };

    expect(request.term).toBe("test");
    expect(componentTerm.text).toBe("test");
  });

  it("should validate required parameters in service methods", async () => {
    await expect(
      llmService.suggestTermDefinition({ term: "" }),
    ).rejects.toThrow("term cannot be empty");
  });

  it("should handle minimal definition request", () => {
    const request: DefinitionSuggestionRequest = {
      term: "artificial intelligence",
    };

    expect(request.term).toBe("artificial intelligence");
    expect(request.domain_title).toBeUndefined();
  });

  it("should handle comprehensive definition request", () => {
    const componentTerms: ComponentTerm[] = [
      {
        text: "machine",
        selected_definitions: ["a device that performs work"],
        selected_relations: [
          {
            predicate: "isa",
            object: "device",
            weight: 0.8,
            text: "machine is a device",
          },
        ],
      },
    ];

    const request: DefinitionSuggestionRequest = {
      term: "machine learning",
      domain_title: "Computer Science",
      domain_definition: "The study of algorithms and computational systems",
      parent_term_title: "artificial intelligence",
      parent_term_definition: "Intelligence demonstrated by machines",
      parent_relationship_predicate: "is_a_type_of",
      component_terms: componentTerms,
      "current definition": "An existing definition",
      dbpedia_context: { uri: "http://dbpedia.org/resource/Machine_learning" },
      wikidata_context: { id: "Q2539" },
    };

    expect(request.term).toBe("machine learning");
    expect(request.component_terms).toHaveLength(1);
    expect(request.component_terms![0].selected_relations).toHaveLength(1);
  });
});
