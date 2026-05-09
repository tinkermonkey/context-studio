import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Breadcrumb, Tabs } from "flowbite-react";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import { Home, FlaskConical } from "lucide-react";
import { Link } from "@tanstack/react-router";
import {
  TestParagraphEditor,
  TestParagraphList,
  PipelineTestRunner,
  TestResultsViewer,
  AnnotationSelector,
} from "@/components/rag_experiments";
import type {
  RunPipelineTestResponse,
  TestParagraphResponse,
} from "@/api/services/ragExperiments";
import { CsSidebar } from "@/components/layout/cs_sidebar";
import { useTestParagraph } from "@/api/hooks/ragExperiments/useRAGExperimentsQueries";

export const Route = createFileRoute("/app/rag/experiments")({
  component: RAGExperimentsPage,
});

function RAGExperimentsPage() {
  const [testResults, setTestResults] = useState<{
    paragraphId: string;
    pipelineNames: string[];
  } | null>(null);
  const [editingParagraph, setEditingParagraph] =
    useState<TestParagraphResponse | null>(null);
  const [showEditor, setShowEditor] = useState(false);

  // Fetch full paragraph data with annotations when editing
  const { data: fullParagraphData, refetch: refetchParagraph } =
    useTestParagraph(editingParagraph?.id);

  const handleTestComplete = (results: RunPipelineTestResponse) => {
    // Extract unique paragraph IDs and pipeline names from results
    if (!results.results) return;

    const paragraphIds = Array.from(
      new Set(results.results.map((r) => r.paragraph_id).filter((id) => id)),
    ) as string[];
    const pipelineNames = Array.from(
      new Set(
        results.results.map((r) => r.pipeline_name).filter((name) => name),
      ),
    ) as string[];

    // For now, show results for the first paragraph
    // In a full implementation, we might want to show results for all paragraphs
    if (paragraphIds.length > 0) {
      setTestResults({
        paragraphId: paragraphIds[0] || "",
        pipelineNames,
      });
    }
  };

  const handleEdit = (paragraph: TestParagraphResponse) => {
    setEditingParagraph(paragraph);
    setShowEditor(true);
  };

  const handleCreateNew = () => {
    setEditingParagraph(null);
    setShowEditor(true);
  };

  const handleEditorSuccess = () => {
    // Don't close the editor immediately - allow annotation after save
    // Just refetch to get the updated paragraph data
    if (editingParagraph?.id) {
      refetchParagraph();
    }
  };

  const handleEditorCancel = () => {
    setEditingParagraph(null);
    setShowEditor(false);
  };

  const handleAnnotationChange = () => {
    // Refetch paragraph data to get updated annotations
    refetchParagraph();
  };

  const handleCloseEditor = () => {
    setEditingParagraph(null);
    setShowEditor(false);
  };

  return (
    <>
      <CsSidebar></CsSidebar>
      <CsMain>
        {/* Breadcrumbs */}
        <Breadcrumb className="mb-4">
          <div className="flex items-center space-x-2 text-sm text-gray-500">
            <Link
              to="/app"
              className="flex items-center gap-1 hover:text-blue-600"
            >
              <Home className="h-4 w-4" />
              Home
            </Link>
            <span>/</span>
            <span className="text-gray-900 dark:text-white">
              RAG Experiments
            </span>
          </div>
        </Breadcrumb>

        <CsMainTitle>RAG Pipeline Experiments</CsMainTitle>

        <div className="mb-4 text-sm text-gray-600 dark:text-gray-400">
          <p>
            Test and compare RAG pipeline performance by creating test
            paragraphs, annotating expected entities, and running pipeline
            tests.
          </p>
        </div>

        {/* Tabs for workflow */}
        <Tabs aria-label="RAG Experiments Workflow">
          <Tabs.Item active title="Test Paragraphs" icon={FlaskConical}>
            <div className="space-y-6">
              {/* Paragraph List */}
              <div className="rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
                <h3 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
                  Test Paragraphs
                </h3>
                <p className="mb-6 text-sm text-gray-600 dark:text-gray-400">
                  Manage test paragraphs that will be used to evaluate RAG
                  pipeline effectiveness.
                </p>
                <TestParagraphList
                  onEdit={handleEdit}
                  onCreateNew={handleCreateNew}
                />
              </div>

              {/* Editor (shown when creating or editing) */}
              {showEditor && (
                <>
                  <div className="rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
                    <h3 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
                      {editingParagraph
                        ? "Edit Paragraph"
                        : "Create New Paragraph"}
                    </h3>
                    <TestParagraphEditor
                      paragraph={editingParagraph || undefined}
                      onSuccess={handleEditorSuccess}
                      onCancel={handleEditorCancel}
                    />
                  </div>

                  {/* Annotation Selector (only for existing paragraphs) */}
                  {fullParagraphData && (
                    <div className="rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
                      <div className="mb-4 flex items-center justify-between">
                        <div>
                          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                            Annotate Expected Entities
                          </h3>
                          <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                            Select text spans and link them to structure nodes
                            to define the ground truth for testing pipeline
                            accuracy.
                          </p>
                        </div>
                        <button
                          onClick={handleCloseEditor}
                          className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800 focus:ring-4 focus:ring-blue-300 focus:outline-none dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
                        >
                          Done
                        </button>
                      </div>
                      <AnnotationSelector
                        paragraph={fullParagraphData}
                        onAnnotationChange={handleAnnotationChange}
                      />
                    </div>
                  )}
                </>
              )}
            </div>
          </Tabs.Item>

          <Tabs.Item title="Run Tests" icon={FlaskConical}>
            <div className="rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
              <h3 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
                Run Pipeline Tests
              </h3>
              <p className="mb-6 text-sm text-gray-600 dark:text-gray-400">
                Select test paragraphs and pipelines to compare their
                performance in parallel.
              </p>
              <PipelineTestRunner onTestComplete={handleTestComplete} />
            </div>
          </Tabs.Item>

          <Tabs.Item title="Results" icon={FlaskConical}>
            <div className="rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
              <h3 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
                Test Results
              </h3>
              <p className="mb-6 text-sm text-gray-600 dark:text-gray-400">
                View and compare pipeline test results, including precision,
                recall, and F1 scores.
              </p>
              {testResults ? (
                <TestResultsViewer
                  paragraphId={testResults.paragraphId}
                  pipelineNames={testResults.pipelineNames}
                />
              ) : (
                <div className="rounded-lg bg-gray-50 p-8 text-center dark:bg-gray-900">
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    No test results yet. Run tests from the "Run Tests" tab to
                    see results here.
                  </p>
                </div>
              )}
            </div>
          </Tabs.Item>
        </Tabs>
      </CsMain>
    </>
  );
}
