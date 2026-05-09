import { useCallback, useEffect, useRef, useState } from "react";

interface UseUndoDeleteOptions {
  onDelete: (id: string) => Promise<void>;
  onDeleteError?: (id: string, error: Error) => void;
  undoWindowMs?: number;
}

export function useUndoDelete({ onDelete, onDeleteError, undoWindowMs = 8000 }: UseUndoDeleteOptions) {
  const [deletedId, setDeletedId] = useState<string | null>(null);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  const performDelete = useCallback(
    async (id: string) => {
      setDeletedId(id);

      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(async () => {
        try {
          await onDelete(id);
          setDeletedId(null);
        } catch (error) {
          const deleteError = error instanceof Error ? error : new Error(String(error));
          if (onDeleteError) {
            onDeleteError(id, deleteError);
          }
          setDeletedId(null);
        }
      }, undoWindowMs);
    },
    [onDelete, onDeleteError, undoWindowMs],
  );

  const undo = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
      setDeletedId(null);
    }
  }, []);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return { performDelete, undo, deletedId };
}
