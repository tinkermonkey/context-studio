export const COPY = {
  // Page header
  versioningPageTitle: "Versioning",
  versioningPageSubtitle: "Change history and synchronization",

  // Tab labels
  changesTab: "Changes",
  syncStatusTab: "Sync Status",

  // Change history
  changesHeading: "Change history",
  noChanges: "No changes recorded yet",
  couldNotLoadChanges: "Could not load change history",

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

  // Error messages
  couldNotLoadSyncStatus: "Could not load sync status",
  retryErrorSuffix: ". Try again.",

  // Toast messages
  pushSuccessMessage: (count: number) => `Pushed ${count} changes`,
  pullSuccessMessage: (count: number) => `Pulled ${count} changes`,
  failedToPush: "Failed to push",
  failedToPull: "Failed to pull",
};
