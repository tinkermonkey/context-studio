/**
 * ReferenceNodeDisplay Component
 *
 * Read-only display of persisted reference links.
 * Groups by source type and provides remove functionality.
 */

import React, { useState } from "react";
import { Button, Badge, Alert, Spinner, Modal, ModalHeader, ModalBody } from "flowbite-react";
import { ExternalLink, Trash2, AlertCircle } from "lucide-react";

import { ReferenceLink } from "@/api/types/structureNodes";
import { useRemoveReferenceLink } from "@/api/hooks/structure_nodes/useReferenceLinks";
import { getSourceBadgeColor, getSourceLabel, getSourceUrl } from "@/utils/sourceUtils";
import { toast } from "@/utils/toast";

interface ReferenceNodeDisplayProps {
  nodeId: string;
  referenceLinks: ReferenceLink[];
}

interface GroupedLinks {
  [source: string]: ReferenceLink[];
}

export const ReferenceNodeDisplay: React.FC<ReferenceNodeDisplayProps> = ({
  nodeId,
  referenceLinks,
}) => {
  const [confirmRemove, setConfirmRemove] = useState<ReferenceLink | null>(null);

  const removeReferenceLink = useRemoveReferenceLink(nodeId, {
    onSuccess: () => {
      toast.success("Reference link removed successfully");
      setConfirmRemove(null);
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : "Failed to remove reference link"
      );
    },
  });

  const handleRemove = (link: ReferenceLink) => {
    setConfirmRemove(link);
  };

  const confirmRemoveAction = () => {
    if (confirmRemove) {
      removeReferenceLink.mutate([confirmRemove]);
    }
  };

  const handleViewExternal = (url: string, source: string, externalId: string) => {
    if (typeof window !== "undefined" && window.open) {
      window.open(url, "_blank", "noopener,noreferrer");
    } else {
      toast.error("Unable to open external link");
    }
  };

  // Group links by source
  const groupedLinks: GroupedLinks = referenceLinks.reduce((acc, link) => {
    if (!acc[link.source]) {
      acc[link.source] = [];
    }
    acc[link.source].push(link);
    return acc;
  }, {} as GroupedLinks);

  // Sort sources alphabetically
  const sortedSources = Object.keys(groupedLinks).sort();

  if (referenceLinks.length === 0) {
    return null;
  }

  return (
    <div className="space-y-4">
      {sortedSources.map((source) => {
        const links = groupedLinks[source];
        const sourceLabel = getSourceLabel(source);

        return (
          <div key={source} className="border-t pt-4">
            <h4 className="mb-3 flex items-center gap-2 text-md font-medium">
              <Badge color={getSourceBadgeColor(source)}>{sourceLabel}</Badge>
              <span className="text-gray-500 text-sm">
                ({links.length} link{links.length !== 1 ? "s" : ""})
              </span>
            </h4>

            <div className="space-y-2" role="list" aria-label={`${sourceLabel} reference links`}>
              {links.map((link, index) => {
                const linkKey = `${link.source}-${link.external_id}-${index}`;
                const sourceUrl = getSourceUrl(link.source, link.external_id);

                return (
                  <div
                    key={linkKey}
                    className="flex items-center justify-between border rounded-lg p-3 bg-gray-50"
                    role="listitem"
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <code className="text-sm font-mono text-gray-700">
                          {link.external_id}
                        </code>
                        {sourceUrl && (
                          <Button
                            size="xs"
                            color="gray"
                            onClick={() => handleViewExternal(sourceUrl, link.source, link.external_id)}
                            className="flex items-center gap-1"
                            aria-label={`View ${link.external_id} on ${sourceLabel}`}
                          >
                            <ExternalLink className="h-3 w-3" />
                            View
                          </Button>
                        )}
                      </div>
                    </div>
                    <Button
                      size="xs"
                      color="failure"
                      onClick={() => handleRemove(link)}
                      disabled={removeReferenceLink.isPending}
                      aria-label={`Remove reference link ${link.external_id} from ${sourceLabel}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}

      {/* Confirmation Modal */}
      <Modal
        show={confirmRemove !== null}
        onClose={() => setConfirmRemove(null)}
        size="md"
      >
        <ModalHeader>Confirm Removal</ModalHeader>
        <ModalBody>
          <div className="space-y-4">
            <Alert color="warning" icon={AlertCircle}>
              <p className="text-sm">
                Are you sure you want to remove this reference link?
              </p>
            </Alert>

            {confirmRemove && (
              <div className="border rounded-lg p-3 bg-gray-50">
                <div className="flex items-center gap-2 mb-2">
                  <Badge color={getSourceBadgeColor(confirmRemove.source)}>
                    {getSourceLabel(confirmRemove.source)}
                  </Badge>
                </div>
                <code className="text-sm font-mono text-gray-700">
                  {confirmRemove.external_id}
                </code>
              </div>
            )}

            <div className="flex gap-2 justify-end">
              <Button
                color="gray"
                onClick={() => setConfirmRemove(null)}
                disabled={removeReferenceLink.isPending}
              >
                Cancel
              </Button>
              <Button
                color="failure"
                onClick={confirmRemoveAction}
                disabled={removeReferenceLink.isPending}
              >
                {removeReferenceLink.isPending ? (
                  <>
                    <Spinner size="sm" className="mr-2" />
                    Removing...
                  </>
                ) : (
                  <>
                    <Trash2 className="mr-2 h-4 w-4" />
                    Remove
                  </>
                )}
              </Button>
            </div>
          </div>
        </ModalBody>
      </Modal>
    </div>
  );
};

export default ReferenceNodeDisplay;
