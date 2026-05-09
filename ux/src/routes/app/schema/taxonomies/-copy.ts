export const taxonomiesCopy = {
  emptyState: {
    title: "No taxonomies yet",
    description: "A taxonomy groups related classes. Most workspaces start with one or two.",
    actionLabel: "+ New taxonomy",
  },
  filteredEmpty: {
    title: "No matching taxonomies",
    description: "Try adjusting your search or filters to find taxonomies.",
  },
  create: {
    buttonLabel: "+ New taxonomy",
    successToast: (id: string) => `Taxonomy created · \`${id}\``,
  },
  delete: {
    confirmTitle: "Delete taxonomy?",
    confirmButton: "Delete taxonomy",
    successToast: "Taxonomy deleted",
  },
  publish: {
    confirmTitle: "Publish taxonomy?",
    confirmButton: "Publish",
    successToast: (name: string, version: number) => `Taxonomy published · ${name} · v${version}`,
  },
};
