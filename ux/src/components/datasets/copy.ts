/** User-facing text for datasets: the selector and the Datasets page. */
export const datasetsCopy = {
  select: {
    ariaLabel: "Dataset",
    allLabel: "All datasets",
  },
  page: {
    eyebrow: "DATA · datasets",
    title: "Datasets",
    subtitle:
      "Named bodies of data over a taxonomy's schema. Each individual belongs to one dataset, and a relationship to its source individual's dataset.",
    addButton: "New dataset",
    taxonomyFilterLabel: "Filter by taxonomy",
    searchPlaceholder: "Search by title or identifier…",
    allTaxonomies: "All taxonomies",
    loadError: "Failed to load datasets",
    yieldsToSchema: "yields to schema",
  },
  table: {
    title: "Dataset",
    taxonomy: "Taxonomy",
    individuals: "Individuals",
    relationships: "Relationships",
    lastModified: "Last modified",
    deleteLabel: (title: string) => `Delete dataset ${title}`,
  },
  empty: {
    title: "No datasets yet",
    description:
      "A taxonomy's first individual creates its dataset. Create more to keep separate bodies of data over the same schema.",
    action: "New dataset",
  },
  create: {
    title: "New dataset",
    subtitle: "A named body of data over one taxonomy's schema.",
    taxonomyLabel: "Taxonomy",
    taxonomyPlaceholder: "Choose a taxonomy",
    titleLabel: "Title",
    identifierLabel: "Identifier",
    identifierPlaceholder: "e.g. platform-a",
    submit: "Create dataset",
    cancel: "Cancel",
    taxonomyRequired: "Choose a taxonomy.",
    titleRequired: "Enter a title.",
    identifierRequired: "Enter an identifier.",
    identifierInvalid: "Start with a lowercase letter; use lowercase letters, digits, - or _.",
    duplicateIdentifier: "This taxonomy already has a dataset with this identifier.",
    failed: "Could not create the dataset.",
    successToast: (title: string) => `Dataset “${title}” created`,
  },
  delete: {
    title: "Delete dataset",
    confirm: "Delete dataset",
    cancel: "Cancel",
    failed: "Could not delete the dataset.",
    successToast: (individuals: number, relationships: number) =>
      `Dataset deleted: ${individuals} ${individuals === 1 ? "individual" : "individuals"} and ${relationships} ${relationships === 1 ? "relationship" : "relationships"} removed`,
  },
} as const;
