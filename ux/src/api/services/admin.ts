import { BaseService } from "./base";
import type { components } from "@/api/types";

type SystemHealthResponse = components["schemas"]["SystemHealthResponse"];
type AppConfigurationResponse = components["schemas"]["AppConfigurationResponse"];
type ConfigSectionUpdateRequest = components["schemas"]["ConfigSectionUpdateRequest"];
type BackgroundTaskResponse = components["schemas"]["BackgroundTaskResponse"];
type BackgroundTaskSummaryResponse = components["schemas"]["BackgroundTaskSummaryResponse"];

class AdminService extends BaseService {
  async getHealth(): Promise<SystemHealthResponse> {
    return this.get<SystemHealthResponse>("/api/v1/admin/health");
  }

  async getDatabaseHealth(): Promise<components["schemas"]["DatabaseHealthResponse"]> {
    return this.get("/api/v1/admin/health/database");
  }

  async getServiceMetrics(): Promise<components["schemas"]["ServiceMetricsResponse"]> {
    return this.get("/api/v1/admin/health/services");
  }

  async getTaskSummary(): Promise<BackgroundTaskSummaryResponse> {
    return this.get<BackgroundTaskSummaryResponse>("/api/v1/admin/health/tasks");
  }

  async getConfig(): Promise<AppConfigurationResponse> {
    return this.get<AppConfigurationResponse>("/api/v1/admin/configuration");
  }

  async updateConfigSection(
    section: string,
    data: ConfigSectionUpdateRequest,
  ): Promise<AppConfigurationResponse> {
    return this.patch<AppConfigurationResponse>(`/api/v1/admin/configuration/${section}`, data);
  }

  async resetConfig(): Promise<AppConfigurationResponse> {
    return this.post<AppConfigurationResponse>("/api/v1/admin/configuration/reset");
  }

  async getBackgroundTasks(): Promise<BackgroundTaskResponse[]> {
    return this.get<BackgroundTaskResponse[]>("/api/v1/admin/tasks");
  }

  async getBackgroundTask(taskId: string): Promise<BackgroundTaskResponse> {
    return this.get<BackgroundTaskResponse>(`/api/v1/admin/tasks/${taskId}`);
  }
}

export const adminService = new AdminService();
