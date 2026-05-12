export const COPY = {
  // Page header
  versioningPageTitle: "Versioning",
  versioningPageSubtitle: "Manage changesets and synchronization",

  // Tab labels
  changesetsTab: "Changesets",
  conflictsTab: "Conflicts",
  syncStatusTab: "Sync Status",

  // Changeset Panel
  pendingChangesHeading: "Pending Changes",
  changesetListHeading: "Changesets",
  stageSelectedButton: "Stage Selected",

  // Create Changeset Modal
  createChangesetModalTitle: "Create Changeset",
  changesetNameLabel: "Changeset Name",
  changesetNamePlaceholder: "e.g., Add new properties to Person class",
  changesetDescriptionLabel: "Description (optional)",
  changesetDescriptionPlaceholder: "Describe the changes in this changeset...",
  changesetNameRequired: "Changeset name is required",
  cancelButton: "Cancel",
  createChangesetButton: "Create Changeset",
  creatingChangesetButton: "Creating...",
  createChangesetInfoMessage: (count: number) =>
    `Creating changeset with ${count} change${count !== 1 ? "s" : ""}`,

  // Changeset empty state
  noChangesetsYet: "No changesets yet",
  createFirstChangesetMessage: "Create your first changeset by staging pending changes",

  // Changeset state chips
  changeset_State: {
    working: "working",
    staged: "staged",
    proposed: "proposed",
    approved: "approved",
    merged: "merged",
  },

  // Changeset list actions
  applyButton: "Apply",
  applyingButton: "Applying...",
  changesHeading: (count: number) => `Changes (${count})`,
  noChanges: "No changes",

  // Sync Status Panel
  syncTargetLabel: "Sync target:",
  notConfiguredLabel: "Not configured",
  pushCardTitle: "Push",
  pullCardTitle: "Pull",
  lastSyncLabel: "Last sync:",
  changesAheadLabel: "Changes ahead:",
  changesPulledLabel: "Changes pulled:",

  // Sync status empty state
  noSyncTargetConfigured: "No sync target configured",
  syncTargetDescription: "Configure a sync target in settings to enable push and pull operations",
  goToSettingsButton: "Go to Settings",

  // Conflict Resolver
  noProposalSelected: "No proposal selected",
  selectProposalMessage: "Select a proposal with conflicts to resolve",
  noConflicts: "No conflicts",
  allClear: "All clear",

  // Conflict Row actions
  ourValue: "Ours",
  theirValue: "Theirs",
  editButton: "Edit",
  resolvedChip: "✓ resolved",

  // Conflict Resolver table headers
  entityHeader: "Entity",
  fieldHeader: "Field",
  oursHeader: "Ours",
  theirsHeader: "Theirs",
  actionHeader: "Action",

  // Conflict Resolver actions
  applyResolutionsButton: "Apply Resolutions",
  applyingResolutionsButton: "Applying...",

  // Toast messages
  conflictDetectedNotification: "Conflict detected. Resolve conflicts to proceed.",
  changesetCreatedSuccess: "Changeset created successfully",
  changesetAppliedSuccess: "Changeset applied successfully",
  conflictsResolvedSuccess: "Conflicts resolved successfully!",
  selectAtLeastOneChange: "Please select at least one change",
  invalidJSONValue: "Invalid JSON value",
  pushSuccessMessage: (count: number) => `Pushed ${count} changes`,
  pullSuccessMessage: (count: number) => `Pulled ${count} changes`,
  failedToPush: "Failed to push",
  failedToPull: "Failed to pull",
  failedToApplyChangeset: "Failed to apply changeset",
  failedToResolveConflicts: "Failed to resolve conflicts",
};
