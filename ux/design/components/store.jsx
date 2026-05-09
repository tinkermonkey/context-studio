// Studio store — mutable in-memory mirror of the API. Implements the
// constraint surface from the backend memo: required parents, ordered
// class_ids, property-definition auto-creation, no self-loops, unique
// triples, optimistic version bumping, and the standard error shape.
const { createContext, useContext } = React;

class APIError extends Error {
  constructor(error_code, detail, status = 400) {
    super(detail);
    this.error_code = error_code;
    this.detail = detail;
    this.status = status;
  }
}

function makeId(prefix) {
  return prefix + "_" + Math.random().toString(36).slice(2, 8);
}

function snakeify(s) {
  return (s || "")
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

// Single in-memory store, lifted out so cross-component changes propagate.
function createStore() {
  const D = window.CS_DATA;
  const state = {
    taxonomies: [...D.taxonomies],
    concept_schemes: [...D.concept_schemes],
    classes: [...D.classes],
    individuals: [...D.individuals],
    property_definitions: [...D.property_definitions],
    relationships: [...D.relationships],
  };
  const subs = new Set();
  const notify = () => subs.forEach((cb) => cb());

  // ---------- helpers ----------
  const findOrThrow = (list, id, kind) => {
    const x = list.find((n) => n.id === id);
    if (!x) throw new APIError("not_found", kind + " " + id + " not found", 404);
    return x;
  };
  const requireTitle = (t) => {
    if (!t || !t.trim()) throw new APIError("invalid_input", "Title is required", 400);
  };

  // ---------- Taxonomy CRUD ----------
  const createTaxonomy = (data) => {
    requireTitle(data.title);
    const t = {
      id: makeId("tax"),
      node_type: "taxonomy",
      domain: data.domain || "default",
      version: 0,
      ...data,
    };
    state.taxonomies = [t, ...state.taxonomies];
    notify();
    return t;
  };
  const updateTaxonomy = (id, patch) => {
    const t = findOrThrow(state.taxonomies, id, "Taxonomy");
    if ("title" in patch) requireTitle(patch.title);
    const next = { ...t, ...patch, version: t.version + 1 };
    state.taxonomies = state.taxonomies.map((x) => (x.id === id ? next : x));
    notify();
    return next;
  };
  const deleteTaxonomy = (id) => {
    if (state.concept_schemes.some((s) => s.taxonomy_id === id))
      throw new APIError(
        "has_children",
        "Cannot delete a taxonomy that contains concept schemes",
        409,
      );
    state.taxonomies = state.taxonomies.filter((x) => x.id !== id);
    notify();
  };

  // ---------- ConceptScheme CRUD ----------
  const createScheme = (data) => {
    requireTitle(data.title);
    if (!data.taxonomy_id) throw new APIError("invalid_input", "taxonomy_id is required", 400);
    const tax = findOrThrow(state.taxonomies, data.taxonomy_id, "Taxonomy");
    const s = {
      id: makeId("sch"),
      node_type: "concept_scheme",
      domain: tax.domain,
      version: 0,
      ...data,
    };
    state.concept_schemes = [s, ...state.concept_schemes];
    notify();
    return s;
  };
  const updateScheme = (id, patch) => {
    const s = findOrThrow(state.concept_schemes, id, "ConceptScheme");
    if ("title" in patch) requireTitle(patch.title);
    const next = { ...s, ...patch, version: s.version + 1 };
    state.concept_schemes = state.concept_schemes.map((x) => (x.id === id ? next : x));
    notify();
    return next;
  };
  const deleteScheme = (id) => {
    if (state.classes.some((c) => c.concept_scheme_id === id))
      throw new APIError(
        "has_children",
        "Cannot delete a concept scheme that contains classes",
        409,
      );
    state.concept_schemes = state.concept_schemes.filter((x) => x.id !== id);
    notify();
  };

  // ---------- Class CRUD + tree ----------
  const createClass = (data) => {
    requireTitle(data.title);
    if (!data.concept_scheme_id)
      throw new APIError("invalid_input", "concept_scheme_id is required", 400);
    const scheme = findOrThrow(state.concept_schemes, data.concept_scheme_id, "ConceptScheme");
    if (data.parent_class_id) {
      const parent = findOrThrow(state.classes, data.parent_class_id, "Class");
      if (parent.concept_scheme_id !== scheme.id)
        throw new APIError(
          "invalid_input",
          "parent_class_id must belong to the same concept scheme",
          400,
        );
    }
    const cls = {
      id: makeId("cls"),
      node_type: "class",
      taxonomy_id: scheme.taxonomy_id,
      domain: scheme.domain,
      parent_class_id: null,
      structural_property_id: null,
      external_references: [],
      lexical_senses: [],
      data_properties: [],
      version: 0,
      ...data,
    };
    state.classes = [cls, ...state.classes];
    notify();
    return cls;
  };
  const updateClass = (id, patch) => {
    const c = findOrThrow(state.classes, id, "Class");
    if ("title" in patch) requireTitle(patch.title);
    // The official UpdateRequest only accepts title + description; rich attrs go through
    // dedicated sub-resource endpoints — but we still apply them here for the mock.
    const next = { ...c, ...patch, version: c.version + 1 };
    state.classes = state.classes.map((x) => (x.id === id ? next : x));
    notify();
    return next;
  };
  const deleteClass = (id) => {
    if (state.classes.some((c) => c.parent_class_id === id))
      throw new APIError(
        "has_children",
        "Cannot delete a class with children — reparent or delete them first",
        409,
      );
    if (state.individuals.some((i) => i.class_ids.includes(id)))
      throw new APIError("has_individuals", "Cannot delete a class with individuals", 409);
    if (state.relationships.some((r) => r.source_id === id || r.target_id === id))
      throw new APIError(
        "has_relationships",
        "Cannot delete a class still used in relationships",
        409,
      );
    state.classes = state.classes.filter((x) => x.id !== id);
    notify();
  };
  // ClassMoveRequest — only target_scheme_id, must share taxonomy
  const moveClass = (id, target_scheme_id) => {
    const c = findOrThrow(state.classes, id, "Class");
    const target = findOrThrow(state.concept_schemes, target_scheme_id, "ConceptScheme");
    if (target.taxonomy_id !== c.taxonomy_id)
      throw new APIError(
        "invalid_input",
        "A class cannot be moved to a scheme in a different taxonomy",
        400,
      );
    const next = {
      ...c,
      concept_scheme_id: target.id,
      parent_class_id: null,
      version: c.version + 1,
    };
    state.classes = state.classes.map((x) => (x.id === id ? next : x));
    notify();
    return next;
  };

  // ---------- Individual CRUD ----------
  // Title uniqueness is scoped per parent class. Returns the offending class id (or null).
  const titleConflict = (title, class_ids, ignoreIndividualId = null) => {
    const t = (title || "").trim().toLowerCase();
    for (const cid of class_ids) {
      const clash = state.individuals.find(
        (i) =>
          i.id !== ignoreIndividualId &&
          i.class_ids.includes(cid) &&
          (i.title || "").trim().toLowerCase() === t,
      );
      if (clash) return { class_id: cid, individual: clash };
    }
    return null;
  };

  // POST /individuals — accepts only title, description, class_ids (string|list).
  // data_properties + external_references start empty.
  const createIndividual = (data) => {
    requireTitle(data.title);
    let class_ids = data.class_ids;
    if (typeof class_ids === "string") class_ids = [class_ids];
    if (!Array.isArray(class_ids) || class_ids.length === 0)
      throw new APIError("invalid_input", "At least one class_id is required", 422);
    // Dedupe while preserving order
    class_ids = class_ids.filter((c, i) => class_ids.indexOf(c) === i);
    class_ids.forEach((cid) => findOrThrow(state.classes, cid, "Class"));
    const conflict = titleConflict(data.title, class_ids);
    if (conflict) {
      const cls = state.classes.find((c) => c.id === conflict.class_id);
      throw new APIError(
        "duplicate_title",
        '"' + data.title + '" already exists in class ' + (cls?.title || conflict.class_id),
        409,
      );
    }
    const now = new Date().toISOString();
    const ind = {
      id: makeId("ind"),
      node_type: "individual",
      title: data.title.trim(),
      description: data.description || "",
      class_ids,
      data_properties: [],
      external_references: [],
      // Display-only metadata kept on the row for the existing UI
      source: data.source || "manual",
      confidence: data.confidence ?? 1.0,
      created_at: now,
      last_modified: now,
      updated: now.slice(0, 10),
      version: 1,
    };
    state.individuals = [ind, ...state.individuals];
    notify();
    return ind;
  };

  // PUT /individuals/{id} — only title + description. No-op detection: if neither
  // value actually changes, last_modified is not touched and no version bump.
  const updateIndividual = (id, patch) => {
    const i = findOrThrow(state.individuals, id, "Individual");
    const titleProvided = "title" in patch && patch.title !== undefined;
    const descProvided = "description" in patch && patch.description !== undefined;
    if (titleProvided) requireTitle(patch.title);
    const nextTitle = titleProvided ? patch.title.trim() : i.title;
    const nextDesc = descProvided ? patch.description || "" : i.description || "";
    const sameTitle = nextTitle === i.title;
    const sameDesc = nextDesc === (i.description || "");
    if (sameTitle && sameDesc) return { ...i, _noop: true };
    if (!sameTitle) {
      const conflict = titleConflict(nextTitle, i.class_ids, i.id);
      if (conflict) {
        const cls = state.classes.find((c) => c.id === conflict.class_id);
        throw new APIError(
          "duplicate_title",
          '"' + nextTitle + '" already exists in class ' + (cls?.title || conflict.class_id),
          409,
        );
      }
    }
    const now = new Date().toISOString();
    const next = {
      ...i,
      title: nextTitle,
      description: nextDesc,
      last_modified: now,
      updated: now.slice(0, 10),
      version: i.version + 1,
    };
    state.individuals = state.individuals.map((x) => (x.id === id ? next : x));
    notify();
    return next;
  };

  // POST /individuals/{id}/classes — append a parent class to the end of the list.
  const addIndividualClass = (id, class_id) => {
    const i = findOrThrow(state.individuals, id, "Individual");
    findOrThrow(state.classes, class_id, "Class");
    if (i.class_ids.includes(class_id))
      throw new APIError("duplicate", "Individual is already a member of this class", 409);
    const conflict = titleConflict(i.title, [class_id], i.id);
    if (conflict) {
      const cls = state.classes.find((c) => c.id === conflict.class_id);
      throw new APIError(
        "duplicate_title",
        '"' + i.title + '" already exists in class ' + (cls?.title || conflict.class_id),
        409,
      );
    }
    const now = new Date().toISOString();
    const next = {
      ...i,
      class_ids: [...i.class_ids, class_id],
      last_modified: now,
      updated: now.slice(0, 10),
      version: i.version + 1,
    };
    state.individuals = state.individuals.map((x) => (x.id === id ? next : x));
    notify();
    return next;
  };

  // DELETE /individuals/{id}/classes/{class_id} — rejects removing the last parent.
  const removeIndividualClass = (id, class_id) => {
    const i = findOrThrow(state.individuals, id, "Individual");
    if (!i.class_ids.includes(class_id))
      throw new APIError("not_found", "Individual is not a member of class " + class_id, 404);
    if (i.class_ids.length === 1)
      throw new APIError(
        "invalid_input",
        "Cannot remove the last parent class — an individual must always have at least one",
        400,
      );
    const now = new Date().toISOString();
    const next = {
      ...i,
      class_ids: i.class_ids.filter((c) => c !== class_id),
      last_modified: now,
      updated: now.slice(0, 10),
      version: i.version + 1,
    };
    state.individuals = state.individuals.map((x) => (x.id === id ? next : x));
    notify();
    return next;
  };

  // PUT /individuals/{id}/classes — full replacement. The ID *set* must match exactly
  // what is on the individual; this endpoint is for reorder, not for diffing.
  const replaceIndividualClasses = (id, class_ids) => {
    const i = findOrThrow(state.individuals, id, "Individual");
    if (!Array.isArray(class_ids) || class_ids.length === 0)
      throw new APIError("invalid_input", "class_ids cannot be empty", 400);
    const incoming = new Set(class_ids);
    const current = new Set(i.class_ids);
    const sameSet = incoming.size === current.size && [...incoming].every((c) => current.has(c));
    if (!sameSet)
      throw new APIError(
        "invalid_input",
        "Reorder list must match the current class set exactly — use add/remove for changes",
        400,
      );
    if (class_ids.every((c, idx) => c === i.class_ids[idx])) return { ...i, _noop: true };
    const now = new Date().toISOString();
    const next = {
      ...i,
      class_ids: [...class_ids],
      last_modified: now,
      updated: now.slice(0, 10),
      version: i.version + 1,
    };
    state.individuals = state.individuals.map((x) => (x.id === id ? next : x));
    notify();
    return next;
  };

  // GET /individuals/{id}/inherited-properties — derived, deduped, first-parent-wins.
  const getInheritedProperties = (id) => {
    const i = state.individuals.find((x) => x.id === id);
    if (!i) return { items: [], total: 0 };
    const seen = new Map();
    for (const cid of i.class_ids) {
      const cls = state.classes.find((c) => c.id === cid);
      if (!cls) continue;
      for (const dp of cls.data_properties || []) {
        const key = dp.key;
        if (!seen.has(key))
          seen.set(key, {
            ...dp,
            identifier: key,
            inherited_from_class_id: cls.id,
            inherited_from_class_title: cls.title,
          });
      }
    }
    const items = [...seen.values()];
    return { items, total: items.length };
  };

  // DELETE /individuals/{id} — cascades all relationships (source or target). Returns
  // a summary of what was deleted so the UI can confirm the cascade after the fact.
  const deleteIndividual = (id) => {
    const i = findOrThrow(state.individuals, id, "Individual");
    const cascadedRels = state.relationships.filter(
      (r) => r.source_id === id || r.target_id === id,
    );
    state.relationships = state.relationships.filter(
      (r) => r.source_id !== id && r.target_id !== id,
    );
    state.individuals = state.individuals.filter((x) => x.id !== id);
    notify();
    return { id: i.id, title: i.title, cascaded_relationships: cascadedRels };
  };

  // Helper used by the UI to count relationships before showing a delete confirm.
  const individualRelationships = (id) =>
    state.relationships.filter((r) => r.source_id === id || r.target_id === id);

  // ---------- PropertyDefinition CRUD ----------
  const createPropertyDefinition = (data) => {
    if (!data.identifier) throw new APIError("invalid_input", "identifier is required", 400);
    const ident = snakeify(data.identifier);
    if (state.property_definitions.some((p) => p.identifier === ident))
      throw new APIError(
        "duplicate",
        'A property with identifier "' + ident + '" already exists',
        409,
      );
    const p = {
      id: makeId("prop"),
      identifier: ident,
      title: data.title || ident,
      description: "",
      is_relevant: null,
      origin: "manual",
      version: 0,
      ...data,
      identifier: ident,
    };
    state.property_definitions = [p, ...state.property_definitions];
    notify();
    return p;
  };
  const updatePropertyDefinition = (id, patch) => {
    const p = findOrThrow(state.property_definitions, id, "PropertyDefinition");
    // identifier is immutable
    const { identifier: _ident, ...allowed } = patch;
    const next = { ...p, ...allowed, version: p.version + 1 };
    state.property_definitions = state.property_definitions.map((x) => (x.id === id ? next : x));
    notify();
    return next;
  };
  const deletePropertyDefinition = (id) => {
    if (state.relationships.some((r) => r.property_definition_id === id))
      throw new APIError("in_use", "Cannot delete a property used by existing relationships", 409);
    state.property_definitions = state.property_definitions.filter((x) => x.id !== id);
    notify();
  };

  // ---------- Relationship CRUD ----------
  // Auto-creates a PropertyDefinition if relationship_type doesn't match an existing one.
  const findEntity = (id) => {
    return (
      state.classes.find((c) => c.id === id) || state.individuals.find((i) => i.id === id) || null
    );
  };
  const createRelationship = (data) => {
    if (!data.source_id || !data.target_id)
      throw new APIError("invalid_input", "source_id and target_id are required", 400);
    if (data.source_id === data.target_id)
      throw new APIError(
        "invalid_input",
        "Self-loops are not allowed (source_id == target_id)",
        400,
      );
    const s = findEntity(data.source_id);
    const t = findEntity(data.target_id);
    if (!s) throw new APIError("not_found", "Source entity " + data.source_id + " not found", 404);
    if (!t) throw new APIError("not_found", "Target entity " + data.target_id + " not found", 404);

    let property_definition_id = data.property_definition_id;
    let auto_created = null;
    if (!property_definition_id) {
      const ident = snakeify(data.relationship_type || "related_to");
      let prop = state.property_definitions.find((p) => p.identifier === ident);
      if (!prop) {
        prop = {
          id: makeId("prop"),
          identifier: ident,
          title: ident
            .split("_")
            .map((w) => w[0].toUpperCase() + w.slice(1))
            .join(" "),
          description: "Auto-created from relationship",
          is_relevant: null,
          origin: "auto",
          version: 0,
        };
        state.property_definitions = [prop, ...state.property_definitions];
        auto_created = prop;
      }
      property_definition_id = prop.id;
    } else {
      findOrThrow(state.property_definitions, property_definition_id, "PropertyDefinition");
    }

    if (
      state.relationships.some(
        (r) =>
          r.source_id === data.source_id &&
          r.target_id === data.target_id &&
          r.property_definition_id === property_definition_id,
      )
    )
      throw new APIError(
        "duplicate",
        "A relationship with this (source, target, property) triple already exists",
        409,
      );

    const rel = {
      id: makeId("rel"),
      source_id: data.source_id,
      target_id: data.target_id,
      property_definition_id,
      source: data.source || "manual",
      confidence: data.confidence ?? 1.0,
      created: new Date().toISOString().slice(0, 10),
    };
    state.relationships = [rel, ...state.relationships];
    notify();
    return { rel, auto_created };
  };
  const deleteRelationship = (id) => {
    state.relationships = state.relationships.filter((r) => r.id !== id);
    notify();
  };

  return {
    getState: () => state,
    subscribe: (cb) => {
      subs.add(cb);
      return () => subs.delete(cb);
    },
    actions: {
      createTaxonomy,
      updateTaxonomy,
      deleteTaxonomy,
      createScheme,
      updateScheme,
      deleteScheme,
      createClass,
      updateClass,
      deleteClass,
      moveClass,
      createIndividual,
      updateIndividual,
      deleteIndividual,
      addIndividualClass,
      removeIndividualClass,
      replaceIndividualClasses,
      getInheritedProperties,
      individualRelationships,
      createPropertyDefinition,
      updatePropertyDefinition,
      deletePropertyDefinition,
      createRelationship,
      deleteRelationship,
    },
  };
}

const StoreCtx = createContext(null);
const ToastCtx = createContext(null);

function StoreProvider({ children }) {
  const storeRef = useRef();
  if (!storeRef.current) storeRef.current = createStore();

  // Tick subscription so consumers re-render
  const [, force] = useState(0);
  useEffect(() => storeRef.current.subscribe(() => force((n) => n + 1)), []);

  // Toast queue
  const [toasts, setToasts] = useState([]);
  const pushToast = useCallback((toast) => {
    const id = makeId("t");
    setToasts((all) => [...all, { id, ...toast }]);
    setTimeout(() => setToasts((all) => all.filter((t) => t.id !== id)), toast.duration || 4200);
  }, []);
  const dismissToast = useCallback((id) => setToasts((all) => all.filter((t) => t.id !== id)), []);

  // Wrap actions so errors flow through toast system and successes get a confirmation
  const actions = useMemo(() => {
    const raw = storeRef.current.actions;
    const wrap =
      (name, fn, successMsg) =>
      (...args) => {
        try {
          const result = fn(...args);
          if (successMsg) {
            const msg = typeof successMsg === "function" ? successMsg(result, ...args) : successMsg;
            if (msg) pushToast({ kind: "success", title: msg.title || "Saved", body: msg.body });
          }
          return result;
        } catch (e) {
          if (e instanceof APIError) {
            pushToast({
              kind: "error",
              title: "HTTP " + e.status + " · " + e.error_code,
              body: e.detail,
              duration: 6000,
            });
          } else {
            pushToast({ kind: "error", title: "Unexpected error", body: e.message });
          }
          throw e;
        }
      };
    return {
      createTaxonomy: wrap("createTaxonomy", raw.createTaxonomy, (r) => ({
        title: "Taxonomy created",
        body: r.title,
      })),
      updateTaxonomy: wrap("updateTaxonomy", raw.updateTaxonomy, (r) => ({
        title: "Taxonomy updated",
        body: r.title + " · v" + r.version,
      })),
      deleteTaxonomy: wrap("deleteTaxonomy", raw.deleteTaxonomy, { title: "Taxonomy deleted" }),
      createScheme: wrap("createScheme", raw.createScheme, (r) => ({
        title: "Concept scheme created",
        body: r.title,
      })),
      updateScheme: wrap("updateScheme", raw.updateScheme, (r) => ({
        title: "Concept scheme updated",
        body: r.title + " · v" + r.version,
      })),
      deleteScheme: wrap("deleteScheme", raw.deleteScheme, { title: "Concept scheme deleted" }),
      createClass: wrap("createClass", raw.createClass, (r) => ({
        title: "Class created",
        body: r.title,
      })),
      updateClass: wrap("updateClass", raw.updateClass, (r) => ({
        title: "Class updated",
        body: r.title + " · v" + r.version,
      })),
      deleteClass: wrap("deleteClass", raw.deleteClass, { title: "Class deleted" }),
      moveClass: wrap("moveClass", raw.moveClass, (r) => ({ title: "Class moved", body: r.title })),
      createIndividual: wrap("createIndividual", raw.createIndividual, (r) => ({
        title: "Individual created",
        body: r.title,
      })),
      updateIndividual: wrap("updateIndividual", raw.updateIndividual, (r) =>
        r._noop ? null : { title: "Individual updated", body: r.title + " · v" + r.version },
      ),
      addIndividualClass: wrap("addIndividualClass", raw.addIndividualClass, (r) => ({
        title: "Parent class added",
        body: r.title + " · " + r.class_ids.length + " parents",
      })),
      removeIndividualClass: wrap("removeIndividualClass", raw.removeIndividualClass, (r) => ({
        title: "Parent class removed",
        body: r.title + " · " + r.class_ids.length + " parents",
      })),
      replaceIndividualClasses: wrap(
        "replaceIndividualClasses",
        raw.replaceIndividualClasses,
        (r) => (r._noop ? null : { title: "Class order updated", body: r.title }),
      ),
      deleteIndividual: wrap("deleteIndividual", raw.deleteIndividual, (r) => ({
        title: "Individual deleted",
        body: r.cascaded_relationships.length
          ? "Cascaded " +
            r.cascaded_relationships.length +
            " relationship" +
            (r.cascaded_relationships.length === 1 ? "" : "s")
          : null,
      })),
      getInheritedProperties: raw.getInheritedProperties,
      individualRelationships: raw.individualRelationships,
      createPropertyDefinition: wrap(
        "createPropertyDefinition",
        raw.createPropertyDefinition,
        (r) => ({ title: "Property created", body: r.identifier }),
      ),
      updatePropertyDefinition: wrap(
        "updatePropertyDefinition",
        raw.updatePropertyDefinition,
        (r) => ({ title: "Property updated", body: r.identifier + " · v" + r.version }),
      ),
      deletePropertyDefinition: wrap("deletePropertyDefinition", raw.deletePropertyDefinition, {
        title: "Property deleted",
      }),
      createRelationship: wrap("createRelationship", raw.createRelationship, (r) => ({
        title: "Relationship created",
        body: r.auto_created ? 'Auto-created property "' + r.auto_created.identifier + '"' : null,
      })),
      deleteRelationship: wrap("deleteRelationship", raw.deleteRelationship, {
        title: "Relationship deleted",
      }),
    };
  }, [pushToast]);

  const value = useMemo(
    () => ({
      state: storeRef.current.getState(),
      actions,
    }),
    [actions, toasts],
  ); // toasts in deps just to retrigger; state mutates in place + force()

  return (
    <StoreCtx.Provider value={value}>
      <ToastCtx.Provider value={{ toasts, pushToast, dismissToast }}>{children}</ToastCtx.Provider>
    </StoreCtx.Provider>
  );
}

const useStore = () => useContext(StoreCtx);
const useToast = () => useContext(ToastCtx);

window.StoreProvider = StoreProvider;
window.useStore = useStore;
window.useToast = useToast;
window.APIError = APIError;
window.snakeify = snakeify;
