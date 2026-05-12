export const COPY = {
  // Sources Page
  sourcesPageTitle: "Reference Sources",
  sourcesTableHeaderName: "Name",
  sourcesTableHeaderStatus: "Status",
  sourcesTableHeaderLastChecked: "Last Checked",

  // Status labels
  statusActive: "Active",
  statusInactive: "Inactive",

  // Relative time
  justNow: "just now",
  minutesAgo: (minutes: number) => `${minutes}m ago`,
  hoursAgo: (hours: number) => `${hours}h ago`,
  daysAgo: (days: number) => `${days}d ago`,

  // Empty states
  sourcesEmptyStateTitle: "No reference sources",
  sourcesEmptyStateDescription: "Reference sources are configured in Settings",
  sourcesFilteredEmptyTitle: "No sources match your search",
  sourcesFilteredEmptyDescription: "Try a different search term",

  // Workflows Page
  workflowsPageTitle: "Grounding Workflows",
  workflowsTableHeaderName: "Name",
  workflowsTableHeaderSource: "Source",
  workflowsTableHeaderClassScope: "Class Scope",
  workflowsTableHeaderStatus: "Status",
  workflowsTableHeaderLastRun: "Last Run",

  // Workflows buttons
  newWorkflowButton: "New Workflow",

  // Workflows empty states
  workflowsEmptyStateTitle: "No grounding workflows",
  workflowsEmptyStateDescription: "Create your first grounding workflow to enrich extracted entities",
  workflowsFilteredEmptyTitle: "No workflows match your search",
  workflowsFilteredEmptyDescription: "Try a different search term",

  // Workflows modal
  createWorkflowModalTitle: "Create Grounding Workflow",

  // Toast messages
  workflowCreatedSuccess: "Grounding workflow created",
  workflowCreateError: "Failed to create workflow",
};
