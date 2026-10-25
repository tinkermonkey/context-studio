export const COPY = {
  // Page header
  settingsPageTitle: "Settings",
  settingsPageSubtitle: "Configure application settings and external integrations",

  // Workspace section
  workspaceTileTitle: "Workspace",
  workspaceTileDescription: "Workspace configuration",
  workspaceDisplayNameLabel: "Workspace Name",
  workspaceDisplayNamePlaceholder: "Enter workspace display name",
  workspacePathLabel: "Workspace Path",
  workspaceUnnamed: "Unnamed",

  // Chat assistant
  chatModelLabel: "Chat model",
  chatModelPlaceholder: "claude-sonnet-5-5",
  chatModelHint:
    "Model the chat assistant uses. Pick a listed model or enter an OpenRouter id (vendor/model).",
  chatModelRequired: "Enter a model id",

  // Embedding Model section
  embeddingModelTileTitle: "Embedding Model",
  embeddingModelTileDescription: "Vector embedding configuration",
  embeddingModelNameLabel: "Embedding model",
  embeddingModelNamePlaceholder: "e.g., sentence-transformers/all-MiniLM-L6-v2",
  embeddingVectorDimensionsLabel: "Vector Dimensions",
  embeddingDimensionsMeta: (dimensions: number) => `${dimensions} dimensions`,

  // NLP Model section
  nlpModelTileTitle: "NLP Model",
  nlpModelTileDescription: "Natural language processing",
  nlpModelNameLabel: "spaCy Model Name",
  nlpModelNamePlaceholder: "e.g., en_core_web_sm",

  // Reference Sources section
  referenceSourcesTileTitle: "Reference Sources",
  referenceSourcesTileDescription: "Manage knowledge sources",
  referenceSourcesMeta: (count: number) => `${count} source(s) configured`,

  // Sync Target section
  syncTargetTileTitle: "Sync Target",
  syncTargetTileDescription: "Remote synchronization",
  syncTargetTypeLabel: "Sync Target Type",
  syncTargetTypeLocalOption: "Local Path",
  syncTargetTypeS3Option: "S3",
  syncTargetPathLabel: "Local Path",
  syncTargetS3BucketLabel: "S3 Bucket",
  syncTargetPathPlaceholder: "/path/to/sync",
  syncTargetS3BucketPlaceholder: "my-bucket",
  syncTargetAwsAccessKeyLabel: "AWS Access Key ID",
  syncTargetAwsSecretKeyLabel: "AWS Secret Access Key",

  // Modal titles
  editWorkspaceSettingsTitle: "Edit Workspace Settings",
  editLlmProviderSettingsTitle: "Edit LLM Provider Settings",
  editEmbeddingModelSettingsTitle: "Edit Embedding Model Settings",
  editNlpModelSettingsTitle: "Edit NLP Model Settings",
  editSyncTargetSettingsTitle: "Edit Sync Target Settings",

  // Modal buttons
  cancelButton: "Cancel",
  saveButton: "Save",
  savingButton: "Saving...",

  // Modal placeholders
  selectOptionPlaceholder: "Select an option",
  sensitiveFieldPlaceholder: "Enter new value to replace existing",

  // Config tile default values
  notConfigured: "Not configured",

  // Toast messages
  settingsUpdatedSuccess: (section: string) => `${section} settings updated`,
  failedToSaveSettings: "Failed to save settings",
};
