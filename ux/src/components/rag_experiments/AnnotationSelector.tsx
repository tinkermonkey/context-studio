/**
 * AnnotationSelector Component
 *
 * Allows users to select text spans in a paragraph and link them to structure nodes.
 * Displays existing annotations with highlighting and tooltips.
 */

import React, { useState, useRef, useEffect } from "react";
import { Button, Spinner, Tooltip } from "flowbite-react";
import { Trash2, Plus } from "lucide-react";
import { RecordSelector } from "@/components/node_selectors/record_selector";
import {
  useCreateAnnotation,
  useDeleteAnnotation,
} from "@/api/hooks/ragExperiments";
import { useStructureNodes } from "@/api/hooks/structure_nodes/useStructureNodes";
import type {
  TestParagraphResponse,
  AnnotationResponse,
} from "@/api/services/ragExperiments";
import type { StructureNode } from "@/api/types/structureNodes";

export interface AnnotationSelectorProps {
  paragraph: TestParagraphResponse;
  onAnnotationChange?: () => void;
}

interface TextSelection {
  start: number;
  end: number;
  text: string;
}

export const AnnotationSelector: React.FC<AnnotationSelectorProps> = ({
  paragraph,
  onAnnotationChange,
}) => {
  const [selection, setSelection] = useState<TextSelection | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string>("");
  const textRef = useRef<HTMLDivElement>(null);

  const createAnnotationMutation = useCreateAnnotation();
  const deleteAnnotationMutation = useDeleteAnnotation();

  // Fetch structure nodes for the selector
  const { data: structureNodes, isLoading: nodesLoading } = useStructureNodes({
    limit: 1000,
  });

  // Handle text selection
  const handleTextSelection = () => {
    const windowSelection = window.getSelection();
    if (!windowSelection || windowSelection.rangeCount === 0) {
      return;
    }

    const range = windowSelection.getRangeAt(0);
    const selectedText = range.toString().trim();

    if (!selectedText || !textRef.current) {
      setSelection(null);
      return;
    }

    // Calculate character positions relative to the paragraph text
    const paragraphElement = textRef.current;
    const textContent = paragraphElement.textContent || "";

    // Find the selected text in the paragraph
    const startOffset = textContent.indexOf(selectedText);
    if (startOffset === -1) {
      setSelection(null);
      return;
    }

    const endOffset = startOffset + selectedText.length;

    setSelection({
      start: startOffset,
      end: endOffset,
      text: selectedText,
    });
  };

  // Create annotation
  const handleCreateAnnotation = async () => {
    if (!selection || !selectedNodeId) {
      return;
    }

    await createAnnotationMutation.mutateAsync({
      paragraphId: paragraph.id,
      startChar: selection.start,
      endChar: selection.end,
      structureNodeId: selectedNodeId,
    });

    // Reset selection
    setSelection(null);
    setSelectedNodeId("");
    window.getSelection()?.removeAllRanges();
    onAnnotationChange?.();
  };

  // Delete annotation
  const handleDeleteAnnotation = async (annotationId: string) => {
    try {
      await deleteAnnotationMutation.mutateAsync({
        annotationId,
        paragraphId: paragraph.id,
      });
      onAnnotationChange?.();
    } catch (error) {
      // Error is already handled by the mutation's error state
      // The UI will show the error message below the annotations list
      console.error("Failed to delete annotation:", error);
    }
  };

  // Render paragraph text with highlighted annotations
  const renderAnnotatedText = () => {
    const { text, annotations = [] } = paragraph;

    if (annotations.length === 0) {
      return <span>{text}</span>;
    }

    // Sort annotations by start position
    const sortedAnnotations = [...annotations].sort(
      (a, b) => a.start_char - b.start_char
    );

    const segments: React.ReactNode[] = [];
    let currentPos = 0;

    sortedAnnotations.forEach((annotation, index) => {
      // Add text before annotation
      if (currentPos < annotation.start_char) {
        segments.push(
          <span key={`text-${index}`}>
            {text.substring(currentPos, annotation.start_char)}
          </span>
        );
      }

      // Add annotated text with highlighting
      const annotatedText = text.substring(
        annotation.start_char,
        annotation.end_char
      );
      const nodeInfo = (structureNodes || []).find(
        (n: StructureNode) => n.id === annotation.structure_node_id
      );

      segments.push(
        <Tooltip
          key={`annotation-${annotation.id}`}
          content={
            <div className="max-w-xs">
              <p className="font-medium">{nodeInfo?.title || "Unknown Node"}</p>
              <p className="text-xs mt-1">Click to remove annotation</p>
            </div>
          }
        >
          <span
            className="cursor-pointer rounded bg-yellow-200 px-1 hover:bg-yellow-300"
            onClick={() => handleDeleteAnnotation(annotation.id)}
          >
            {annotatedText}
          </span>
        </Tooltip>
      );

      currentPos = annotation.end_char;
    });

    // Add remaining text
    if (currentPos < text.length) {
      segments.push(
        <span key="text-end">{text.substring(currentPos)}</span>
      );
    }

    return <>{segments}</>;
  };

  const selectedNode = selectedNodeId
    ? (structureNodes || []).find((n: StructureNode) => n.id === selectedNodeId)
    : undefined;

  return (
    <div className="space-y-4">
      {/* Paragraph text with annotations */}
      <div className="rounded-lg border border-gray-300 bg-white p-4">
        <div
          ref={textRef}
          className="select-text whitespace-pre-wrap font-mono text-sm leading-relaxed"
          onMouseUp={handleTextSelection}
        >
          {renderAnnotatedText()}
        </div>
      </div>

      {/* Selection info and annotation creator */}
      {selection && (
        <div className="rounded-lg border border-blue-300 bg-blue-50 p-4">
          <p className="mb-2 text-sm font-medium text-blue-900">
            Selected Text: "{selection.text}"
          </p>
          <p className="mb-3 text-xs text-blue-700">
            Position: {selection.start} - {selection.end}
          </p>

          <div className="space-y-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                Link to Structure Node
              </label>
              {nodesLoading ? (
                <div className="flex items-center gap-2">
                  <Spinner size="sm" />
                  <span className="text-sm text-gray-500">Loading nodes...</span>
                </div>
              ) : (
                <RecordSelector
                  records={structureNodes || []}
                  fieldMap={{ value: "id", title: "title", definition: "definition" }}
                  value={selectedNodeId}
                  onSelect={(node: StructureNode) => setSelectedNodeId(node?.id || "")}
                />
              )}
            </div>

            <div className="flex items-center gap-2">
              <Button
                size="sm"
                onClick={handleCreateAnnotation}
                disabled={!selectedNodeId || createAnnotationMutation.isPending}
              >
                {createAnnotationMutation.isPending ? (
                  <>
                    <Spinner size="sm" className="mr-2" />
                    Creating...
                  </>
                ) : (
                  <>
                    <Plus className="mr-2 h-4 w-4" />
                    Create Annotation
                  </>
                )}
              </Button>
              <Button
                size="sm"
                color="gray"
                onClick={() => {
                  setSelection(null);
                  setSelectedNodeId("");
                  window.getSelection()?.removeAllRanges();
                }}
              >
                Cancel
              </Button>
            </div>
          </div>

          {createAnnotationMutation.error && (
            <div className="mt-2 text-sm text-red-600">
              Error: {createAnnotationMutation.error.message}
            </div>
          )}
        </div>
      )}

      {/* Annotations list */}
      {paragraph.annotations && paragraph.annotations.length > 0 && (
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
          <h4 className="mb-3 text-sm font-medium text-gray-900">
            Annotations ({paragraph.annotations.length})
          </h4>
          <div className="space-y-2">
            {paragraph.annotations.map((annotation) => {
              const nodeInfo = (structureNodes || []).find(
                (n: StructureNode) => n.id === annotation.structure_node_id
              );
              return (
                <div
                  key={annotation.id}
                  className="flex items-start justify-between rounded border border-gray-300 bg-white p-2 text-sm"
                >
                  <div className="flex-1">
                    <p className="font-medium text-gray-900">
                      "{annotation.text}"
                    </p>
                    <p className="text-xs text-gray-600">
                      → {nodeInfo?.title || annotation.structure_node_id}
                    </p>
                    <p className="text-xs text-gray-500">
                      Position: {annotation.start_char} - {annotation.end_char}
                    </p>
                  </div>
                  <Button
                    size="xs"
                    color="failure"
                    onClick={() => handleDeleteAnnotation(annotation.id)}
                    disabled={deleteAnnotationMutation.isPending}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {deleteAnnotationMutation.error && (
        <div className="rounded-lg bg-red-50 p-3 text-sm text-red-800">
          Error deleting annotation: {deleteAnnotationMutation.error.message}
        </div>
      )}
    </div>
  );
};
