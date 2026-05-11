import { useState } from "react";
import { Loader2 } from "lucide-react";
import { Textarea } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { useSparqlQuery } from "@/api/hooks/graph";
import type { components } from "@/api/types";

type SPARQLResponse = components["schemas"]["SPARQLResponse"];

const PLACEHOLDER_QUERY = `PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?subject ?label ?type
WHERE {
  ?subject rdf:type ?type .
  ?subject rdfs:label ?label .
}
LIMIT 10`;

export function SparqlEditor() {
  const [query, setQuery] = useState("");
  const { mutate, data, isPending, error, isSuccess } = useSparqlQuery();

  const handleRunQuery = () => {
    if (query.trim()) {
      mutate(query);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      if (!isPending && query.trim()) {
        mutate(query);
      }
    }
  };

  const isIdle = !isPending && !data && !error && !isSuccess;
  const isEmpty = isSuccess && data && data.results.length === 0;
  const isPopulated = isSuccess && data && data.results.length > 0;
  const isError = error !== null;

  const columns: string[] = isPopulated && data ? Object.keys(data.results[0]) : [];

  return (
    <div data-testid="sparql-editor" className="stack-lg">
      <div>
        <label htmlFor="sparql-query-textarea" className="form-group-label">SPARQL Query</label>
        <Textarea
          id="sparql-query-textarea"
          data-testid="sparql-query-textarea"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={PLACEHOLDER_QUERY}
          mono={true}
          rows={6}
          style={{
            resize: "vertical",
          }}
          disabled={isPending}
        />
        <div
          style={{
            fontSize: "var(--text-xs)",
            color: "var(--canvas-fg-3)",
            marginTop: "var(--space-2)",
          }}
        >
          Press Ctrl+Enter (or ⌘+Enter on Mac) to run
        </div>
      </div>

      <Button
        data-testid="sparql-run-button"
        onClick={handleRunQuery}
        disabled={isPending || !query.trim()}
        className="btn-primary"
        aria-busy={isPending}
      >
        {isPending ? (
          <>
            <Loader2 size={16} className="animate-spin" data-testid="sparql-loading-spinner" />
            Running...
          </>
        ) : (
          "Run Query"
        )}
      </Button>

      {isError && (
        <div
          data-testid="sparql-error-banner"
          style={{
            padding: "var(--space-3)",
            background: "var(--rose-50)",
            borderRadius: "var(--radius-sm)",
            color: "var(--rose-700)",
            fontSize: "var(--text-sm)",
            border: "1px solid var(--rose-200)",
          }}
        >
          <p style={{ margin: 0, fontWeight: 500, marginBottom: "var(--space-2)" }}>
            Query Error
          </p>
          <p style={{ margin: 0 }}>
            {error instanceof Error ? error.message : "An error occurred while executing the query"}
          </p>
        </div>
      )}

      {isEmpty && (
        <div
          data-testid="sparql-empty-state"
          style={{
            padding: "var(--space-3)",
            background: "var(--canvas-bg-2)",
            borderRadius: "var(--radius-sm)",
            color: "var(--canvas-fg-3)",
            fontSize: "var(--text-sm)",
            textAlign: "center",
          }}
        >
          Query returned no results
        </div>
      )}

      {isIdle && (
        <div
          style={{
            padding: "var(--space-3)",
            background: "var(--canvas-bg-2)",
            borderRadius: "var(--radius-sm)",
            color: "var(--canvas-fg-3)",
            fontSize: "var(--text-sm)",
            textAlign: "center",
          }}
        >
          Enter a SPARQL query and click Run
        </div>
      )}

      {isPopulated && data && (
        <div>
          <div
            style={{
              fontSize: "var(--text-sm)",
              color: "var(--canvas-fg-2)",
              marginBottom: "var(--space-2)",
              fontWeight: 500,
            }}
          >
            {data.results.length} result{data.results.length !== 1 ? "s" : ""}
            {` (${data.triple_count} triples)`}
          </div>
          <div className="table-wrap" style={{ maxHeight: "400px", overflowY: "auto" }}>
            <table className="t" data-testid="sparql-results-table">
              <thead>
                <tr>
                  {columns.map((col) => (
                    <th key={col}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.results.map((row, idx) => (
                  <tr key={idx} data-testid={`sparql-result-row-${idx}`}>
                    {columns.map((col) => (
                      <td key={`${idx}-${col}`} className="mono">
                        {String(row[col] ?? "")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
