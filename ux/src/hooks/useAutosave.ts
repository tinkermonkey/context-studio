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

  const mutation = useMutation({
    mutationFn,
    onSuccess: () => {
      setStatus("saved");
      setLastSavedAt(new Date());
      if (statusTimeoutRef.current) clearTimeout(statusTimeoutRef.current);
      statusTimeoutRef.current = setTimeout(() => setStatus("idle"), 1500);
    },
    onError: (err) => {
      setStatus("error");
      onError?.(err as Error);
    },
  });

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    debounceRef.current = setTimeout(() => {
      if (status === "idle" || status === "saved") {
        mutation.mutate(data);
      }
    }, debounceMs);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [data, debounceMs, status, mutation]);

  useEffect(() => {
    if (mutation.isPending) {
      setStatus("saving");
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
