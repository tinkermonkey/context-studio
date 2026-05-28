export const COPY = {
  // Pipelines Index Page
  PIPELINES_PAGE_TITLE: "Pipelines",
  PIPELINES_PAGE_SUBTITLE:
    "Graph-RAG ingest pipelines. Each pipeline pulls from a source, extracts structure, and writes to the knowledge graph.",
  NEW_PIPELINE_BUTTON: "New Pipeline",
  SEARCH_PIPELINES_PLACEHOLDER: "Search by name, provider, or model…",
  FILTER_PIPELINES_LABEL: "Filter pipelines by status",
  FILTER_ALL: "All",
  FILTER_RUNNING: "Running",
  FILTER_SUCCESS: "Success",
  FILTER_IDLE: "Idle",
  FILTER_FAILED: "Failed",

  // Pipelines empty/error states
  PIPELINES_LOAD_ERROR: "Failed to load pipelines",
  EXECUTIONS_LOAD_ERROR:
    "Failed to load execution history. Pipeline status indicators may be inaccurate.",
  NO_PIPELINES_TITLE: "No pipelines yet",
  NO_PIPELINES_DESCRIPTION:
    "Create your first pipeline to get started with extraction and processing.",
  CREATE_PIPELINE_CTA: "Create Pipeline",
  NO_PIPELINES_FILTERED_TITLE: "No pipelines match your filters",
  NO_PIPELINES_FILTERED_DESCRIPTION: "Try adjusting your search or filter criteria.",

  // Pipeline Detail Page
  PIPELINE_LOAD_ERROR: "Failed to load pipeline",
  PIPELINE_SAVE_BUTTON: "Save",
  PIPELINE_CANCEL_BUTTON: "Cancel",
  LAST_10_RUNS_LABEL: "Last 10 Runs",
  PIPELINE_NO_RUNS: "This pipeline has never been run",
  PIPELINE_RUN_BUTTON: "Run",
  PIPELINE_VIEW_LOG: "View log",
  NO_PIPELINE_RUNS: "No runs yet",

  // Detail panel tabs
  TAB_PROMPTS: "Prompts",
  TAB_CONFIG: "Config",
  TAB_TEST: "Test",
  TAB_HISTORY: "History",

  // Prompts tab
  SYSTEM_PROMPT_LABEL: "System Prompt",
  USER_PROMPT_LABEL: "User Prompt",
  SYSTEM_PROMPT_PLACEHOLDER: "You are an expert at…",
  USER_PROMPT_PLACEHOLDER: "Process the following:\n\n{text}",

  // Config tab
  PROVIDER_LABEL: "Provider",
  MODEL_LABEL: "Model",
  ENABLED_LABEL: "Enabled",
  PIPELINE_CONFIGURATION_LABEL: "Extra Configuration",
  SAVING_LABEL: "Saving…",

  // Test tab
  TEST_INPUT_LABEL: "Test Input",
  TEST_INPUT_PLACEHOLDER: "Enter text to test the pipeline against…",
  RUN_TEST_BUTTON: "Run",
  RUNNING_LABEL: "Running…",
  TEST_NO_OUTPUT: "Run the pipeline to see output here",
  OUTPUT_COPIED: "Output copied to clipboard",

  // Pipeline Status Labels
  STATUS_SUCCESS: "success",
  STATUS_FAILED: "failed",
  STATUS_DISABLED: "disabled",
  STATUS_IDLE: "idle",
  STATUS_RUNNING: "running",

  // Pipeline Detail Panel columns
  RUN_STATUS_HEADER: "Status",
  RUN_PIPELINE_HEADER: "Pipeline",
  RUN_STARTED_HEADER: "Started",
  RUN_DURATION_HEADER: "Duration",
  RUN_TOKENS_HEADER: "Tokens",

  // Pipeline Error Log
  ERROR_DETAILS_TITLE: "Error Details",
  COPY_ERROR_BUTTON: "Copy error to clipboard",

  // Pipeline Run History Page
  RUN_HISTORY_PAGE_TITLE: "Run History",
  SEARCH_RUNS_PLACEHOLDER: "Search by pipeline name…",
  FILTER_RUNS_LABEL: "Filter runs by status",
  RUNS_LOAD_ERROR: "Failed to load run history",
  STATUS_FILTER_SUCCESS: "Success",
  STATUS_FILTER_ERROR: "Error",
  STATUS_FILTER_TIMEOUT: "Timeout",
  NO_RUNS_TITLE: "No pipeline runs yet",
  NO_RUNS_DESCRIPTION: "Execute a pipeline to see run history here.",
  NO_RUNS_FILTERED_TITLE: "No runs match your filter",
  NO_RUNS_FILTERED_DESCRIPTION: "Try adjusting your search or filter criteria.",
  PAGINATION_PREVIOUS: "Previous",
  PAGINATION_NEXT: "Next",

  // Pipeline Flavors Page
  FLAVORS_PAGE_TITLE: "Pipeline Flavors",
  NEW_FLAVOR_BUTTON: "New Flavor",
  SEARCH_FLAVORS_PLACEHOLDER: "Search by name or description…",
  FLAVORS_LOAD_ERROR: "Failed to load pipeline flavors",
  NO_FLAVORS_TITLE: "No pipeline flavors yet",
  NO_FLAVORS_DESCRIPTION: "Create your first flavor to save template configurations.",
  CREATE_FLAVOR_CTA: "Create Flavor",
  NO_FLAVORS_FILTERED_TITLE: "No flavors match your search",
  NO_FLAVORS_FILTERED_DESCRIPTION: "Try adjusting your search criteria.",

  // Create pipeline form
  CREATE_PIPELINE_TITLE: "New Pipeline",
  CREATE_FORM_TITLE_LABEL: "Title",
  CREATE_FORM_TITLE_PLACEHOLDER: "e.g. Schema Extraction v2",
  CREATE_FORM_PIPELINE_TYPE_LABEL: "Pipeline Type",
  CREATE_FORM_PROVIDER_LABEL: "Provider",
  CREATE_FORM_MODEL_LABEL: "Model",
  CREATE_FORM_MODEL_PLACEHOLDER: "e.g. claude-sonnet-4-6",
  CREATE_FORM_SYSTEM_PROMPT_LABEL: "System Prompt",
  CREATE_FORM_SYSTEM_PROMPT_PLACEHOLDER: "You are an expert at…",
  CREATE_FORM_USER_PROMPT_LABEL: "User Prompt",
  CREATE_FORM_USER_PROMPT_PLACEHOLDER: "Process the following:\n\n{text}",
  CREATE_FORM_ENABLED_LABEL: "Enabled",
  CREATE_FORM_SUBMIT: "Create Pipeline",
  CREATE_FORM_CREATING: "Creating…",
  CREATE_PIPELINE_SUCCESS: (title: string) => `Pipeline '${title}' created`,
  CREATE_PIPELINE_ERROR: "Failed to create pipeline",
  VALIDATION_TITLE_REQUIRED: "Title is required",
  VALIDATION_MODEL_REQUIRED: "Model is required",
  VALIDATION_SYSTEM_PROMPT_REQUIRED: "System prompt is required",
  VALIDATION_USER_PROMPT_REQUIRED: "User prompt is required",

  // Toast messages
  PIPELINE_COMPLETED: (title: string) => `Pipeline '${title}' completed`,
  PIPELINE_FAILED: (title: string) => `Pipeline '${title}' failed`,
  PIPELINE_RUN_ERROR: "Failed to run pipeline",
  PIPELINE_CONFIG_SAVED: "Configuration saved",
  PIPELINE_CONFIG_SAVE_ERROR: "Failed to save configuration",
  AUTOSAVE_FAILED: (error: string) => `Autosave failed: ${error}`,
  ERROR_COPIED: "Error copied to clipboard",
  CLIPBOARD_COPY_ERROR: "Failed to copy error message",
} as const;
