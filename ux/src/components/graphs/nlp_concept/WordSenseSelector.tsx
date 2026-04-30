import React from "react";
import { Alert } from "flowbite-react";
import { Info } from "lucide-react";
import { WordSense } from "@/api/types/ontology";

interface WordSenseSelectorProps {
  title: string;
  persistedSenses: WordSense[];
  nodeId: string;
  onSaveComplete?: () => void;
}

/**
 * WordSenseSelector Component
 *
 * This component is disabled pending backend API implementation.
 */
export const WordSenseSelector: React.FC<WordSenseSelectorProps> = () => {
  return (
    <Alert color="info" icon={Info}>
      Word sense selection is not yet available. This feature requires backend
      API implementation.
    </Alert>
  );
};

export default WordSenseSelector;
