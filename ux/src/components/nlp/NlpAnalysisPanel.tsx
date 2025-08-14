import React, { useState, useEffect, useCallback } from 'react';
import { Button, Spinner } from 'flowbite-react';
import { InlineApiError } from '@/components/misc/error_boundary';
import { useNLPAnalysis } from '@/api/hooks/nlp/useNLPAnalysis';
import { apiLogger } from '@/api/utils/logger';

interface NlpAnalysisPanelProps {
  text: string;
}

export const NlpAnalysisPanel: React.FC<NlpAnalysisPanelProps> = ({ text }) => {
  const [pendingText, setPendingText] = useState(text);
  const [debouncedText, setDebouncedText] = useState(text);
  const [hasAnalyzed, setHasAnalyzed] = useState(false);

  // Custom hook for API call
  const lowercasedText = debouncedText.toLowerCase();
  const queryKey = ["nlp", "analysis", JSON.stringify({ text: lowercasedText })];
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
      apiLogger.info('NLP analysis re-triggered due to text change');
    }, 1000);
    return () => clearTimeout(handler);
  }, [pendingText, hasAnalyzed, refetch]);

  // Error handling
  useEffect(() => {
    if (error) {
      apiLogger.error('NLP analysis error', { error });
    }
  }, [error]);

  // Analyze button click
  const handleAnalyze = useCallback(() => {
    setDebouncedText(pendingText);
    setHasAnalyzed(true);
    refetch(); // refetch will use lowercasedText due to hook dependency
    apiLogger.info('NLP analysis triggered by user');
  }, [pendingText, refetch]);

  return (
    <>
      <Button onClick={handleAnalyze} disabled={loading || !pendingText} color="dark">
        {loading ? <Spinner size="sm" /> : hasAnalyzed ? 'Analyze Again' : 'Analyze'}
      </Button>
      <div className="mt-2">
        {analysisResult && (
          <pre className="bg-gray-100 p-2 rounded text-xs overflow-x-auto">
            {JSON.stringify(analysisResult, null, 2)}
          </pre>
        )}
        {error && (
          <InlineApiError error={error} className="mt-2" showDetails />
        )}
      </div>
    </>
  );
};
