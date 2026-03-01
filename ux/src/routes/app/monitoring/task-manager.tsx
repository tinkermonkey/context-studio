import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import { CsSidebar } from "@/components/layout/cs_sidebar";
import {
  Card,
  Button,
  Spinner,
  Select,
  Tabs,
  Badge,
  Alert,
} from "flowbite-react";
import { ListTodo, AlertCircle, Activity, Settings } from "lucide-react";
import {
  useTaskList,
  useTaskStats,
  useDeadLetterQueue,
  useCancelTask,
} from "@/api/hooks/backgroundTasks";
import {
  SystemHealthCard,
  TaskStatusViewer,
  PerformanceMetricsPanel,
} from "@/components/monitoring";
import type { MetricGroup } from "@/components/monitoring/PerformanceMetricsPanel";
import { useButterToast } from "@/hooks/useButterToast";

export const Route = createFileRoute("/app/monitoring/task-manager")({
  component: RouteComponent,
});

function RouteComponent() {
  const [statusFilter, setStatusFilter] = useState<string | undefined>(
    undefined,
  );
  const toast = useButterToast();

  const {
    data: tasks,
    isLoading: tasksLoading,
    error: tasksError,
    refetch: refetchTasks,
  } = useTaskList({ status_filter: statusFilter });
  const {
    data: stats,
    isLoading: statsLoading,
    error: statsError,
  } = useTaskStats();
  const {
    data: deadLetterQueue,
    isLoading: dlqLoading,
    error: dlqError,
  } = useDeadLetterQueue();
  const cancelTask = useCancelTask();

  const isLoading = tasksLoading || statsLoading || dlqLoading;
  const hasError = tasksError || statsError || dlqError;

  const handleCancelTask = (taskId: string) => {
    cancelTask.mutate(taskId, {
      onSuccess: () => {
        toast.success("Task cancelled successfully");
        refetchTasks();
      },
      onError: (error) => {
        toast.error(`Failed to cancel task: ${error.message}`);
      },
    });
  };

  const statsMetrics: MetricGroup[] = stats
    ? [
        {
          title: "Task Manager Statistics",
          metrics: [
            {
              label: "Total Tasks",
              value: stats.total_tasks,
              icon: <ListTodo className="h-5 w-5" />,
            },
            {
              label: "Queue Size",
              value: stats.queue_size,
              icon: <Activity className="h-5 w-5" />,
            },
            {
              label: "Failed Tasks",
              value: stats.dead_letter_queue_size,
              icon: <AlertCircle className="h-5 w-5" />,
            },
            {
              label: "Running",
              value: stats.status_counts.running || 0,
            },
            {
              label: "Pending",
              value: stats.status_counts.pending || 0,
            },
            {
              label: "Completed",
              value: stats.status_counts.completed || 0,
            },
          ],
        },
      ]
    : [];

  return (
    <>
      <CsSidebar></CsSidebar>
      <CsMain>
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CsMainTitle>Task Manager</CsMainTitle>
            <Badge color="purple" icon={Settings}>
              Admin Tool
            </Badge>
          </div>
          <Select
            value={statusFilter || "all"}
            onChange={(e) =>
              setStatusFilter(
                e.target.value === "all" ? undefined : e.target.value,
              )
            }
          >
            <option value="all">All Tasks</option>
            <option value="pending">Pending</option>
            <option value="running">Running</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="cancelled">Cancelled</option>
          </Select>
        </div>

        {hasError && (
          <Alert color="failure" icon={AlertCircle} className="mb-4">
            <span className="font-medium">Error loading task data</span>
            <p className="mt-1 text-sm">
              {tasksError?.message || statsError?.message || dlqError?.message}
            </p>
          </Alert>
        )}

        {stats && (
          <div className="mb-6">
            <SystemHealthCard
              title="Task Manager"
              status={stats.is_running ? "healthy" : "error"}
              healthScore={
                stats.total_tasks > 0
                  ? ((stats.status_counts.completed || 0) / stats.total_tasks) *
                    100
                  : 100
              }
              metrics={[
                {
                  label: "Manager Status",
                  value: stats.is_running ? "Running" : "Stopped",
                  status: stats.is_running ? "healthy" : "error",
                },
                {
                  label: "Queue Capacity",
                  value: `${stats.queue_size} / ${stats.max_queue_size}`,
                },
              ]}
              issues={
                !stats.is_running
                  ? ["Task manager is not running"]
                  : stats.dead_letter_queue_size > 0
                    ? [
                        `${stats.dead_letter_queue_size} failed tasks in dead letter queue`,
                      ]
                    : []
              }
            />
          </div>
        )}

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Spinner size="xl" />
          </div>
        ) : (
          <Tabs aria-label="Task manager tabs">
            <Tabs.Item active title="Overview" icon={Activity}>
              <div className="space-y-6">
                {statsMetrics.length > 0 && (
                  <PerformanceMetricsPanel groups={statsMetrics} />
                )}

                {tasks && tasks.tasks.length > 0 ? (
                  <TaskStatusViewer
                    tasks={tasks.tasks}
                    onCancel={handleCancelTask}
                  />
                ) : (
                  <Card>
                    <p className="text-center text-gray-500">No tasks found</p>
                  </Card>
                )}
              </div>
            </Tabs.Item>

            <Tabs.Item title="Failed Tasks" icon={AlertCircle}>
              <div className="space-y-6">
                {deadLetterQueue && deadLetterQueue.tasks.length > 0 ? (
                  <>
                    <Card>
                      <h5 className="mb-2 text-lg font-semibold text-gray-900 dark:text-white">
                        Dead Letter Queue
                      </h5>
                      <p className="text-sm text-gray-600 dark:text-gray-400">
                        Tasks that have failed and require manual intervention.
                        Total: {deadLetterQueue.total}
                      </p>
                    </Card>
                    <TaskStatusViewer
                      tasks={deadLetterQueue.tasks}
                      showActions={false}
                    />
                  </>
                ) : (
                  <Card>
                    <p className="text-center text-gray-500">
                      No failed tasks in dead letter queue
                    </p>
                  </Card>
                )}
              </div>
            </Tabs.Item>
          </Tabs>
        )}
      </CsMain>
    </>
  );
}
