import * as React from "react";
import { useState, useEffect, useCallback } from "react";
import { Button, Spinner } from "flowbite-react";
import { useNLPAnalysis } from "@/api/hooks/nlp/useNLPAnalysis";
import { apiLogger } from "@/api/utils/logger";
import TokenSelectionList from "@/components/nlp/TokenSelectionList";
import NlpEntityAnalysis from "@/components/nlp/NlpEntityAnalysis";
import {
  ApiErrorBoundary,
  InlineApiError,
} from "@/components/misc/error_boundary";
import { TokenNlpAnalysis } from "@/components/nlp/TokenNlpAnalysis";

interface NlpAnalysisPanelProps {
  text: string;
}

export const NlpAnalysisPanel: React.FC<NlpAnalysisPanelProps> = ({ text }) => {
  const [pendingText, setPendingText] = useState(text);
  const [debouncedText, setDebouncedText] = useState(text);
  const [hasAnalyzed, setHasAnalyzed] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [selectedToken, setSelectedToken] = useState<any | null>(null);

  // Custom hook for API call
  const lowercasedText = debouncedText.toLowerCase();
  const queryKey = [
    "nlp",
    "analysis",
    JSON.stringify({ text: lowercasedText }),
  ];
  const {
    data: analysisResult,
    isLoading: loading,
    error,
    refetch,
  } = useNLPAnalysis(lowercasedText, { enabled: false, queryKey });

  // Sync prop text changes
  useEffect(() => {
    setPendingText(text);
    if (!hasAnalyzed) {
      setDebouncedText(text);
    }
  }, [text, hasAnalyzed]);

  // Debounce text changes after analysis
  useEffect(() => {
    if (!hasAnalyzed) return;
    const handler = setTimeout(() => {
      setDebouncedText(pendingText);
      refetch(); // refetch will use lowercasedText due to hook dependency
      apiLogger.info("NLP analysis re-triggered due to text change");
    }, 1000);
    return () => clearTimeout(handler);
  }, [pendingText, hasAnalyzed, refetch]);

  // Error handling
  useEffect(() => {
    if (error) {
      apiLogger.error("NLP analysis error", { error });
    }
  }, [error]);

  // Analyze button click
  const handleAnalyze = useCallback(() => {
    setDebouncedText(pendingText);
    setHasAnalyzed(true);
    setIsAnalyzing(true);
    refetch(); // refetch will use lowercasedText due to hook dependency
    apiLogger.info("NLP analysis triggered by user");
  }, [pendingText, refetch]);

  // Reset isAnalyzing when loading finishes
  useEffect(() => {
    if (!loading && isAnalyzing) {
      setIsAnalyzing(false);
    }
  }, [loading, isAnalyzing]);

  return (
    <>
      <div className="flex items-center gap-3">
        <Button
          onClick={handleAnalyze}
          disabled={loading || isAnalyzing || !pendingText}
          color="dark"
        >
          {loading || isAnalyzing ? (
            <Spinner size="sm" />
          ) : hasAnalyzed ? (
            "Analyze Again"
          ) : (
            "Analyze"
          )}
        </Button>
      </div>

      <div className="mt-3 space-y-3">
        {error && <InlineApiError error={error} className="mt-2" showDetails />}

        {analysisResult && (
          <>
            <div className="space-y-3">
              <div>
                <h4 className="text-sm font-medium">Token Analysis</h4>
                <ApiErrorBoundary
                  showDetails={process.env.NODE_ENV === "development"}
                >
                  <TokenSelectionList
                    tokens={analysisResult.tokens || []}
                    selectedToken={selectedToken}
                    onTokenSelect={(t) => setSelectedToken(t)}
                  />
                </ApiErrorBoundary>
              </div>

              <div>
                <h4 className="text-sm font-medium">Entities</h4>
                <ApiErrorBoundary
                  showDetails={process.env.NODE_ENV === "development"}
                >
                  <NlpEntityAnalysis
                    entities={analysisResult.entities || []}
                    onEntitySelect={(e) => {}}
                  />
                </ApiErrorBoundary>
              </div>

              <div>
                <h4 className="text-sm font-medium">Selected Token</h4>
                <ApiErrorBoundary
                  showDetails={process.env.NODE_ENV === "development"}
                >
                  {selectedToken ? (
                    <React.Suspense
                      fallback={
                        <div className="flex items-center gap-2">
                          <Spinner size="sm" />{" "}
                          <span className="text-sm text-gray-500">
                            Loading details...
                          </span>
                        </div>
                      }
                    >
                      <TokenNlpAnalysis token={selectedToken} />
                    </React.Suspense>
                  ) : (
                    <div className="text-sm text-gray-500">
                      Select a token to view details
                    </div>
                  )}
                </ApiErrorBoundary>
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
};
