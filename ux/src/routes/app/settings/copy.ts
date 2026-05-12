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

  // LLM Provider section
  llmProviderTileTitle: "LLM Provider",
  llmProviderTileDescription: "Language model configuration",
  llmProviderLabel: "Provider",
  llmProviderAnthropicOption: "Anthropic",
  llmProviderOpenAIOption: "OpenAI",
  llmProviderOllamaOption: "Ollama",
  llmModelLabel: "Model Name",
  llmModelPlaceholder: "e.g., claude-3-5-sonnet, gpt-4-turbo",
  llmApiKeyLabel: "API Key",
  llmApiKeyPlaceholder: "Enter API key (write-only)",
  llmBaseUrlLabel: "Base URL",
  llmBaseUrlPlaceholder: "http://localhost:11434",

  // Embedding Model section
  embeddingModelTileTitle: "Embedding Model",
  embeddingModelTileDescription: "Vector embedding configuration",
  embeddingModelNameLabel: "Model Name",
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

  // Config tile default values
  notConfigured: "Not configured",

  // Toast messages
  settingsUpdatedSuccess: (section: string) => `${section} settings updated`,
  failedToSaveSettings: "Failed to save settings",
};
