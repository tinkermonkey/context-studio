/**
 * TestParagraphList Component
 *
 * Displays a list of test paragraphs with edit and delete actions
 */

import React, { useState } from "react";
import {
  Badge,
  Button,
  Spinner,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeadCell,
  TableRow,
} from "flowbite-react";
import { Edit, Plus, Trash2 } from "lucide-react";
import {
  useTestParagraphs,
  useDeleteTestParagraph,
} from "@/api/hooks/ragExperiments";
import type { TestParagraphResponse } from "@/api/services/ragExperiments";

export interface TestParagraphListProps {
  onEdit?: (paragraph: TestParagraphResponse) => void;
  onCreateNew?: () => void;
}

export const TestParagraphList: React.FC<TestParagraphListProps> = ({
  onEdit,
  onCreateNew,
}) => {
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const { data, isLoading, error, refetch } = useTestParagraphs({ limit: 100 });
  const deleteMutation = useDeleteTestParagraph();

  const paragraphs = data?.paragraphs || [];

  const handleDelete = async (paragraphId: string) => {
    if (!confirm("Are you sure you want to delete this test paragraph?")) {
      return;
    }

    setDeletingId(paragraphId);
    try {
      await deleteMutation.mutateAsync(paragraphId);
      await refetch();
    } catch (err) {
      console.error("Failed to delete paragraph:", err);
    } finally {
      setDeletingId(null);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Spinner size="lg" />
        <span className="ml-3 text-gray-600">Loading test paragraphs...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg bg-red-50 p-4">
        <p className="text-sm text-red-800">
          Error loading paragraphs: {error.message}
        </p>
        <Button
          size="sm"
          color="gray"
          onClick={() => refetch()}
          className="mt-2"
        >
          Retry
        </Button>
      </div>
    );
  }

  if (paragraphs.length === 0) {
    return (
      <div
        className="rounded-lg border border-gray-200 bg-gray-50 p-8 text-center"
        data-testid="test-paragraph-list"
      >
        <p className="mb-4 text-gray-600">No test paragraphs yet.</p>
        {onCreateNew && (
          <Button
            size="sm"
            onClick={onCreateNew}
            data-testid="test-paragraph-create-button"
          >
            <Plus className="mr-2 h-4 w-4" />
            Create First Paragraph
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="test-paragraph-list">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-600">
            {paragraphs.length} test paragraph
            {paragraphs.length !== 1 ? "s" : ""}
          </p>
        </div>
        {onCreateNew && (
          <Button
            size="sm"
            onClick={onCreateNew}
            data-testid="test-paragraph-create-button"
          >
            <Plus className="mr-2 h-4 w-4" />
            Create New
          </Button>
        )}
      </div>

      <div className="overflow-x-auto">
        <Table data-testid="test-paragraph-table">
          <TableHead>
            <TableRow>
              <TableHeadCell>Text Preview</TableHeadCell>
              <TableHeadCell>Notes</TableHeadCell>
              <TableHeadCell>Annotations</TableHeadCell>
              <TableHeadCell>Actions</TableHeadCell>
            </TableRow>
          </TableHead>
          <TableBody className="divide-y">
            {paragraphs.map((paragraph) => (
              <TableRow
                key={paragraph.id}
                className="bg-white dark:border-gray-700 dark:bg-gray-800"
              >
                <TableCell className="max-w-md">
                  <div className="font-medium text-gray-900 dark:text-white">
                    {paragraph.text.length > 100
                      ? `${paragraph.text.substring(0, 100)}...`
                      : paragraph.text}
                  </div>
                  <div className="text-xs text-gray-500">
                    {paragraph.text.length} characters
                  </div>
                </TableCell>
                <TableCell>
                  {paragraph.notes ? (
                    <span className="text-sm text-gray-600">
                      {paragraph.notes}
                    </span>
                  ) : (
                    <span className="text-sm text-gray-400 italic">
                      No notes
                    </span>
                  )}
                </TableCell>
                <TableCell>
                  <Badge
                    color={paragraph.annotations?.length ? "success" : "gray"}
                  >
                    {paragraph.annotations?.length || 0} annotation
                    {paragraph.annotations?.length !== 1 ? "s" : ""}
                  </Badge>
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Button
                      size="xs"
                      color="gray"
                      onClick={() => onEdit?.(paragraph)}
                      data-testid={`test-paragraph-edit-button-${paragraph.id}`}
                    >
                      <Edit className="h-3 w-3" />
                    </Button>
                    <Button
                      size="xs"
                      color="failure"
                      onClick={() => handleDelete(paragraph.id)}
                      disabled={deletingId === paragraph.id}
                      data-testid={`test-paragraph-delete-button-${paragraph.id}`}
                    >
                      {deletingId === paragraph.id ? (
                        <Spinner size="xs" />
                      ) : (
                        <Trash2 className="h-3 w-3" />
                      )}
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
};
