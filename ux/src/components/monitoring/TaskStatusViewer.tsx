/**
 * Task Status Viewer Component
 *
 * Reusable component for displaying background task status and progress
 */

import { Card,
  Progress,
  Button,
  Table,
  TableHead,
  TableHeadCell,
  TableBody,
  TableRow,
    } from "flowbite-react";
import { Clock,
  CheckCircle,
  XCircle,
  Loader2,
  Play,
  StopCircle,
   } from "lucide-react";
import type { TaskStatus } from "@/api/hooks/backgroundTasks/useBackgroundTasks";

export interface TaskStatusViewerProps {
  tasks: TaskStatus[];
  onCancel?: (taskId: string) => void;
  onRetry?: (taskId: string) => void;
  showActions?: boolean;
  className?: string;
}

export function TaskStatusViewer({
  tasks,
  onCancel,
  onRetry,
  showActions = true,
  className = "",
}: TaskStatusViewerProps) {
  const getStatusIcon = (status: string) => {
    switch (status.toLowerCase()) {
      case "completed":
        return <CheckCircle className="h-5 w-5 text-green-600" />;
      case "failed":
      case "cancelled":
        return <XCircle className="h-5 w-5 text-red-600" />;
      case "running":
        return <Loader2 className="h-5 w-5 animate-spin text-blue-600" />;
      case "pending":
        return <Clock className="h-5 w-5 text-gray-600" />;
      default:
        return <Play className="h-5 w-5 text-gray-600" />;
    }
  };

  const getStatusColor = (
    status: string,
  ): "success" | "warning" | "failure" | "info" | "gray" => {
    switch (status.toLowerCase()) {
      case "completed":
        return "success";
      case "failed":
        return "failure";
      case "cancelled":
        return "gray";
      case "running":
        return "info";
      case "pending":
        return "warning";
      default:
        return "gray";
    }
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return "N/A";
    return new Date(dateString).toLocaleString();
  };

  const formatDuration = (startDate?: string, endDate?: string) => {
    if (!startDate) return "N/A";
    const start = new Date(startDate).getTime();
    const end = endDate ? new Date(endDate).getTime() : Date.now();
    const duration = end - start;
    const seconds = Math.floor(duration / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ${seconds % 60}s`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h ${minutes % 60}m`;
  };

  if (tasks.length === 0) {
    return (
      <Card className={className}>
        <div className="py-8 text-center text-gray-500 dark:text-gray-400">
          No tasks found
        </div>
      </Card>
    );
  }

  return (
    <Card className={className}>
      <div className="overflow-x-auto">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeadCell>Task ID</TableHeadCell>
              <TableHeadCell>Type</TableHeadCell>
              <TableHeadCell>Status</TableHeadCell>
              <TableHeadCell>Progress</TableHeadCell>
              <TableHeadCell>Duration</TableHeadCell>
              <TableHeadCell>Created</TableHeadCell>
              {showActions && <TableHeadCell>Actions</TableHeadCell>}
            </TableRow>
          </TableHead>
          <TableBody className="divide-y">
            {tasks.map((task) => (
              <TableRow
                key={task.task_id}
                className="bg-white dark:border-gray-700 dark:bg-gray-800"
              >
                <TableCell className="font-mono text-xs font-medium whitespace-nowrap text-gray-900 dark:text-white">
                  {task.task_id.substring(0, 8)}...
                </TableCell>
                <TableCell>{task.task_type}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    {getStatusIcon(task.status)}
                    <Badge color={getStatusColor(task.status)} size="sm">
                      {task.status}
                    </Badge>
                  </div>
                </TableCell>
                <TableCell>
                  <div className="w-32">
                    <Progress
                      progress={task.progress * 100}
                      size="sm"
                      color={
                        task.status === "failed"
                          ? "red"
                          : task.status === "completed"
                            ? "green"
                            : "blue"
                      }
                    />
                    <span className="mt-1 text-xs text-gray-500">
                      {(task.progress * 100).toFixed(0)}%
                    </span>
                  </div>
                </TableCell>
                <TableCell className="text-sm">
                  {formatDuration(task.started_at, task.completed_at)}
                </TableCell>
                <TableCell className="text-sm">
                  {formatDate(task.created_at)}
                </TableCell>
                {showActions && (
                  <TableCell>
                    <div className="flex gap-2">
                      {(task.status === "running" ||
                        task.status === "pending") &&
                        onCancel && (
                          <Button
                            size="xs"
                            color="failure"
                            onClick={() => onCancel(task.task_id)}
                          >
                            <StopCircle className="h-3 w-3" />
                          </Button>
                        )}
                      {task.status === "failed" && onRetry && (
                        <Button
                          size="xs"
                          color="info"
                          onClick={() => onRetry(task.task_id)}
                        >
                          <Play className="h-3 w-3" />
                        </Button>
                      )}
                    </div>
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {tasks.some((t) => t.error) && (
        <div className="mt-4 border-t pt-4 dark:border-gray-700">
          <h6 className="mb-2 text-sm font-semibold text-gray-900 dark:text-white">
            Error Details
          </h6>
          {tasks
            .filter((t) => t.error)
            .map((task) => (
              <div
                key={task.task_id}
                className="mb-2 rounded-lg bg-red-50 p-3 dark:bg-red-900/20"
              >
                <div className="mb-1 font-mono text-xs font-medium text-red-900 dark:text-red-200">
                  {task.task_id.substring(0, 8)}... - {task.task_type}
                </div>
                <div className="text-sm text-red-700 dark:text-red-300">
                  {task.error}
                </div>
              </div>
            ))}
        </div>
      )}
    </Card>
  );
}
