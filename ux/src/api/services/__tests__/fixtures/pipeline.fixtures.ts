/**
 * Test fixtures for PipelineService using OpenAPI-generated types.
 */

import type { components } from "@/api/types";

export function createPipelineConfiguration(
  overrides?: Partial<components["schemas"]["PipelineConfigurationResponse"]>,
): components["schemas"]["PipelineConfigurationResponse"] {
  return {
    id: "pipeline-1",
    pipeline: "text_analysis",
    title: "Text Analysis Pipeline",
    provider: "openai",
    model: "gpt-3.5-turbo",
    system_prompt: "You are a helpful assistant",
    user_prompt: "Analyze the following text",
    version: 1,
    enabled: true,
    created_at: new Date().toISOString(),
    last_updated: new Date().toISOString(),
    ...overrides,
  };
}

export function createPipelineConfigurationCreate(
  overrides?: Partial<components["schemas"]["PipelineConfigurationCreate"]>,
): components["schemas"]["PipelineConfigurationCreate"] {
  return {
    pipeline: "new_pipeline",
    title: "New Pipeline",
    provider: "openai",
    model: "gpt-3.5-turbo",
    system_prompt: "You are a helpful assistant",
    user_prompt: "Analyze the following text",
    enabled: true,
    ...overrides,
  };
}

export function createPipelineConfigurationUpdate(
  overrides?: Partial<components["schemas"]["PipelineConfigurationUpdate"]>,
): components["schemas"]["PipelineConfigurationUpdate"] {
  return {
    title: "Updated Pipeline",
    provider: "openai",
    model: "gpt-3.5-turbo",
    system_prompt: "Updated prompt",
    user_prompt: "Updated user prompt",
    enabled: true,
    ...overrides,
  };
}

export function createExecution(
  overrides?: Partial<components["schemas"]["ExecutionResponse"]>,
): components["schemas"]["ExecutionResponse"] {
  return {
    id: "exec-1",
    pipeline_config_id: "pipeline-1",
    output_text: "Execution result",
    provider: "openai",
    model: "gpt-3.5-turbo",
    tokens_in: 100,
    tokens_out: 50,
    duration_ms: 1500,
    status: "success",
    timestamp: new Date().toISOString(),
    ...overrides,
  };
}

export function createPipelineExecuteRequest(
  overrides?: Partial<components["schemas"]["PipelineExecuteRequest"]>,
): components["schemas"]["PipelineExecuteRequest"] {
  return {
    input_text: "Sample text to process",
    ...overrides,
  };
}
