/**
 * ReferenceNodeSelectionList Component
 *
 * This component is disabled pending backend API implementation.
 */

import React from "react";
import { Alert } from "flowbite-react";
import { Info } from "lucide-react";

interface ReferenceNodeSelectionListProps {
  nodeId: string;
  selectedNodes: any[];
  onRemoveNode: (node: any) => void;
  onClearAll: () => void;
  onSaveSuccess: () => void;
}

export const ReferenceNodeSelectionList: React.FC<
  ReferenceNodeSelectionListProps
> = () => {
  return (
    <Alert color="info" icon={Info}>
      Reference node selection is not yet available. This feature requires
      backend API implementation.
    </Alert>
  );
};

export default ReferenceNodeSelectionList;
