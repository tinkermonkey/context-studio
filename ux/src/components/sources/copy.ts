/** User-facing text for the Sources page and the extract flow. */
export const sourcesCopy = {
  page: {
    eyebrow: (taxonomy: string, dataset?: string) =>
      dataset ? `DATA · ${taxonomy} · dataset ${dataset}` : `DATA · ${taxonomy} · sources`,
    title: "Sources",
    subtitle:
      "Manuals, web pages and notes to extract from. A source keeps its text with page and character offsets, so every extracted candidate points back to the passage it came from.",
    taxonomyLabel: "Taxonomy",
    datasetLabel: "Dataset",
    allDatasets: "All datasets",
    count: (n: number) => (n === 1 ? "1 source" : `${n} sources`),
    loadError: "Failed to load sources",
    footnote:
      "Extracting a source again makes a new proposal and supersedes its open one. Removing a source keeps the entities already applied from it; their provenance still names it.",
    noTaxonomy: "Create a taxonomy first: sources belong to a taxonomy and one of its datasets.",
  },
  add: {
    heading: "ADD A SOURCE",
    modeLabel: "Source type",
    modes: { file: "File", url: "Web page", text: "Text" },
    datasetLabel: "Add to dataset",
    defaultDatasetBefore: "This taxonomy has no dataset yet. The source goes into a new dataset, ",
    defaultDatasetName: "default",
    defaultDatasetAfter: ", made when you add it.",
    dropTitle: "Drop a file here, or choose one",
    dropHint:
      "PDF, Markdown, HTML or plain text, up to 50 MB. Scanned PDFs without a text layer are refused for now.",
    uploading: (name: string) => `Uploading ${name}…`,
    urlLabel: "Web page",
    urlHint:
      "Fetched once and kept. The page's main text is extracted; menus and footers are dropped.",
    urlRequired: "Enter the page's address.",
    urlInvalid: "Enter an http or https address.",
    fetchButton: "Fetch page",
    titleLabel: "Title",
    titlePlaceholder: "Water heater service notes",
    titleRequired: "Enter a title.",
    textLabel: "Text",
    textHint: "Kept as a source like any file, so its candidates point back to it.",
    textPlaceholder: "Paste text",
    textRequired: "Paste the text.",
    addButton: "Add source",
    added: (title: string) => `Added “${title}”`,
    fetching: "Fetching the page. Its row updates when it's read.",
    failed: "Could not add the source.",
  },
  table: {
    source: "Source",
    kind: "Kind",
    status: "Status",
    lastExtraction: "Last extraction",
    added: "Added",
    actions: "Actions",
    notExtracted: "Not extracted yet",
    extract: "Extract",
    extractAgain: "Extract again",
    extractLabel: (title: string) => `Extract ${title}`,
    removeLabel: (title: string) => `Remove ${title}`,
    openProposal: "Open proposal",
    runProgress: (done: number, total: number) => `chunk ${Math.min(done + 1, total)} of ${total}`,
    runStarting: "starting",
    followRun: "Extracting…",
    noCandidates: "No candidates found",
    nothingProposed: "Nothing proposed",
    noProposal: "No proposal",
    foundCount: (n: number) => (n === 1 ? "1 found" : `${n} found`),
    interrupted: "Stopped when the app closed",
    runEnded: (status: string) => `Run ${status.toLowerCase()}`,
    openSchemaProposal: "Open schema proposal",
    operations: (n: number) => (n === 1 ? "1 op" : `${n} ops`),
  },
  empty: {
    title: "No sources yet",
    description: "Add a manual, a web page or a note above to extract individuals from it.",
  },
  remove: {
    title: "Remove source",
    message: (title: string) =>
      `Remove “${title}”? Its file and text are deleted. Entities already applied from it keep their provenance.`,
    confirm: "Remove",
    removed: (title: string) => `Removed “${title}”`,
    failed: "Could not remove the source.",
  },
  extract: {
    eyebrow: (kind: string, taxonomy: string) => `SOURCE · ${kind} · ${taxonomy}`,
    subtitle: (detail: string, age: string, dataset: string) =>
      `${detail} · added ${age} to dataset ${dataset}`,
    loadError: "Failed to load the source",
    notReady:
      "This source isn't ready to extract: it is still being fetched, or it couldn't be read.",
    configureTitle: "Extract",
    configureSubtitle:
      "Candidates land as one proposal in the review queue. Nothing changes the dataset until it is applied there.",
    datasetLabel: "Dataset",
    datasetHint:
      "The proposal, and every individual it creates, belongs to this dataset. Near matches are looked for here.",
    configLabel: "Individual extraction",
    configHint: "Individuals and relationships, typed by the taxonomy's class definitions.",
    configPlaceholder: "Server default",
    schemaLabel: "Also suggest schema changes",
    schemaHint:
      "Runs schema extraction too. New classes and predicates go in a separate proposal, since schema changes follow the taxonomy's approval policy.",
    schemaMirroredHint:
      "Not available here: this taxonomy mirrors a client's spec, so only that client proposes schema changes, over MCP.",
    skipBoilerplateLabel: "Skip boilerplate and other languages",
    skipBoilerplateHint:
      "Leaves out warranty, safety, legal and contact sections, and copies of the text in other languages. Each run lists what it skipped.",
    pagesLabel: "Pages",
    pagesHint: "Optional. Leave out index or appendix pages to save time and cost.",
    pagesPlaceholder: "e.g. 1-12, 15",
    /** `chunks` is a count or a range ("3–6"); `cost` likewise, when a price is known. */
    estimate: (chunks: string, schema: boolean, dataset: string, cost?: string) => {
      const chunkText = chunks === "1" ? "about 1 chunk" : `about ${chunks} chunks`;
      const runs = schema
        ? `Two runs, two proposals: individuals for dataset ${dataset}, and schema suggestions.`
        : `One run, one proposal for dataset ${dataset}.`;
      return `Rough estimate: ${chunkText}${cost ? `, ${cost}` : ""}. ${runs}`;
    },
    cancel: "Cancel",
    start: "Start extraction",
    startFailed: "Could not start the extraction.",
    runningTitle: "Extracting",
    runningSubtitle:
      "You can leave this page. The run carries on, and the source's row shows its progress.",
    starting: "Starting…",
    chunkHeadline: (done: number, total: number) =>
      `Chunk ${Math.min(done + 1, total)} of ${total}`,
    percentLabel: (percent: number) => `${percent}% of chunks read`,
    cancelRun: "Cancel run",
    cancelFailed: "Could not cancel the run.",
    schemaRun: "Schema suggestions",
    doneTitle: "Proposal ready",
    doneSubtitle: (title: string, dataset?: string) =>
      dataset ? `Extraction: ${title} · dataset ${dataset}` : `Extraction: ${title}`,
    operations: "Operations",
    newIndividuals: "New individuals",
    relationships: "Relationships",
    nearMatches: "Near matches",
    schemaDoneTitle: "Schema proposal ready",
    noCandidatesTitle: "No candidates found",
    noCandidatesMessage: "The run read every chunk and found nothing to propose.",
    nothingProposedTitle: "Nothing proposed",
    /** `found` is 0 when the run didn't count its candidates (an unchunked run). */
    nothingProposedMessage: (found: number) =>
      found > 0
        ? `The chunks found ${found === 1 ? "1 candidate" : `${found} candidates`}, but none could be proposed.`
        : "Candidates were found, but none could be proposed.",
    skippedLabel: "Not proposed",
    backToSources: "Back to sources",
    reviewProposal: "Review proposal",
    reviewSchemaProposal: "Review schema proposal",
    failedTitle: "Extraction failed",
    cancelledTitle: "Run cancelled",
    cancelledMessage: "The run stopped. Nothing was proposed.",
    interruptedTitle: "Stopped when the app closed",
    interruptedMessage:
      "The run was extracting when Context Studio closed, and it doesn't resume. Nothing was proposed; extract again to start over.",
    runLoadTitle: "Couldn't load this run",
    runMissing: "This run no longer exists. Extract again to start a new one.",
    tryAgain: "Extract again",
  },
  chunks: {
    heading: "CHUNKS · BY SECTION",
    count: (n: number, pages: number) =>
      `${n === 1 ? "1 chunk" : `${n} chunks`}${pages > 1 ? ` · ${pages} pages` : ""}`,
    estimated: (range: string) => (range === "1" ? "about 1 chunk" : `about ${range} chunks`),
    chunk: (n: number) => `Chunk ${n}`,
    waiting: "waiting",
    reading: "reading",
    read: "read",
    found: (n: number) => `${n} found`,
    note: "Split at headings, about 8k characters each, never mid-sentence. Candidates found in several chunks merge into one operation with every passage as evidence.",
  },
} as const;
