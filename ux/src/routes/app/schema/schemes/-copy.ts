export const schemesCopy = {
  emptyState: {
    title: "No concept schemes yet",
    description: "A concept scheme organizes classes within a taxonomy.",
    actionLabel: "+ New scheme",
  },
  filteredEmpty: {
    title: "No matching concept schemes",
    description: "Try adjusting your search or filters to find concept schemes.",
  },
  create: {
    buttonLabel: "+ New scheme",
    successToast: (id: string) => `Concept scheme created · \`${id}\``,
  },
  delete: {
    confirmTitle: "Delete concept scheme?",
    confirmButton: "Delete scheme",
    successToast: "Concept scheme deleted",
  },
};
