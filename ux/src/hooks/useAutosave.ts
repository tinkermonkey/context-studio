import { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";

type AutosaveStatus = "idle" | "saving" | "saved" | "error";

interface UseAutosaveOptions<T> {
  data: T;
  mutationFn: (data: T) => Promise<void>;
  onError?: (error: Error) => void;
  debounceMs?: number;
}

export function useAutosave<T>({
  data,
  mutationFn,
  onError,
  debounceMs = 250,
}: UseAutosaveOptions<T>) {
  const [status, setStatus] = useState<AutosaveStatus>("idle");
  const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null);
  const debounceRef = useRef<NodeJS.Timeout | null>(null);
  const statusTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const statusRef = useRef<AutosaveStatus>("idle");
  const isFirstRenderRef = useRef(true);
  const mutateRef = useRef<(data: T) => void | null>(null);

  const mutation = useMutation({
    mutationFn,
    onSuccess: () => {
      setStatus("saved");
      statusRef.current = "saved";
      setLastSavedAt(new Date());
      if (statusTimeoutRef.current) clearTimeout(statusTimeoutRef.current);
      statusTimeoutRef.current = setTimeout(() => {
        setStatus("idle");
        statusRef.current = "idle";
      }, 1500);
    },
    onError: (err) => {
      setStatus("error");
      statusRef.current = "error";
      onError?.(err as Error);
    },
  });

  mutateRef.current = mutation.mutate;

  useEffect(() => {
    if (isFirstRenderRef.current) {
      isFirstRenderRef.current = false;
      return;
    }

    if (debounceRef.current) clearTimeout(debounceRef.current);

    debounceRef.current = setTimeout(() => {
      if ((statusRef.current === "idle" || statusRef.current === "saved") && mutateRef.current) {
        mutateRef.current(data);
      }
    }, debounceMs);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [data, debounceMs]);

  useEffect(() => {
    if (mutation.isPending) {
      setStatus("saving");
      statusRef.current = "saving";
    }
  }, [mutation.isPending]);

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      if (statusTimeoutRef.current) clearTimeout(statusTimeoutRef.current);
    };
  }, []);

  return {
    status,
    lastSavedAt,
    save: () => mutation.mutate(data),
    isLoading: mutation.isPending,
  };
}
