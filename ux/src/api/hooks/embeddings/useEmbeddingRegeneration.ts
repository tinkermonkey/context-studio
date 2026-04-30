import { useState, useRef, useEffect } from "react";
import { API_CONFIG } from "@/api/config";
import { apiLogger } from "@/api/utils/logger";

export interface EmbeddingProgress {
  total_nodes: number;
  completed_nodes: number;
  completion_percentage: number;
  current_node_title: string;
  current_node_type: string;
  start_time: string;
  current_time: string;
  estimated_remaining_seconds: number;
  processing_rate_per_second: number;
  error_count: number;
  errors: string[];
}

export type EmbeddingRegenerationStatus =
  | "disconnected"
  | "connected"
  | "running"
  | "completed"
  | "error";

export function useEmbeddingRegeneration() {
  const [status, setStatus] =
    useState<EmbeddingRegenerationStatus>("disconnected");
  const [progress, setProgress] = useState<EmbeddingProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const connect = (force = false) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return; // Already connected
    }

    const wsBase = API_CONFIG.baseURL.replace("http", "ws");
    const wsUrl = `${wsBase}/api/embeddings/regenerate?force=${force}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => setStatus("connected");

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        switch (data.type) {
          case "connected":
            setStatus("connected");
            break;

          case "started":
            setStatus("running");
            setProgress(null);
            setError(null);
            break;

          case "progress":
            setProgress(data.progress);
            break;

          case "completed":
            setStatus("completed");
            break;

          case "error":
            setStatus("error");
            setError(data.message);
            break;
        }
      } catch (parseError) {
        apiLogger.error("Failed to parse WebSocket message", {
          error: parseError instanceof Error ? parseError.message : String(parseError),
        });
        setStatus("error");
        setError("Failed to parse server response");
      }
    };

    ws.onerror = (event) => {
      apiLogger.error("WebSocket connection error", {
        url: wsUrl,
        readyState: ws.readyState,
        eventType: event instanceof Event ? event.type : "unknown",
      });
      setStatus("error");
      setError("WebSocket connection error. Check logs for details.");
    };

    ws.onclose = () => setStatus("disconnected");
  };

  const disconnect = () => {
    wsRef.current?.close();
    setStatus("disconnected");
    setProgress(null);
    setError(null);
  };

  const stopRegeneration = async () => {
    try {
      const url = `${API_CONFIG.baseURL}/api/embeddings/stop`;
      const response = await fetch(url, {
        method: "POST",
      });

      if (!response.ok) {
        apiLogger.error("Stop regeneration request failed", {
          url,
          status: response.status,
          statusText: response.statusText,
        });
        setError(`Failed to stop regeneration (HTTP ${response.status})`);
        return false;
      }

      const result = await response.json();
      return result.stopped;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      apiLogger.error("Stop regeneration error", { error: errorMessage });
      setError("Failed to stop regeneration");
      return false;
    }
  };

  useEffect(() => {
    return () => disconnect();
  }, []);

  return {
    status,
    progress,
    error,
    connect,
    disconnect,
    stopRegeneration,
  };
}
