import { useCallback, useRef, useState } from "react";

interface UseUndoDeleteOptions<T> {
  onDelete: (id: string) => Promise<void>;
  onRestore: (id: string, data: T) => Promise<void>;
  undoWindowMs?: number;
}

export function useUndoDelete<T>({
  onDelete,
  onRestore,
  undoWindowMs = 8000,
}: UseUndoDeleteOptions<T>) {
  const [deletedId, setDeletedId] = useState<string | null>(null);
  const [deletedData, setDeletedData] = useState<T | null>(null);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  const performDelete = useCallback(
    async (id: string, data: T) => {
      setDeletedId(id);
      setDeletedData(data);

      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(async () => {
        try {
          await onDelete(id);
          setDeletedId(null);
          setDeletedData(null);
        } catch {
          setDeletedId(null);
          setDeletedData(null);
        }
      }, undoWindowMs);
    },
    [onDelete, undoWindowMs]
  );

  const undo = useCallback(async () => {
    if (deletedId && deletedData && timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
      try {
        await onRestore(deletedId, deletedData);
      } finally {
        setDeletedId(null);
        setDeletedData(null);
      }
    }
  }, [deletedId, deletedData, onRestore]);

  return { performDelete, undo, deletedId };
}
