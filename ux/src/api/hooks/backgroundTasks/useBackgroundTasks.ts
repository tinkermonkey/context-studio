/**
 * Background Tasks API Hooks
 *
 * React Query hooks for background task management endpoints
 */

import {
  useQuery,
  useMutation,
  UseQueryOptions,
  UseMutationOptions,
  useQueryClient,
} from "@tanstack/react-query";
import { apiClient } from "@/api/client/axios";

// API Response Types
export interface TaskStatus {
  task_id: string;
  task_type: string;
  status: string;
  progress: number;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  result?: any;
  error?: string;
  created_at?: string;
  started_at?: string;
  completed_at?: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  metadata: Record<string, any>;
}

export interface TaskList {
  tasks: TaskStatus[];
  total: number;
}

export interface TaskStats {
  total_tasks: number;
  queue_size: number;
  max_queue_size: number;
  dead_letter_queue_size: number;
  status_counts: Record<string, number>;
  is_running: boolean;
}

export interface CancelTaskResponse {
  task_id: string;
  cancelled: boolean;
  message: string;
}

// Query Keys
export const backgroundTasksKeys = {
  all: ["backgroundTasks"] as const,
  list: (params?: { status_filter?: string; task_type?: string }) =>
    [...backgroundTasksKeys.all, "list", params] as const,
  detail: (taskId: string) =>
    [...backgroundTasksKeys.all, "detail", taskId] as const,
  stats: () => [...backgroundTasksKeys.all, "stats"] as const,
  deadLetterQueue: () =>
    [...backgroundTasksKeys.all, "dead-letter-queue"] as const,
};

// Query Hooks

export function useTaskList(
  params?: { status_filter?: string; task_type?: string },
  options?: UseQueryOptions<TaskList>,
) {
  return useQuery<TaskList>({
    queryKey: backgroundTasksKeys.list(params),
    queryFn: async () => {
      const response = await apiClient.get(`/api/tasks`, { params });
      return response.data;
    },
    ...options,
  });
}

export function useTaskDetail(
  taskId: string,
  options?: UseQueryOptions<TaskStatus>,
) {
  return useQuery<TaskStatus>({
    queryKey: backgroundTasksKeys.detail(taskId),
    queryFn: async () => {
      const response = await apiClient.get(`/api/tasks/${taskId}`);
      return response.data;
    },
    enabled: !!taskId,
    ...options,
  });
}

export function useTaskStats(options?: UseQueryOptions<TaskStats>) {
  return useQuery<TaskStats>({
    queryKey: backgroundTasksKeys.stats(),
    queryFn: async () => {
      const response = await apiClient.get(`/api/tasks/stats/summary`);
      return response.data;
    },
    ...options,
  });
}

export function useDeadLetterQueue(options?: UseQueryOptions<TaskList>) {
  return useQuery<TaskList>({
    queryKey: backgroundTasksKeys.deadLetterQueue(),
    queryFn: async () => {
      const response = await apiClient.get(`/api/tasks/dead-letter-queue`);
      return response.data;
    },
    ...options,
  });
}

// Mutation Hooks

export function useCancelTask(
  options?: UseMutationOptions<CancelTaskResponse, Error, string>,
) {
  const queryClient = useQueryClient();

  return useMutation<CancelTaskResponse, Error, string>({
    mutationFn: async (taskId: string) => {
      const response = await apiClient.delete(`/api/tasks/${taskId}`);
      return response.data;
    },
    onSuccess: (_, taskId) => {
      // Invalidate relevant queries
      queryClient.invalidateQueries({ queryKey: backgroundTasksKeys.list() });
      queryClient.invalidateQueries({
        queryKey: backgroundTasksKeys.detail(taskId),
      });
      queryClient.invalidateQueries({ queryKey: backgroundTasksKeys.stats() });
    },
    ...options,
  });
}
