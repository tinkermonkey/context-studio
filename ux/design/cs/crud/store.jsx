// =========================================================================
// Context Studio — CRUD store engine
// A tiny external store layered over window.CS_DATA that adds:
//   • optimistic create / update / delete with version bumps
//   • cascade-impact computation (what a delete will orphan)
//   • identifier validation (snake_case + uniqueness)
//   • a simulated AI "suggest" service for description/definition fields
//   • an activity feed + a global toast queue
// Components read it with useCS() (useSyncExternalStore) and mutate with
// the CSStore.* methods. Mutations replace collection references so the
// snapshot identity changes and subscribers re-render.
// =========================================================================

(() => {
  const D = window.CS_DATA;

  // ---- seed: Pipeline Types (system-defined, read-only) -----------------
  // A Pipeline Type maps to a python module implementing the pipeline.
  // Configurations (formerly "Flavors") are the user-editable layer beneath.
  const pipeline_types = [
    {
      id: "pt_schema_extraction",
      name: "Schema extraction",
      system: true,
      module: "pipelines/schema_extraction.py",
      icon: "schema",
      description: "Derive taxonomies, concept schemes and classes from a source corpus.",
      inputs: "Source documents",
      outputs: "Taxonomy · Scheme · Class",
      stages: ["chunk", "extract", "cluster", "write"],
    },
    {
      id: "pt_schema_refinement",
      name: "Schema refinement",
      system: true,
      module: "pipelines/schema_refinement.py",
      icon: "component",
      description: "Deduplicate, merge and re-parent existing schema nodes for consistency.",
      inputs: "Existing schema",
      outputs: "Schema diffs",
      stages: ["scan", "embed", "merge", "write"],
    },
    {
      id: "pt_individual_extraction",
      name: "Individual extraction",
      system: true,
      module: "pipelines/individual_extraction.py",
      icon: "data",
      description: "Extract concrete individuals (instances) and assign them to classes.",
      inputs: "Source documents",
      outputs: "Individuals",
      stages: ["chunk", "ner", "resolve", "write"],
    },
    {
      id: "pt_relationship_extraction",
      name: "Relationship extraction",
      system: true,
      module: "pipelines/relationship_extraction.py",
      icon: "link",
      description: "Infer typed relationships (triples) between graph nodes.",
      inputs: "Nodes + context",
      outputs: "Relationships",
      stages: ["pair", "classify", "score", "write"],
    },
    {
      id: "pt_grounding",
      name: "Grounding",
      system: true,
      module: "pipelines/grounding.py",
      icon: "globe",
      description: "Link nodes to external references and authority records.",
      inputs: "Nodes",
      outputs: "External references",
      stages: ["query", "match", "rank", "write"],
    },
  ];

  // ---- seed: Configurations (formerly Flavors) --------------------------
  const cfg = (o) =>
    Object.assign(
      {
        enabled: true,
        version: 1,
        parameters: { temperature: 0.4, max_tokens: 800, top_p: 0.9 },
        execution_count: 0,
        average_duration_ms: 0,
        average_cost: 0,
        updated: "2026-05-18",
        system_prompt: "",
        user_prompt_template: "",
      },
      o,
    );

  const configurations = [
    cfg({
      id: "cfg_schema_gpt4o",
      pipeline_type_id: "pt_schema_extraction",
      name: "GPT-4o structural",
      description: "High-accuracy schema extraction tuned for biomedical corpora.",
      provider: "openai",
      model: "gpt-4o",
      system_prompt:
        "You are an expert knowledge engineer. Extract a clean, hierarchical taxonomy of concepts. Prefer precise, mutually-exclusive classes.",
      user_prompt_template:
        "From the {{source}} below, extract candidate classes for the {{domain}} domain.\n\nDocument:\n{{chunk}}",
      parameters: { temperature: 0.3, max_tokens: 1200, top_p: 0.9 },
      execution_count: 1284,
      average_duration_ms: 2140,
      average_cost: 0.0182,
      version: 6,
      updated: "2026-05-19",
    }),
    cfg({
      id: "cfg_schema_claude",
      pipeline_type_id: "pt_schema_extraction",
      name: "Claude precise",
      description: "Structured-thinking variant; strong at hierarchy and disambiguation.",
      provider: "anthropic",
      model: "claude-3-5-sonnet",
      system_prompt:
        "You organise domain knowledge into clean concept schemes. Think step by step about the hierarchy before emitting classes.",
      user_prompt_template:
        "Build a concept scheme for {{domain}} from this {{source}}:\n\n{{chunk}}",
      parameters: { temperature: 0.2, max_tokens: 1500, top_p: 0.95 },
      execution_count: 642,
      average_duration_ms: 3010,
      average_cost: 0.024,
      version: 3,
      updated: "2026-05-17",
    }),
    cfg({
      id: "cfg_ind_fast",
      pipeline_type_id: "pt_individual_extraction",
      name: "Fast NER",
      description: "Cheap, high-throughput entity extraction for large document sets.",
      provider: "openai",
      model: "gpt-4o-mini",
      system_prompt:
        "You are a precise named-entity extractor. Return only entities that clearly instantiate one of the provided classes.",
      user_prompt_template: "Classes: {{classes}}\n\nExtract individuals from:\n{{chunk}}",
      parameters: { temperature: 0.1, max_tokens: 600, top_p: 1.0 },
      execution_count: 8932,
      average_duration_ms: 740,
      average_cost: 0.0009,
      version: 9,
      updated: "2026-05-20",
    }),
    cfg({
      id: "cfg_ind_grounded",
      pipeline_type_id: "pt_individual_extraction",
      name: "Grounded extraction",
      description: "Extraction with inline resolution against authority IDs.",
      provider: "anthropic",
      model: "claude-3-haiku",
      system_prompt:
        "Extract individuals and, where possible, attach an authoritative identifier (NCBI, UniProt, Wikidata).",
      user_prompt_template: "Classes: {{classes}}\nAuthorities: {{authorities}}\n\n{{chunk}}",
      parameters: { temperature: 0.2, max_tokens: 900, top_p: 0.9 },
      execution_count: 3110,
      average_duration_ms: 1180,
      average_cost: 0.0016,
      version: 4,
      updated: "2026-05-15",
    }),
    cfg({
      id: "cfg_rel_classify",
      pipeline_type_id: "pt_relationship_extraction",
      name: "Triple classifier",
      description: "Classifies candidate node pairs into typed predicates with a confidence score.",
      provider: "openai",
      model: "gpt-4o",
      system_prompt:
        "Given a pair of nodes and surrounding context, choose the single best predicate from the provided list or reply NONE.",
      user_prompt_template:
        "Predicates: {{predicates}}\nSource: {{source}}\nTarget: {{target}}\nContext: {{context}}",
      parameters: { temperature: 0.0, max_tokens: 200, top_p: 1.0 },
      execution_count: 5401,
      average_duration_ms: 920,
      average_cost: 0.0071,
      version: 5,
      updated: "2026-05-18",
    }),
    cfg({
      id: "cfg_refine_merge",
      pipeline_type_id: "pt_schema_refinement",
      name: "Dedupe & merge",
      description: "Embedding-guided merge proposals for near-duplicate classes.",
      provider: "openai",
      model: "gpt-4o-mini",
      system_prompt:
        "You propose safe merges between near-duplicate classes. Be conservative; never merge across concept schemes.",
      user_prompt_template: "Candidate cluster:\n{{cluster}}\n\nPropose merges or reply KEEP_ALL.",
      parameters: { temperature: 0.2, max_tokens: 500, top_p: 0.9 },
      execution_count: 412,
      average_duration_ms: 1340,
      average_cost: 0.0011,
      version: 2,
      updated: "2026-05-11",
      enabled: false,
    }),
    cfg({
      id: "cfg_ground_wikidata",
      pipeline_type_id: "pt_grounding",
      name: "Wikidata linker",
      description: "Links nodes to Wikidata QIDs with disambiguation.",
      provider: "anthropic",
      model: "claude-3-haiku",
      system_prompt:
        "You match a concept to the single best Wikidata entity. Prefer exact sense matches; reply NONE if uncertain.",
      user_prompt_template: "Concept: {{title}}\nContext: {{context}}\nCandidates: {{candidates}}",
      parameters: { temperature: 0.0, max_tokens: 150, top_p: 1.0 },
      execution_count: 2204,
      average_duration_ms: 680,
      average_cost: 0.0006,
      version: 3,
      updated: "2026-05-14",
    }),
  ];

  // ---- initial state (clone so we never mutate CS_DATA in place) --------
  const clone = (a) => a.map((x) => ({ ...x }));
  let state = {
    taxonomies: clone(D.taxonomies),
    concept_schemes: clone(D.concept_schemes),
    classes: clone(D.classes),
    individuals: clone(D.individuals),
    property_definitions: clone(D.property_definitions),
    relationships: clone(D.relationships),
    pipeline_types: clone(pipeline_types),
    configurations: clone(configurations),
    datasets: clone(D.datasets || []),
    activity: clone(D.activity),
    rev: 0,
  };

  const listeners = new Set();
  const notify = () => {
    state = { ...state, rev: state.rev + 1 };
    listeners.forEach((l) => l());
  };
  const subscribe = (l) => {
    listeners.add(l);
    return () => listeners.delete(l);
  };
  const getSnapshot = () => state;

  // ---- activity ---------------------------------------------------------
  const ME = "you@studio";
  const logActivity = (kind, what, subject, meta) => {
    state.activity = [{ kind, who: ME, what, subject, meta, when: "now" }, ...state.activity];
  };

  // ---- toast queue (separate lightweight store) -------------------------
  let toasts = [];
  const toastListeners = new Set();
  const toastSub = (l) => {
    toastListeners.add(l);
    return () => toastListeners.delete(l);
  };
  const toastSnap = () => toasts;
  const pushToast = (t) => {
    const id = "t" + Date.now() + Math.random().toString(36).slice(2, 6);
    toasts = [...toasts, { id, ...t }];
    toastListeners.forEach((l) => l());
    return id;
  };
  const dismissToast = (id) => {
    toasts = toasts.filter((t) => t.id !== id);
    toastListeners.forEach((l) => l());
  };

  // ---- helpers ----------------------------------------------------------
  const collectionOf = {
    taxonomy: "taxonomies",
    scheme: "concept_schemes",
    class: "classes",
    individual: "individuals",
    property: "property_definitions",
    relationship: "relationships",
    configuration: "configurations",
    dataset: "datasets",
  };
  const NICE = {
    taxonomy: "taxonomy",
    scheme: "concept scheme",
    class: "class",
    individual: "individual",
    property: "property",
    relationship: "relationship",
    configuration: "configuration",
    dataset: "dataset",
  };

  const find = (col, id) => state[col].find((x) => x.id === id);

  // ---- mutations --------------------------------------------------------
  function create(type, obj) {
    const col = collectionOf[type];
    const row = { version: 1, updated: "now", ...obj };
    state[col] = [row, ...state[col]];
    logActivity("create", `Created ${NICE[type]}`, row.id, row.title || row.name || "");
    notify();
    pushToast({ variant: "success", title: `${cap(NICE[type])} created`, subtitle: row.id });
    return row;
  }

  function update(type, id, patch, opts = {}) {
    const col = collectionOf[type];
    let updated;
    state[col] = state[col].map((x) => {
      if (x.id !== id) return x;
      updated = { ...x, ...patch, version: (x.version || 0) + 1, updated: "now" };
      return updated;
    });
    if (updated && !opts.silent) {
      logActivity("update", `Updated ${NICE[type]}`, id, opts.field ? `${opts.field} changed` : "");
    }
    notify();
    return updated;
  }

  function remove(type, id) {
    const imp = cascade(type, id);
    // delete dependents first
    state.relationships = state.relationships.filter((r) => !imp.relationshipIds.has(r.id));
    state.individuals = state.individuals.filter((i) => !imp.individualIds.has(i.id));
    state.classes = state.classes.filter((c) => !imp.classIds.has(c.id));
    state.concept_schemes = state.concept_schemes.filter((s) => !imp.schemeIds.has(s.id));
    state.configurations = state.configurations.filter((c) => !imp.configurationIds.has(c.id));
    const col = collectionOf[type];
    const self = find(col, id);
    state[col] = state[col].filter((x) => x.id !== id);
    const casc = imp.total;
    logActivity("delete", `Removed ${NICE[type]}`, id, casc ? `cascade ×${casc}` : "");
    notify();
    pushToast({
      variant: "info",
      title: `${cap(NICE[type])} deleted`,
      subtitle: casc ? `${id} · ${casc} dependent${casc === 1 ? "" : "s"} removed` : id,
    });
    return self;
  }

  function bulkRemove(type, ids) {
    let total = 0;
    ids.forEach((id) => {
      const imp = cascade(type, id);
      total += imp.total;
    });
    ids.forEach((id) => {
      const imp = cascade(type, id);
      state.relationships = state.relationships.filter((r) => !imp.relationshipIds.has(r.id));
      state.individuals = state.individuals.filter((i) => !imp.individualIds.has(i.id));
      state.classes = state.classes.filter((c) => !imp.classIds.has(c.id));
      state.concept_schemes = state.concept_schemes.filter((s) => !imp.schemeIds.has(s.id));
      const col = collectionOf[type];
      state[col] = state[col].filter((x) => x.id !== id);
    });
    logActivity(
      "delete",
      `Removed ${ids.length} ${pl(NICE[type], ids.length)}`,
      ids[0],
      total ? `cascade ×${total}` : "",
    );
    notify();
    pushToast({
      variant: "info",
      title: `${ids.length} ${pl(NICE[type], ids.length)} deleted`,
      subtitle: total ? `${total} dependents removed` : "",
    });
  }

  function bulkUpdate(type, ids, patch, label) {
    const col = collectionOf[type];
    state[col] = state[col].map((x) =>
      ids.includes(x.id) ? { ...x, ...patch, version: (x.version || 0) + 1, updated: "now" } : x,
    );
    logActivity(
      "update",
      `Updated ${ids.length} ${pl(NICE[type], ids.length)}`,
      ids[0],
      label || "",
    );
    notify();
    pushToast({ variant: "success", title: `${ids.length} updated`, subtitle: label || "" });
  }

  // ---- cascade impact ---------------------------------------------------
  // Returns sets of dependent ids + a flat list for display.
  function cascade(type, id) {
    const schemeIds = new Set();
    const classIds = new Set();
    const individualIds = new Set();
    const relationshipIds = new Set();
    const configurationIds = new Set();

    const addClass = (cid) => {
      if (classIds.has(cid)) return;
      classIds.add(cid);
      // children classes (recursive)
      state.classes.filter((c) => c.parent_class_id === cid).forEach((c) => addClass(c.id));
      // individuals of this class
      state.individuals
        .filter((i) => i.class_ids && i.class_ids.includes(cid))
        .forEach((i) => individualIds.add(i.id));
    };

    if (type === "taxonomy") {
      state.concept_schemes
        .filter((s) => s.taxonomy_id === id)
        .forEach((s) => {
          schemeIds.add(s.id);
          state.classes.filter((c) => c.concept_scheme_id === s.id).forEach((c) => addClass(c.id));
        });
    } else if (type === "scheme") {
      state.classes.filter((c) => c.concept_scheme_id === id).forEach((c) => addClass(c.id));
    } else if (type === "class") {
      addClass(id);
      classIds.delete(id); // the class itself is the subject, not a dependent
    } else if (type === "individual") {
      individualIds.add(id);
      individualIds.delete(id);
    } else if (type === "property") {
      // relationships using this predicate
    }

    // relationships touching any affected node (or self)
    const affected = new Set([id, ...classIds, ...individualIds]);
    state.relationships.forEach((r) => {
      if (type === "property" && r.property_definition_id === id) relationshipIds.add(r.id);
      else if (affected.has(r.source_id) || affected.has(r.target_id)) relationshipIds.add(r.id);
    });

    const items = [];
    schemeIds.forEach((sid) => {
      const s = find("concept_schemes", sid);
      if (s) items.push({ type: "scheme", id: sid, label: s.title });
    });
    classIds.forEach((cid) => {
      const c = find("classes", cid);
      if (c) items.push({ type: "class", id: cid, label: c.title });
    });
    individualIds.forEach((iid) => {
      const i = find("individuals", iid);
      if (i) items.push({ type: "individual", id: iid, label: i.title });
    });
    relationshipIds.forEach((rid) => {
      const r = find("relationships", rid);
      if (r) items.push({ type: "relationship", id: rid, label: r.id });
    });

    return {
      schemeIds,
      classIds,
      individualIds,
      relationshipIds,
      configurationIds,
      items,
      counts: {
        scheme: schemeIds.size,
        class: classIds.size,
        individual: individualIds.size,
        relationship: relationshipIds.size,
      },
      total: schemeIds.size + classIds.size + individualIds.size + relationshipIds.size,
    };
  }

  // ---- validation -------------------------------------------------------
  const SNAKE = /^[a-z][a-z0-9_]*$/;
  function validateIdent(type, value, { excludeId } = {}) {
    if (!value || !value.trim()) return "Required.";
    if (!SNAKE.test(value))
      return "Use snake_case: lowercase, digits, underscores; must start with a letter.";
    const col = collectionOf[type];
    const clash = state[col].some((x) => x.id === value && x.id !== excludeId);
    if (clash) return `\u201c${value}\u201d already exists.`;
    return null;
  }

  // ---- simulated AI suggestion -----------------------------------------
  const SUGGEST_DB = {
    cls_neuron:
      "An electrically excitable cell that processes and transmits information through electrical and chemical signals across synapses.",
    cls_gene:
      "A heritable unit of DNA that encodes a functional product \u2014 typically a protein or RNA \u2014 and governs an organism\u2019s traits.",
    cls_protein:
      "A large biomolecule composed of amino-acid chains that performs structural, catalytic, or signalling roles within cells.",
    cls_co2:
      "A colourless greenhouse gas released by respiration and combustion; the principal driver of anthropogenic radiative forcing.",
    prop_related_to:
      "A generic, untyped association asserting that two nodes are conceptually connected without specifying the nature of the link.",
    prop_located_in:
      "A spatial-containment predicate asserting that the source node is physically or topologically inside the target node.",
  };
  function suggest({ type, id, title, context }) {
    return new Promise((resolve) => {
      const delay = 700 + Math.random() * 600;
      setTimeout(() => {
        if (id && SUGGEST_DB[id]) return resolve(SUGGEST_DB[id]);
        const t = (title || "This " + (NICE[type] || "node")).trim();
        const ctx = context ? ` within the ${context} context` : "";
        resolve(
          `${t} is a ${NICE[type] || "concept"}${ctx} that captures a distinct, well-scoped idea in the knowledge graph. It is curated to support retrieval-augmented generation and downstream agent reasoning.`,
        );
      }, delay);
    });
  }

  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

  // ---- simulated AI relationship suggestions ----------------------------
  // Proposes typed triples (this node → predicate → another node), skipping
  // any that already exist. Curated edges for the seed graph, plus a generic
  // same-scheme fallback.
  function suggestRelationships(node) {
    return new Promise((resolve) => {
      setTimeout(
        () => {
          const propByIdent = (ident) =>
            state.property_definitions.find((p) => p.identifier === ident);
          const existing = new Set(
            state.relationships
              .filter((r) => r.source_id === node.id || r.target_id === node.id)
              .map(
                (r) =>
                  (r.source_id === node.id ? r.target_id : r.source_id) +
                  "|" +
                  r.property_definition_id,
              ),
          );
          const out = [];
          const push = (predIdent, targetId, conf, rationale) => {
            const pred = propByIdent(predIdent);
            const target =
              state.classes.find((c) => c.id === targetId) ||
              state.individuals.find((i) => i.id === targetId);
            if (!pred || !target) return;
            if (existing.has(targetId + "|" + pred.id)) return;
            if (out.some((o) => o.target_id === targetId && o.property_definition_id === pred.id))
              return;
            out.push({
              property_definition_id: pred.id,
              predicate: pred.identifier,
              target_id: targetId,
              target_label: target.title,
              target_domain: target.domain,
              confidence: conf,
              rationale,
            });
          };
          const CURATED = {
            cls_gene: [
              ["encodes", "cls_protein", 0.96, "Genes encode protein products."],
              ["has_part", "cls_variant", 0.82, "Variants are subsequences of a gene."],
            ],
            cls_protein: [
              ["part_of", "cls_pathway", 0.9, "Proteins act within molecular pathways."],
            ],
            cls_cell: [
              ["has_part", "cls_nucleus", 0.98, "A cell contains a nucleus."],
              ["has_part", "cls_mito", 0.97, "A cell contains mitochondria."],
              ["has_part", "cls_membrane", 0.95, "A cell is bounded by a membrane."],
            ],
            cls_nucleus: [["part_of", "cls_cell", 0.98, "The nucleus is part of the cell."]],
            cls_mito: [["part_of", "cls_cell", 0.98, "Mitochondria are part of the cell."]],
            cls_co2: [["causes", "cls_warming", 0.93, "CO₂ is a primary driver of warming."]],
            cls_warming: [["causes", "cls_sealevel", 0.9, "Warming drives sea-level rise."]],
            cls_deforest: [["emits", "cls_co2", 0.86, "Deforestation releases stored CO₂."]],
            cls_pathway: [["has_part", "cls_protein", 0.84, "Pathways are composed of proteins."]],
          };
          (CURATED[node.id] || []).forEach(([p, t, c, r]) => push(p, t, c, r));
          if (out.length < 2) {
            state.classes
              .filter((c) => c.id !== node.id && c.concept_scheme_id === node.concept_scheme_id)
              .slice(0, 3)
              .forEach((s) => {
                if (out.length < 3)
                  push("related_to", s.id, 0.61, "Co-occurs in the same concept scheme.");
              });
          }
          resolve(out.slice(0, 3));
        },
        800 + Math.random() * 500,
      );
    });
  }

  // ---- simulated AI grounding suggestions -------------------------------
  // Proposes external reference sources (from CS_DATA.reference_sources) to
  // ground a node against, by domain, skipping ones already attached.
  function suggestGrounding(node) {
    return new Promise((resolve) => {
      setTimeout(
        () => {
          const sources = window.CS_DATA.reference_sources || [];
          const byDomain = {
            life: ["src_pubmed", "src_uniprot", "src_reactome", "src_wikidata"],
            climate: ["src_ipcc", "src_eia", "src_wikidata"],
            software: ["src_arxiv", "src_wikidata"],
          };
          const ids = byDomain[node.domain] || ["src_wikidata"];
          const have = new Set((node.grounding || []).map((g) => g.source_id));
          const out = [];
          ids.forEach((sid) => {
            const s = sources.find((x) => x.id === sid);
            if (s && !have.has(sid) && out.length < 3) {
              out.push({
                source_id: sid,
                name: s.name,
                url: s.url,
                confidence: sid === "src_wikidata" ? 0.78 : 0.91,
                rationale: `${s.name} is an authoritative source for ${node.domain} concepts.`,
              });
            }
          });
          resolve(out);
        },
        800 + Math.random() * 500,
      );
    });
  }

  // ---- dataset activation ----------------------------------------------
  // Exactly one dataset is active at a time. Activating one deactivates the
  // rest. Mirrors POST /api/v1/admin/datasets/{id}/activate.
  function activateDataset(id) {
    const target = find("datasets", id);
    if (!target || target.is_active) return target;
    state.datasets = state.datasets.map((d) => {
      if (d.id === id)
        return { ...d, is_active: true, last_accessed: "now", version: (d.version || 0) + 1 };
      if (d.is_active) return { ...d, is_active: false };
      return d;
    });
    logActivity("update", "Activated dataset", id, target.title || "");
    notify();
    pushToast({
      variant: "success",
      title: "Dataset activated",
      subtitle: `${target.title} is now the working set`,
    });
    return find("datasets", id);
  }

  // attach a grounding reference to a node (optimistic, version-bumped)
  function addGrounding(type, node, ref) {
    const id = "gr_" + Math.random().toString(36).slice(2, 6);
    const grounding = [...(node.grounding || []), { id, ...ref }];
    update(type, node.id, { grounding }, { field: "grounding" });
    pushToast({
      variant: "success",
      title: "Grounding reference added",
      subtitle: `${ref.name} → ${node.id}`,
    });
  }
  function removeGrounding(type, node, grId) {
    update(
      type,
      node.id,
      { grounding: (node.grounding || []).filter((g) => g.id !== grId) },
      { field: "grounding" },
    );
  }

  // English-ish pluralizer for the NICE nouns (class→classes, taxonomy→taxonomies…)
  const pl = (word, n) =>
    n === 1
      ? word
      : /y$/.test(word)
        ? word.replace(/y$/, "ies")
        : /(s|sh|ch|x)$/.test(word)
          ? word + "es"
          : word + "s";

  window.CSStore = {
    subscribe,
    getSnapshot,
    create,
    update,
    remove,
    bulkRemove,
    bulkUpdate,
    cascade,
    validateIdent,
    suggest,
    suggestRelationships,
    suggestGrounding,
    addGrounding,
    removeGrounding,
    activateDataset,
    toast: pushToast,
    dismissToast,
    toastSub,
    toastSnap,
    collectionOf,
    NICE,
    pl,
  };

  window.useCS = function useCS() {
    return useSyncExternalStore(subscribe, getSnapshot);
  };
  window.useCSToasts = function useCSToasts() {
    return useSyncExternalStore(toastSub, toastSnap);
  };
})();
