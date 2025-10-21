import { createFileRoute } from "@tanstack/react-router";
import RAGTestPage from "../../components/rag/RAGTestPage";

export const Route = createFileRoute("/app/reference/rag-test")({
  component: RAGTestComponent,
});

function RAGTestComponent() {
  return <RAGTestPage />;
}
