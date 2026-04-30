/**
 * Attribute Panel Component
 *
 * Manages the complete attribute workflow: display, creation, editing, and deletion
 */

import React from "react";
import { Alert } from "flowbite-react";
import { AlertCircle } from "lucide-react";

/**
 * @deprecated Attribute management is not yet supported by the backend API
 */

interface AttributePanelProps {
  nodeId: string;
}

export const AttributePanel: React.FC<AttributePanelProps> = ({
  nodeId: _nodeId,
}) => {
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">Attributes</h3>
      <Alert color="info" icon={AlertCircle}>
        <p>
          Attribute management is not yet available. This feature is coming in a
          future release.
        </p>
      </Alert>
    </div>
  );
};
