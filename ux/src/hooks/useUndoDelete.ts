import { useCallback, useEffect, useRef, useState } from "react";

interface UseUndoDeleteOptions<T> {
  onDelete: (id: string) => Promise<void>;
  undoWindowMs?: number;
}

export function useUndoDelete<T>({
  onDelete,
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

  const undo = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
      setDeletedId(null);
      setDeletedData(null);
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
