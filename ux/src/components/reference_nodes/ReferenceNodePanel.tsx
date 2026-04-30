/**
 * ReferenceNodePanel Component
 *
 * Container component that manages state for reference node search, selection, and display.
 * Coordinates between search interface and persisted reference display.
 */

import React from "react";
import { Alert } from "flowbite-react";
import { Info } from "lucide-react";

interface ReferenceNodePanelProps {
  nodeId: string;
  nodeTitle?: string;
}

/**
 * ReferenceNodePanel Component
 *
 * Displays a message that reference node management is not yet available.
 * This feature requires backend API implementation for managing reference links.
 */
export const ReferenceNodePanel: React.FC<ReferenceNodePanelProps> = () => {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-xl font-semibold">
          Reference Nodes
        </h2>
      </div>

      <Alert color="info" icon={Info}>
        <div className="space-y-2">
          <p className="font-medium">Reference node management coming soon</p>
          <p className="text-sm text-gray-600">
            This feature is not yet available. Reference node management will be
            enabled once the backend API is implemented.
          </p>
        </div>
      </Alert>
    </div>
  );
};

export default ReferenceNodePanel;
