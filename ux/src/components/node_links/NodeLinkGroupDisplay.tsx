/**
 * NodeLinkGroupDisplay Component
 *
 * Displays a group of links that share the same predicate
 */

import React from "react";
// removed import;

import { StructureNodeLink } from "@/api/types/structureNodes";
import { NodeLinkItem } from "./NodeLinkItem";

interface NodeLinkGroupDisplayProps {
  predicate: string;
  links: StructureNodeLink[];
  currentNodeId: string;
  onDelete: (linkId: string) => void;
  deletingLinkId?: string;
}

export const NodeLinkGroupDisplay: React.FC<NodeLinkGroupDisplayProps> = ({
  predicate,
  links,
  currentNodeId,
  onDelete,
  deletingLinkId,
}) => {
  if (links.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2">
      <h4 className="flex items-center gap-2 text-sm font-medium">
        <Badge color="blue">{predicate}</Badge>
        <span className="text-gray-500">
          ({links.length} link{links.length !== 1 ? "s" : ""})
        </span>
      </h4>

      <div
        className="space-y-2 pl-2"
        role="list"
        aria-label={`Links with predicate ${predicate}`}
      >
        {links.map((link) => (
          <NodeLinkItem
            key={link.id}
            link={link}
            currentNodeId={currentNodeId}
            onDelete={onDelete}
            isDeleting={deletingLinkId === link.id}
          />
        ))}
      </div>
    </div>
  );
};
