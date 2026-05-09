/**
 * NodeLinkDisplay Component
 *
 * Displays all links for a node, organized by direction (outgoing/incoming)
 * and grouped by predicate
 */

import React, { useState, useMemo } from "react";

import { OntologyClassLink } from "@/api/types/ontology";
import { useDeleteRelationship } from "@/api/hooks/relationships";
import { toast } from "@/utils/toast";
import { NodeLinkGroupDisplay } from "./NodeLinkGroupDisplay";

interface NodeLinkDisplayProps {
  links: OntologyClassLink[];
  currentNodeId: string;
}

interface GroupedLinks {
  [predicate: string]: OntologyClassLink[];
}

export const NodeLinkDisplay: React.FC<NodeLinkDisplayProps> = ({
  links,
  currentNodeId,
}) => {
  const [deletingLinkId, setDeletingLinkId] = useState<string | undefined>();

  const deleteRelationship = useDeleteRelationship({
    onSuccess: () => {
      toast.success("Link deleted successfully");
      setDeletingLinkId(undefined);
    },
    onError: (error: Error) => {
      toast.error(
        error instanceof Error ? error.message : "Failed to delete link",
      );
      setDeletingLinkId(undefined);
    },
  });

  const handleDelete = (linkId: string) => {
    setDeletingLinkId(linkId);
    deleteRelationship.mutate(linkId);
  };

  // Separate links into outgoing and incoming
  const { outgoingLinks, incomingLinks } = useMemo(() => {
    const outgoing = links.filter((link) => link.source_id === currentNodeId);
    const incoming = links.filter((link) => link.target_id === currentNodeId);
    return { outgoingLinks: outgoing, incomingLinks: incoming };
  }, [links, currentNodeId]);

  // Group links by predicate
  const groupByPredicate = (linksList: OntologyClassLink[]): GroupedLinks => {
    return linksList.reduce((acc, link) => {
      if (!acc[link.property_definition_id]) {
        acc[link.property_definition_id] = [];
      }
      acc[link.property_definition_id].push(link);
      return acc;
    }, {} as GroupedLinks);
  };

  const groupedOutgoing = useMemo(
    () => groupByPredicate(outgoingLinks),
    [outgoingLinks],
  );
  const groupedIncoming = useMemo(
    () => groupByPredicate(incomingLinks),
    [incomingLinks],
  );

  const hasOutgoing = outgoingLinks.length > 0;
  const hasIncoming = incomingLinks.length > 0;

  if (!hasOutgoing && !hasIncoming) {
    return null;
  }

  return (
    <div className="space-y-6">
      {/* Outgoing Links */}
      {hasOutgoing && (
        <div>
          <h3 className="mb-3 text-lg font-medium">
            Outgoing Links ({outgoingLinks.length})
          </h3>
          <div className="space-y-4">
            {Object.keys(groupedOutgoing)
              .sort()
              .map((predicate) => (
                <NodeLinkGroupDisplay
                  key={`outgoing-${predicate}`}
                  predicate={predicate}
                  links={groupedOutgoing[predicate]}
                  currentNodeId={currentNodeId}
                  onDelete={handleDelete}
                  deletingLinkId={deletingLinkId}
                />
              ))}
          </div>
        </div>
      )}

      {/* Incoming Links */}
      {hasIncoming && (
        <div>
          <h3 className="mb-3 text-lg font-medium">
            Incoming Links ({incomingLinks.length})
          </h3>
          <div className="space-y-4">
            {Object.keys(groupedIncoming)
              .sort()
              .map((predicate) => (
                <NodeLinkGroupDisplay
                  key={`incoming-${predicate}`}
                  predicate={predicate}
                  links={groupedIncoming[predicate]}
                  currentNodeId={currentNodeId}
                  onDelete={handleDelete}
                  deletingLinkId={deletingLinkId}
                />
              ))}
          </div>
        </div>
      )}
    </div>
  );
};
