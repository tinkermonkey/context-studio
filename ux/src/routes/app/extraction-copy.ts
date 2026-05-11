export const COPY = {
  // Page header
  PAGE_TITLE: "Entity Extraction",
  PAGE_SUBTITLE: "Extract entities, relationships, and embeddings from text",

  // Extraction Input Panel
  INPUT_PANEL_TITLE: "Input",
  INPUT_PLACEHOLDER: "Paste text here to extract entities, relationships, and embeddings...",
  EXTRACT_BUTTON: "Extract",
  EXTRACTING_BUTTON: "Extracting...",
  UPLOAD_FILE_BUTTON: "Or upload a file (.txt, .md, .pdf)",
  CHARACTERS_LABEL: "characters",

  // File upload messages
  PDF_SUPPORT_WARNING: "PDF support coming soon",
  PDF_SUPPORT_HINT: "Please paste text or upload .txt/.md files.",
  FILE_READ_ERROR: "Failed to read file",
  FILE_READ_RETRY: "Please try again.",

  // Layer names
  KG_CONTEXT_LAYER: "KG Context",
  LLM_EXTRACTION_LAYER: "LLM Extraction",
  NLP_GAP_FILL_LAYER: "NLP Gap Fill",
  REFERENCE_ENRICHMENT_LAYER: "Reference Enrichment",

  // Extraction Result Panel
  ENTITIES_LABEL: "Entities",
  LOADING_STATE: "Loading...",
  NO_ENTITIES_EXTRACTED: "No entities extracted",
  SHOW_RAW_JSON: "Show raw JSON",
  HIDE_RAW_JSON: "Hide raw JSON",

  // Entity Review Panel
  ENTITY_REVIEW_PANEL_TITLE: "Entity Review",
  ALL_SUGGESTIONS_REVIEWED: "All suggestions reviewed",
  APPROVE_BUTTON: "Approve",
  REJECT_BUTTON: "Reject",
  LINK_BUTTON: "Link",
  APPROVE_ALL_BUTTON: "Approve All",
  REJECT_ALL_BUTTON: "Reject All",
  SEARCH_CLASSES_PLACEHOLDER: "Search classes...",
  NO_CLASSES_FOUND: "No classes found",

  // Entity Review Toast Messages
  ENTITY_REJECTED: "Entity rejected",
  ENTITY_LINKED: "Entity linked to class",
  NO_CONCEPT_SCHEME: "No concept scheme available for creating classes",
  CLASS_CREATED: "Created class: ",
  CLASS_CREATION_FAILED: "Failed to create class: ",
  CLASSES_CREATED: "Created ",
  CLASSES_CREATED_SUFFIX: " class(es)",
  CLASSES_CREATION_FAILED: "Failed to create ",
  CLASSES_CREATION_FAILED_SUFFIX: " class(es)",
  BATCH_OPERATION_FAILED: "Batch operation failed: ",
  ALL_ENTITIES_REJECTED: "All entities rejected",
} as const;
