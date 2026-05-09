import { useCallback, useEffect, useState } from "react";

interface UseUndoDeleteOptions {
  onDelete: (id: string) => Promise<void>;
  onDeleteError?: (id: string, error: Error) => void;
  undoWindowMs?: number;
}

// Module-level store for pending deletes that outlives component unmounting
const pendingDeletes = new Map<
  string,
  {
    timeoutId: NodeJS.Timeout;
    onDelete: (id: string) => Promise<void>;
    onDeleteError?: (id: string, error: Error) => void;
  }
>();

export function useUndoDelete({ onDelete, onDeleteError, undoWindowMs = 8000 }: UseUndoDeleteOptions) {
  const [deletedId, setDeletedId] = useState<string | null>(null);

  const performDelete = useCallback(
    async (id: string) => {
      setDeletedId(id);

      // Clear any existing pending delete for this ID
      if (pendingDeletes.has(id)) {
        clearTimeout(pendingDeletes.get(id)!.timeoutId);
      }

      const timeoutId = setTimeout(async () => {
        try {
          await onDelete(id);
          setDeletedId(null);
        } catch (error) {
          const deleteError = error instanceof Error ? error : new Error(String(error));
          if (onDeleteError) {
            onDeleteError(id, deleteError);
          }
          setDeletedId(null);
        } finally {
          pendingDeletes.delete(id);
        }
      }, undoWindowMs);

      pendingDeletes.set(id, { timeoutId, onDelete, onDeleteError });
    },
    [onDelete, onDeleteError, undoWindowMs],
  );

  const undo = useCallback(() => {
    if (deletedId && pendingDeletes.has(deletedId)) {
      const pending = pendingDeletes.get(deletedId)!;
      clearTimeout(pending.timeoutId);
      pendingDeletes.delete(deletedId);
      setDeletedId(null);
    }
  }, [deletedId]);

  useEffect(() => {
    return () => {
      // On component unmount, do NOT clear the timeout — it needs to persist
      // Just remove from local state so UI doesn't show the "undo" toast
      setDeletedId(null);
    };
  }, []);

  return { performDelete, undo, deletedId };
}
