/**
 * LLM API Usage Examples
 *
 * Examples demonstrating how to use the new LLM API endpoints for definition suggestions
 */

import React, { useState } from "react";
import {
  useLLMHealth,
  useSimpleDefinition,
  useDefinitionWithDomain,
  useSuggestDefinitionMutation,
  useGenerateSimpleDefinitionMutation,
  type DefinitionSuggestionRequest,
  type DefinitionSuggestionResponse,
  type ComponentTerm,
} from "../../api";

// Example 1: Simple health check
export const LLMHealthCheck: React.FC = () => {
  const { data: health, isLoading, error } = useLLMHealth();

  if (isLoading) return <div>Checking LLM health...</div>;
  if (error) return <div>Error: {error.message}</div>;

  return (
    <div>
      <h3>LLM Service Health</h3>
      <p>Status: {health?.status}</p>
      <p>Timestamp: {health?.timestamp}</p>
      <pre>{JSON.stringify(health?.model_info, null, 2)}</pre>
    </div>
  );
};

// Example 2: Simple definition generation
export const SimpleDefinitionExample: React.FC = () => {
  const [term, setTerm] = useState("");
  const {
    data: definition,
    isLoading,
    error,
  } = useSimpleDefinition(term.trim().length > 0 ? term : null);

  return (
    <div>
      <h3>Simple Definition Generation</h3>
      <input
        type="text"
        value={term}
        onChange={(e) => setTerm(e.target.value)}
        placeholder="Enter a term to define..."
      />

      {isLoading && <p>Generating definition...</p>}
      {error && <p>Error: {error.message}</p>}
      {definition && (
        <div>
          <h4>Definition:</h4>
          <p>{definition.definition}</p>
          <h4>Reasoning:</h4>
          <p>{definition.reasoning}</p>
          {definition.discrepancies && (
            <>
              <h4>Discrepancies:</h4>
              <p>{definition.discrepancies}</p>
            </>
          )}
        </div>
      )}
    </div>
  );
};

// Example 3: Definition with domain context
export const DefinitionWithDomainExample: React.FC = () => {
  const [term, setTerm] = useState("neural network");
  const [domain, setDomain] = useState("Machine Learning");
  const [domainDef, setDomainDef] = useState(
    "A subset of artificial intelligence",
  );

  const {
    data: definition,
    isLoading,
    error,
  } = useDefinitionWithDomain(
    term.trim().length > 0 ? term : null,
    domain.trim().length > 0 ? domain : null,
    domainDef.trim().length > 0 ? domainDef : undefined,
  );

  return (
    <div>
      <h3>Definition with Domain Context</h3>
      <input
        type="text"
        value={term}
        onChange={(e) => setTerm(e.target.value)}
        placeholder="Term to define..."
      />
      <input
        type="text"
        value={domain}
        onChange={(e) => setDomain(e.target.value)}
        placeholder="Domain title..."
      />
      <textarea
        value={domainDef}
        onChange={(e) => setDomainDef(e.target.value)}
        placeholder="Domain definition..."
      />

      {isLoading && <p>Generating contextual definition...</p>}
      {error && <p>Error: {error.message}</p>}
      {definition && (
        <div>
          <h4>Contextual Definition:</h4>
          <p>{definition.definition}</p>
          <h4>Reasoning:</h4>
          <p>{definition.reasoning}</p>
        </div>
      )}
    </div>
  );
};

// Example 4: Mutation-based definition generation
export const MutationDefinitionExample: React.FC = () => {
  const [term, setTerm] = useState("");
  const generateDefinition = useGenerateSimpleDefinitionMutation({
    onSuccess: (data: DefinitionSuggestionResponse) => {
      console.log("Definition generated:", data);
    },
    onError: (error: Error) => {
      console.error("Error generating definition:", error);
    },
  });

  const handleGenerate = () => {
    if (term.trim()) {
      generateDefinition.mutate(term);
    }
  };

  return (
    <div>
      <h3>Manual Definition Generation</h3>
      <input
        type="text"
        value={term}
        onChange={(e) => setTerm(e.target.value)}
        placeholder="Enter a term..."
      />
      <button
        onClick={handleGenerate}
        disabled={generateDefinition.isPending || !term.trim()}
      >
        {generateDefinition.isPending ? "Generating..." : "Generate Definition"}
      </button>

      {generateDefinition.error && (
        <p>Error: {generateDefinition.error.message}</p>
      )}
      {generateDefinition.data && (
        <div>
          <h4>Generated Definition:</h4>
          <p>{generateDefinition.data.definition}</p>
          <h4>Reasoning:</h4>
          <p>{generateDefinition.data.reasoning}</p>
        </div>
      )}
    </div>
  );
};

// Example 5: Comprehensive definition request
export const ComprehensiveDefinitionExample: React.FC = () => {
  const [request, setRequest] = useState<DefinitionSuggestionRequest>({
    term: "machine learning",
    domain_title: "Computer Science",
    domain_definition: "The study of algorithms and computational systems",
    parent_term_title: "artificial intelligence",
    parent_term_definition: "Intelligence demonstrated by machines",
    parent_relationship_predicate: "is_a_type_of",
    component_terms: [
      {
        text: "algorithm",
        selected_definitions: ["A process or set of rules to be followed"],
        selected_relations: [
          {
            predicate: "used_for",
            object: "computation",
            weight: 0.9,
            text: "algorithms are used for computation",
          },
        ],
      },
    ],
    dbpedia_context: {
      uri: "http://dbpedia.org/resource/Machine_learning",
      label: "Machine learning",
    },
    wikidata_context: {
      id: "Q2539",
      label: "machine learning",
    },
  });

  const generateDefinition = useSuggestDefinitionMutation({
    onSuccess: (data: DefinitionSuggestionResponse) => {
      console.log("Comprehensive definition generated:", data);
    },
  });

  const handleGenerate = () => {
    generateDefinition.mutate(request);
  };

  return (
    <div>
      <h3>Comprehensive Definition Generation</h3>
      <p>This example shows a complete request with all context types:</p>
      <ul>
        <li>Term: {request.term}</li>
        <li>Domain: {request.domain_title}</li>
        <li>Parent term: {request.parent_term_title}</li>
        <li>Component terms: {request.component_terms?.length || 0}</li>
        <li>External references: DBpedia + Wikidata</li>
      </ul>

      <button onClick={handleGenerate} disabled={generateDefinition.isPending}>
        {generateDefinition.isPending
          ? "Generating..."
          : "Generate Comprehensive Definition"}
      </button>

      {generateDefinition.error && (
        <p>Error: {generateDefinition.error.message}</p>
      )}
      {generateDefinition.data && (
        <div>
          <h4>Comprehensive Definition:</h4>
          <p>{generateDefinition.data.definition}</p>
          <h4>Reasoning:</h4>
          <p>{generateDefinition.data.reasoning}</p>
          {generateDefinition.data.discrepancies && (
            <>
              <h4>Discrepancies:</h4>
              <p>{generateDefinition.data.discrepancies}</p>
            </>
          )}
        </div>
      )}
    </div>
  );
};

// Main example component combining all examples
export const LLMAPIExamples: React.FC = () => {
  const [activeExample, setActiveExample] = useState<string>("health");

  const examples = {
    health: { component: LLMHealthCheck, title: "Health Check" },
    simple: { component: SimpleDefinitionExample, title: "Simple Definition" },
    domain: { component: DefinitionWithDomainExample, title: "Domain Context" },
    mutation: {
      component: MutationDefinitionExample,
      title: "Manual Generation",
    },
    comprehensive: {
      component: ComprehensiveDefinitionExample,
      title: "Comprehensive",
    },
  };

  const ActiveComponent =
    examples[activeExample as keyof typeof examples]?.component;

  return (
    <div style={{ padding: "20px" }}>
      <h2>LLM API Usage Examples</h2>
      <div style={{ marginBottom: "20px" }}>
        {Object.entries(examples).map(([key, { title }]) => (
          <button
            key={key}
            onClick={() => setActiveExample(key)}
            style={{
              margin: "0 5px",
              padding: "5px 10px",
              backgroundColor: activeExample === key ? "#007bff" : "#f8f9fa",
              color: activeExample === key ? "white" : "black",
              border: "1px solid #ccc",
              borderRadius: "4px",
              cursor: "pointer",
            }}
          >
            {title}
          </button>
        ))}
      </div>

      {ActiveComponent && <ActiveComponent />}
    </div>
  );
};

export default LLMAPIExamples;
