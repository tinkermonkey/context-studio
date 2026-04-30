/**
 * ReferenceNodeDisplay Component
 *
 * This component is disabled pending backend API implementation.
 */

import React from "react";
import { Alert } from "flowbite-react";
import { Info } from "lucide-react";

interface ReferenceNodeDisplayProps {
  nodeId: string;
  referenceLinks: any[];
}

export const ReferenceNodeDisplay: React.FC<ReferenceNodeDisplayProps> = () => {
  return (
    <Alert color="info" icon={Info}>
      Reference node display is not yet available. This feature requires backend
      API implementation.
    </Alert>
  );
};

export default ReferenceNodeDisplay;
