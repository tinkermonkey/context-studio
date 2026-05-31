/**
 * Test fixtures for PipelineService using OpenAPI-generated types.
 * TODO: Pipeline types are not yet in the OpenAPI spec (Phase 2 work)
 */

export function createPipelineConfiguration(
  overrides?: Partial<any>,
): any {
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
  overrides?: Partial<any>,
): any {
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
  overrides?: Partial<any>,
): any {
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
  overrides?: Partial<any>,
): any {
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
  overrides?: Partial<any>,
): any {
  return {
    input_text: "Sample text to process",
    ...overrides,
  };
}

export function createExecutionWithPipeline(
  overrides?: Partial<any>,
): any {
  return {
    id: "exec-1",
    pipeline_config_id: "pipeline-1",
    pipeline_title: "Text Analysis Pipeline",
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

export function createListExecutionsWithPipeline(
  items?: any[],
): any {
  return {
    items: items || [createExecutionWithPipeline()],
    total: items?.length ?? 1,
    limit: 10,
    offset: 0,
  };
}
