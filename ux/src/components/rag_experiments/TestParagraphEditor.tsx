/**
 * TestParagraphEditor Component
 *
 * Form for creating and editing test paragraphs for RAG pipeline testing
 */

import React, { useState, useEffect } from "react";
import { Button, Label, Textarea, TextInput, Spinner } from "flowbite-react";
import { Save, X } from "lucide-react";
import {
  useCreateTestParagraph,
  useUpdateTestParagraph,
} from "@/api/hooks/ragExperiments";
import type { TestParagraphResponse } from "@/api/services/ragExperiments";

export interface TestParagraphEditorProps {
  paragraph?: TestParagraphResponse;
  onSuccess?: (paragraph: TestParagraphResponse) => void;
  onCancel?: () => void;
}

export const TestParagraphEditor: React.FC<TestParagraphEditorProps> = ({
  paragraph,
  onSuccess,
  onCancel,
}) => {
  const [text, setText] = useState(paragraph?.text || "");
  const [notes, setNotes] = useState(paragraph?.notes || "");

  const createMutation = useCreateTestParagraph();
  const updateMutation = useUpdateTestParagraph();

  const isEditing = !!paragraph;
  const isLoading = createMutation.isPending || updateMutation.isPending;
  const error = createMutation.error || updateMutation.error;

  // Update form when paragraph prop changes
  useEffect(() => {
    if (paragraph) {
      setText(paragraph.text);
      setNotes(paragraph.notes || "");
    }
  }, [paragraph]);

  // Handle successful mutations
  useEffect(() => {
    if (createMutation.isSuccess && createMutation.data) {
      onSuccess?.(createMutation.data);
      // Reset form after creation
      setText("");
      setNotes("");
    }
  }, [createMutation.isSuccess, createMutation.data, onSuccess]);

  useEffect(() => {
    if (updateMutation.isSuccess && updateMutation.data) {
      onSuccess?.(updateMutation.data);
    }
  }, [updateMutation.isSuccess, updateMutation.data, onSuccess]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!text.trim()) {
      return;
    }

    if (isEditing && paragraph) {
      updateMutation.mutate({
        paragraphId: paragraph.id,
        text: text.trim(),
        notes: notes.trim() || undefined,
      });
    } else {
      createMutation.mutate({
        text: text.trim(),
        notes: notes.trim() || undefined,
      });
    }
  };

  const handleCancel = () => {
    if (isEditing && paragraph) {
      // Reset to original values
      setText(paragraph.text);
      setNotes(paragraph.notes || "");
    } else {
      // Clear form
      setText("");
      setNotes("");
    }
    onCancel?.();
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <Label htmlFor="paragraph-text">Paragraph Text</Label>
        <Textarea
          id="paragraph-text"
          placeholder="Enter the test paragraph text..."
          rows={6}
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={isLoading}
          required
          className="mt-1"
        />
        <p className="mt-1 text-sm text-gray-500">
          {text.length} characters
        </p>
      </div>

      <div>
        <Label htmlFor="paragraph-notes">Notes (Optional)</Label>
        <TextInput
          id="paragraph-notes"
          type="text"
          placeholder="Add notes about this test paragraph..."
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          disabled={isLoading}
          className="mt-1"
        />
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 p-4 text-sm text-red-800">
          <p className="font-medium">Error</p>
          <p>{error instanceof Error ? error.message : "An error occurred"}</p>
        </div>
      )}

      <div className="flex items-center gap-2">
        <Button type="submit" disabled={isLoading || !text.trim()}>
          {isLoading ? (
            <>
              <Spinner size="sm" className="mr-2" />
              {isEditing ? "Updating..." : "Creating..."}
            </>
          ) : (
            <>
              <Save className="mr-2 h-4 w-4" />
              {isEditing ? "Update Paragraph" : "Create Paragraph"}
            </>
          )}
        </Button>
        <Button type="button" color="gray" onClick={handleCancel} disabled={isLoading}>
          <X className="mr-2 h-4 w-4" />
          Cancel
        </Button>
      </div>
    </form>
  );
};
