/**
 * Attribute List Component
 *
 * Displays resolved attributes with visual distinction for inherited vs local
 */

import React, { useMemo } from "react";
import { Badge, Button, Tooltip } from "flowbite-react";
import { Edit2, Link, Trash2 } from "lucide-react";
import type {
  ResolvedAttribute,
  StructureNodeAttribute,
} from "@/api/types/structureNodes";
import { useStructureNode } from "@/api/hooks/structure_nodes/useStructureNodes";

interface AttributeListProps {
  attributes: ResolvedAttribute[];
  onRemoveAttribute?: (key: string) => void;
  onEditAttribute?: (attribute: StructureNodeAttribute) => void;
  isLoading?: boolean;
}

const AttributeTypeDisplay: React.FC<{ type: string }> = ({ type }) => {
  const colorMap: Record<string, string> = {
    string: "blue",
    number: "green",
    boolean: "purple",
    date: "orange",
    url: "red",
  };

  return (
    <Badge color={colorMap[type] || "gray"} size="sm">
      {type}
    </Badge>
  );
};

const AttributeValueDisplay: React.FC<{
  value: unknown;
  maxLength?: number;
}> = ({ value, maxLength = 50 }) => {
  const displayValue =
    value === null || value === undefined ? "(empty)" : String(value);
  const isTruncated = displayValue.length > maxLength;
  const truncatedValue = isTruncated
    ? displayValue.substring(0, maxLength) + "..."
    : displayValue;

  if (!isTruncated) {
    return <span className="text-gray-700">{truncatedValue}</span>;
  }

  return (
    <Tooltip content={displayValue}>
      <span className="cursor-help text-gray-700">{truncatedValue}</span>
    </Tooltip>
  );
};

const InheritedAttributeInfo: React.FC<{
  sourceNodeId: string | null | undefined;
}> = ({ sourceNodeId }) => {
  const { data: sourceNode } = useStructureNode(sourceNodeId || "");

  const sourceTitle = sourceNode?.title || "Unknown node";

  return (
    <Tooltip content={`Inherited from: ${sourceTitle}`}>
      <div className="flex items-center gap-1 text-blue-600">
        <Link className="h-4 w-4" />
        <span className="text-xs">inherited</span>
      </div>
    </Tooltip>
  );
};

export const AttributeList: React.FC<AttributeListProps> = ({
  attributes,
  onRemoveAttribute,
  onEditAttribute,
  isLoading = false,
}) => {
  const localAttributes = useMemo(
    () => attributes.filter((a) => !a.inherited),
    [attributes],
  );

  const inheritedAttributes = useMemo(
    () => attributes.filter((a) => a.inherited),
    [attributes],
  );

  if (isLoading) {
    return (
      <div className="py-4 text-center text-gray-500">
        <p>Loading attributes...</p>
      </div>
    );
  }

  if (attributes.length === 0) {
    return (
      <div className="py-4 text-center text-gray-500">
        <p>No attributes</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {localAttributes.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-gray-700">
            Local Attributes
          </h3>
          <div className="space-y-2">
            {localAttributes.map((attr) => (
              <div
                key={attr.key}
                className="flex items-center justify-between rounded-md border border-gray-200 bg-white p-2 hover:bg-gray-50"
              >
                <div className="flex-1 space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-900">
                      {attr.title || attr.key}
                    </span>
                    <AttributeTypeDisplay type={attr.value_type} />
                  </div>
                  <div>
                    <AttributeValueDisplay value={attr.value} />
                  </div>
                </div>
                <div className="ml-2 flex gap-1">
                  {onEditAttribute && (
                    <Button
                      size="sm"
                      color="light"
                      onClick={() =>
                        onEditAttribute(attr as StructureNodeAttribute)
                      }
                      disabled={isLoading}
                    >
                      <Edit2 className="h-4 w-4" />
                    </Button>
                  )}
                  {onRemoveAttribute && (
                    <Button
                      size="sm"
                      color="light"
                      onClick={() => onRemoveAttribute(attr.key)}
                      disabled={isLoading}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {inheritedAttributes.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-gray-700">
            Inherited Attributes
          </h3>
          <div className="space-y-2">
            {inheritedAttributes.map((attr) => (
              <div
                key={attr.key}
                className="flex items-center justify-between rounded-md border border-blue-200 bg-blue-50 p-2 opacity-75"
              >
                <div className="flex-1 space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-900">
                      {attr.title || attr.key}
                    </span>
                    <AttributeTypeDisplay type={attr.value_type} />
                    <InheritedAttributeInfo
                      sourceNodeId={attr.source_node_id}
                    />
                  </div>
                  <div>
                    <AttributeValueDisplay value={attr.value} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
