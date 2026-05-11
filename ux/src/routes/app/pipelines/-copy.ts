export const COPY = {
  // Pipelines Index Page
  PIPELINES_PAGE_TITLE: "Pipelines",
  NEW_PIPELINE_BUTTON: "New Pipeline",
  SEARCH_PIPELINES_PLACEHOLDER: "Search by name, provider, or model…",
  FILTER_PIPELINES_LABEL: "Filter pipelines by status",
  FILTER_ALL: "All",
  FILTER_ENABLED: "Enabled",
  FILTER_DISABLED: "Disabled",

  // Pipelines empty/error states
  PIPELINES_LOAD_ERROR: "Failed to load pipelines",
  NO_PIPELINES_TITLE: "No pipelines yet",
  NO_PIPELINES_DESCRIPTION: "Create your first pipeline to get started with extraction and processing.",
  CREATE_PIPELINE_CTA: "Create Pipeline",
  NO_PIPELINES_FILTERED_TITLE: "No pipelines match your filters",
  NO_PIPELINES_FILTERED_DESCRIPTION: "Try adjusting your search or filter criteria.",

  // Pipeline Detail Page
  PIPELINE_LOAD_ERROR: "Failed to load pipeline",
  PIPELINE_CONFIGURATION_LABEL: "Pipeline Configuration",
  PIPELINE_EDIT_BUTTON: "Edit",
  PIPELINE_SAVE_BUTTON: "Save",
  PIPELINE_CANCEL_BUTTON: "Cancel",
  LAST_10_RUNS_LABEL: "Last 10 Runs",
  PIPELINE_NO_RUNS: "This pipeline has never been run",
  PIPELINE_RUN_BUTTON: "Run",
  PIPELINE_VIEW_LOG: "View log",
  NO_PIPELINE_RUNS: "No runs yet",

  // Pipeline Status Labels
  STATUS_SUCCESS: "success",
  STATUS_FAILED: "failed",
  STATUS_DISABLED: "disabled",
  STATUS_IDLE: "idle",
  STATUS_RUNNING: "running",

  // Pipeline Detail Panel columns
  RUN_STATUS_HEADER: "Status",
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
  NEW_FLAVOR_BUTTON: "+ New flavor",
  NO_FLAVORS_TITLE: "No flavors yet",
  NO_FLAVORS_DESCRIPTION: "Create a pipeline flavor to get started.",
  CREATE_A_FLAVOR_CTA: "Create a flavor",
  FLAVORS_LOAD_ERROR: "Failed to load pipeline flavors",
  NO_FLAVORS_FILTERED_TITLE: "No flavors match your search",
  NO_FLAVORS_FILTERED_DESCRIPTION: "Try adjusting your search criteria.",

  // Flavor Table columns
  FLAVOR_ID_HEADER: "ID",
  FLAVOR_NAME_HEADER: "Name",
  FLAVOR_DESCRIPTION_HEADER: "Description",
  FLAVOR_STEPS_HEADER: "Steps",
  FLAVOR_UPDATED_HEADER: "Updated",

  // Flavor Modal/Drawer
  CREATE_FLAVOR_MODAL_TITLE: "Create Pipeline Flavor",
  EDIT_FLAVOR_MODAL_TITLE: "Edit Pipeline Flavor",
  DELETE_FLAVOR_TITLE: "Delete Flavor",
  FLAVOR_CREATE_ERROR: "Failed to create flavor",
  FLAVOR_UPDATE_ERROR: "Failed to update flavor",
  FLAVOR_DELETE_CONFIRM_MESSAGE: (flavorName: string) =>
    `Are you sure you want to delete "${flavorName}"? This cannot be undone.`,
  DELETE_CONFIRM_LABEL: "Delete",
  CANCEL_LABEL: "Cancel",

  // Flavor Drawer
  FLAVOR_DRAWER_ID_LABEL: "ID",
  FLAVOR_DRAWER_NAME_LABEL: "Name",
  FLAVOR_DRAWER_DESCRIPTION_LABEL: "Description",
  FLAVOR_DRAWER_STEP_COUNT_LABEL: "Step Count",
  FLAVOR_DRAWER_CREATED_LABEL: "Created",
  FLAVOR_DRAWER_UPDATED_LABEL: "Updated",
  FLAVOR_CREATE_PIPELINE_BUTTON: "Create Pipeline",
  FLAVOR_CREATE_PIPELINE_CREATING: "Creating...",
  FLAVOR_EDIT_BUTTON: "Edit",
  FLAVOR_DELETE_BUTTON: "Delete",

  // Toast messages
  PIPELINE_COMPLETED: (title: string) => `Pipeline '${title}' completed`,
  PIPELINE_FAILED: (title: string) => `Pipeline '${title}' failed`,
  PIPELINE_RUN_ERROR: "Failed to run pipeline",
  PIPELINE_CONFIG_SAVED: "Pipeline configuration saved",
  PIPELINE_CONFIG_SAVE_ERROR: "Failed to save configuration",
  AUTOSAVE_FAILED: (error: string) => `Autosave failed: ${error}`,
  ERROR_COPIED: "Error copied to clipboard",

  FLAVOR_DELETED: (name: string) => `Deleted flavor "${name}"`,
  FLAVOR_DELETE_ERROR: (error: string) => `Failed to delete flavor: ${error}`,
  FLAVOR_PIPELINE_CREATED: (name: string) => `Created pipeline from flavor "${name}"`,
  FLAVOR_PIPELINE_CREATE_ERROR: (error: string) => `Failed to create pipeline: ${error}`,
  FLAVOR_UPDATED: (name: string) => `Updated flavor "${name}"`,
} as const;
