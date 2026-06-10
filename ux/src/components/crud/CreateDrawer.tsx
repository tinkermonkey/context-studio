import { useState, useEffect, useRef, useCallback } from "react";
import {
  Button,
  Field,
  Icon,
  Select,
  TextArea,
  TextInput,
  SegmentedControl,
  RelationshipBuilder,
  type RelationshipBuilderValue,
} from "@tinkermonkey/heimdall-ui";
import { useCreateTaxonomy, useTaxonomies } from "@/api/hooks/ontology/useTaxonomies";
import { useCreateScheme, useSchemes } from "@/api/hooks/ontology/useSchemes";
import { useCreateClass, useClasses } from "@/api/hooks/ontology/useClasses";
import { useCreateProperty } from "@/api/hooks/ontology/useProperties";
import { useProperties } from "@/api/hooks/ontology/useProperties";
import { useCreateIndividual } from "@/api/hooks/ontology/useIndividuals";
import { useCreateRelationship } from "@/api/hooks/ontology/useRelationships";

export type EntityType =
  | "taxonomy"
  | "scheme"
  | "class"
  | "property"
  | "individual"
  | "relationship";

interface EntityConfig {
  icon: string;
  eyebrow: string;
  title: string;
  description: string;
  idPrefix: string | null;
  requiredFields: string[];
  requirementLabels: Record<string, string>;
}

const ENTITY_CONFIG: Record<EntityType, EntityConfig> = {
  taxonomy: {
    icon: "schema",
    eyebrow: "NEW · TAXONOMY",
    title: "Taxonomy",
    description: "A taxonomy is the top-level domain that groups related concept schemes.",
    idPrefix: "tax_",
    requiredFields: ["title"],
    requirementLabels: { title: "title" },
  },
  scheme: {
    icon: "layout",
    eyebrow: "NEW · CONCEPT SCHEME",
    title: "Concept Scheme",
    description: "A concept scheme organizes related classes within a taxonomy domain.",
    idPrefix: "sch_",
    requiredFields: ["title", "taxonomyId"],
    requirementLabels: { title: "title", taxonomyId: "taxonomy" },
  },
  class: {
    icon: "component",
    eyebrow: "NEW · CLASS",
    title: "Class",
    description: "A class defines a category of entities within a concept scheme.",
    idPrefix: "cls_",
    requiredFields: ["title", "schemeId"],
    requirementLabels: { title: "title", schemeId: "scheme" },
  },
  property: {
    icon: "link",
    eyebrow: "NEW · PROPERTY",
    title: "Property",
    description: "A property defines a typed relationship between ontology entities.",
    idPrefix: "",
    requiredFields: ["title"],
    requirementLabels: { title: "title" },
  },
  individual: {
    icon: "user",
    eyebrow: "NEW · INDIVIDUAL",
    title: "Individual",
    description: "An individual is a specific instance of one or more classes.",
    idPrefix: "ind_",
    requiredFields: ["title", "classIds"],
    requirementLabels: { title: "title", classIds: "class" },
  },
  relationship: {
    icon: "arrowRight",
    eyebrow: "NEW · RELATIONSHIP",
    title: "Relationship",
    description: "A relationship asserts a typed connection between two ontology entities.",
    idPrefix: null,
    requiredFields: ["sourceId", "targetId", "relationshipType"],
    requirementLabels: { sourceId: "source", targetId: "target", relationshipType: "predicate" },
  },
};

interface FormValues {
  title: string;
  identifier: string;
  description: string;
  taxonomyId: string;
  schemeId: string;
  parentClassId: string;
  classIds: string[];
  relevance: string;
  sourceId: string;
  targetId: string;
  relationshipType: string;
  confidence: number;
  sourceText: string;
}

function defaultValues(initialTaxonomyId?: string, initialSchemeId?: string): FormValues {
  return {
    title: "",
    identifier: "",
    description: "",
    taxonomyId: initialTaxonomyId ?? "",
    schemeId: initialSchemeId ?? "",
    parentClassId: "",
    classIds: [],
    relevance: "relevant",
    sourceId: "",
    targetId: "",
    relationshipType: "",
    confidence: 0.8,
    sourceText: "",
  };
}

function toSlug(str: string): string {
  return str
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, "")
    .replace(/\s+/g, "_");
}

function isFieldFilled(values: FormValues, field: string): boolean {
  switch (field) {
    case "title":
      return values.title.trim().length > 0;
    case "identifier":
      return values.identifier.trim().length > 0;
    case "taxonomyId":
      return values.taxonomyId.length > 0;
    case "schemeId":
      return values.schemeId.length > 0;
    case "classIds":
      return values.classIds.length > 0;
    case "sourceId":
      return values.sourceId.length > 0;
    case "targetId":
      return values.targetId.length > 0;
    case "relationshipType":
      return values.relationshipType.length > 0;
    default:
      return false;
  }
}

function contextFieldsForAnother(
  entityType: EntityType,
  values: FormValues,
): Partial<FormValues> {
  switch (entityType) {
    case "scheme":
      return { taxonomyId: values.taxonomyId };
    case "class":
      return { schemeId: values.schemeId, taxonomyId: values.taxonomyId };
    case "individual":
      return { classIds: values.classIds };
    default:
      return {};
  }
}

export interface CreateDrawerProps {
  entityType: EntityType;
  isOpen: boolean;
  onClose: () => void;
  variant?: "full" | "inline";
  initialTaxonomyId?: string;
  initialSchemeId?: string;
  onSuccess?: (entity: { id: string; title?: string }) => void;
}

export function CreateDrawer({
  entityType,
  isOpen,
  onClose,
  variant = "full",
  initialTaxonomyId,
  initialSchemeId,
  onSuccess,
}: CreateDrawerProps) {
  const config = ENTITY_CONFIG[entityType];

  const [values, setValues] = useState<FormValues>(() =>
    defaultValues(initialTaxonomyId, initialSchemeId),
  );
  const [identifierCustomized, setIdentifierCustomized] = useState(false);
  const [touched, setTouched] = useState<Set<string>>(new Set());
  const [submitAttempted, setSubmitAttempted] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [createAnother, setCreateAnother] = useState(false);
  const [successBanner, setSuccessBanner] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // RelationshipBuilder state
  const [relValue, setRelValue] = useState<RelationshipBuilderValue>({
    predicate: "",
  });
  const [sourceQuery, setSourceQuery] = useState("");
  const [targetQuery, setTargetQuery] = useState("");

  const titleRef = useRef<HTMLInputElement>(null);
  const successTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Mutations
  const createTaxonomy = useCreateTaxonomy();
  const createScheme = useCreateScheme();
  const createClass = useCreateClass();
  const createProperty = useCreateProperty();
  const createIndividual = useCreateIndividual();
  const createRelationship = useCreateRelationship();

  // Data for dropdowns
  const { data: taxonomiesData } = useTaxonomies();
  const { data: schemesData } = useSchemes(values.taxonomyId || undefined);
  const { data: classesData } = useClasses(
    values.schemeId ? { concept_scheme_id: values.schemeId } : undefined,
  );
  const { data: allClassesData } = useClasses();
  const { data: propertiesData } = useProperties();

  const taxonomies = taxonomiesData?.items ?? [];
  const schemes = schemesData?.items ?? [];
  const classes = classesData?.items ?? [];
  const allClasses = allClassesData?.items ?? [];
  const properties = propertiesData?.items ?? [];

  // Reset on open
  useEffect(() => {
    if (isOpen) {
      setValues(defaultValues(initialTaxonomyId, initialSchemeId));
      setIdentifierCustomized(false);
      setTouched(new Set());
      setSubmitAttempted(false);
      setSubmitError(null);
      setSuccessBanner(null);
      setRelValue({ predicate: "" });
      setSourceQuery("");
      setTargetQuery("");
      // Focus title after render
      const timer = setTimeout(() => titleRef.current?.focus(), 50);
      return () => clearTimeout(timer);
    }
  }, [isOpen, initialTaxonomyId, initialSchemeId]);

  // Auto-slug: update identifier from title unless customized
  useEffect(() => {
    if (!identifierCustomized && config.idPrefix !== null) {
      const slug = toSlug(values.title);
      const id = slug ? `${config.idPrefix}${slug}` : "";
      setValues((v) => ({ ...v, identifier: id }));
    }
  }, [values.title, identifierCustomized, config.idPrefix]);

  // Keyboard shortcuts
  const handleCreate = useCallback(async () => {
    setSubmitAttempted(true);
    setSubmitError(null);

    const requiredFields = config.requiredFields;
    const incomplete = requiredFields.filter((f) => !isFieldFilled(values, f));
    if (entityType === "relationship") {
      const relIncomplete =
        !relValue.source?.id || !relValue.target?.id || !relValue.predicate;
      if (relIncomplete) return;
    } else if (incomplete.length > 0) {
      return;
    }

    setIsSubmitting(true);
    try {
      let result: { id: string; title?: string };

      if (entityType === "taxonomy") {
        result = await createTaxonomy.mutateAsync({
          title: values.title,
          description: values.description || null,
        });
      } else if (entityType === "scheme") {
        result = await createScheme.mutateAsync({
          taxonomyId: values.taxonomyId,
          data: { title: values.title, description: values.description || null },
        });
      } else if (entityType === "class") {
        result = await createClass.mutateAsync({
          schemeId: values.schemeId,
          data: {
            title: values.title,
            description: values.description || null,
          },
        });
      } else if (entityType === "property") {
        const slug = toSlug(values.title);
        result = await createProperty.mutateAsync({
          identifier: values.identifier || slug,
          title: values.title,
          description: values.description || null,
        });
      } else if (entityType === "individual") {
        result = await createIndividual.mutateAsync({
          class_ids: values.classIds,
          title: values.title,
          description: values.description || null,
        });
      } else {
        result = await createRelationship.mutateAsync({
          source_id: relValue.source!.id,
          target_id: relValue.target!.id,
          relationship_type: relValue.predicate,
        });
      }

      if (createAnother) {
        const retained = contextFieldsForAnother(entityType, values);
        setValues({ ...defaultValues(initialTaxonomyId, initialSchemeId), ...retained });
        setIdentifierCustomized(false);
        setTouched(new Set());
        setSubmitAttempted(false);
        setRelValue({ predicate: "" });
        setSourceQuery("");
        setTargetQuery("");
        const name = "title" in result ? result.title ?? result.id : result.id;
        setSuccessBanner(name);
        if (successTimerRef.current) clearTimeout(successTimerRef.current);
        successTimerRef.current = setTimeout(() => setSuccessBanner(null), 3500);
        setTimeout(() => titleRef.current?.focus(), 50);
      } else {
        onSuccess?.(result);
        onClose();
      }
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Failed to create");
    } finally {
      setIsSubmitting(false);
    }
  }, [
    entityType,
    values,
    relValue,
    createAnother,
    config.requiredFields,
    initialTaxonomyId,
    initialSchemeId,
    createTaxonomy,
    createScheme,
    createClass,
    createProperty,
    createIndividual,
    createRelationship,
    onSuccess,
    onClose,
  ]);

  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        void handleCreate();
      }
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen, handleCreate, onClose]);

  // Clean up timer on unmount
  useEffect(() => {
    return () => {
      if (successTimerRef.current) clearTimeout(successTimerRef.current);
    };
  }, []);

  // Progress calculation
  const isRelationship = entityType === "relationship";
  const requiredFields = config.requiredFields;
  const filledCount = isRelationship
    ? [relValue.source?.id, relValue.target?.id, relValue.predicate].filter(Boolean).length
    : requiredFields.filter((f) => isFieldFilled(values, f)).length;
  const totalRequired = requiredFields.length;
  const progressPct = totalRequired > 0 ? (filledCount / totalRequired) * 100 : 0;
  const isComplete = filledCount === totalRequired;

  const touch = (field: string) => setTouched((t) => new Set([...t, field]));

  const showError = (field: string): boolean =>
    submitAttempted || touched.has(field);

  const fieldError = (field: string): string | undefined => {
    if (!showError(field)) return undefined;
    if (!isFieldFilled(values, field)) return `${config.requirementLabels[field] ?? field} is required`;
    return undefined;
  };

  const relFieldsFilled = isRelationship
    ? {
        sourceId: !!relValue.source?.id,
        targetId: !!relValue.target?.id,
        relationshipType: !!relValue.predicate,
      }
    : {};

  // Entity picker results for RelationshipBuilder
  const classPickerResults = allClasses
    .filter((c) => c.title.toLowerCase().includes(sourceQuery.toLowerCase()))
    .slice(0, 20)
    .map((c) => ({ id: c.id, label: c.title }));

  const targetPickerResults = allClasses
    .filter((c) => c.title.toLowerCase().includes(targetQuery.toLowerCase()))
    .slice(0, 20)
    .map((c) => ({ id: c.id, label: c.title }));

  const predicates = properties.length > 0
    ? properties.map((p) => p.identifier)
    : ["related_to", "contains", "depends_on", "is_used_by"];

  const content = (
    <div className="create-drawer" data-testid="create-drawer">
      {/* Header */}
      <div className="create-drawer__header">
        <div className="create-drawer__eyebrow">
          <Icon name={config.icon as any} size={12} />
          {config.eyebrow}
        </div>
        <div className="create-drawer__title">New {config.title}</div>
        <div className="create-drawer__desc">{config.description}</div>
      </div>

      {/* Progress */}
      <div className="create-drawer__progress">
        <div className="create-drawer__bar-track">
          <div
            className={`create-drawer__bar-fill${isComplete ? " complete" : ""}`}
            style={{ width: `${progressPct}%` }}
          />
        </div>
        <div className="create-drawer__chips">
          {requiredFields.map((f) => {
            const filled = isRelationship
              ? !!relFieldsFilled[f as keyof typeof relFieldsFilled]
              : isFieldFilled(values, f);
            return (
              <span
                key={f}
                className={`create-drawer__chip${filled ? " satisfied" : ""}`}
                aria-label={`${config.requirementLabels[f] ?? f}: ${filled ? "satisfied" : "required"}`}
              >
                {filled ? (
                  <Icon name="check" size={10} />
                ) : (
                  <span className="create-drawer__chip-dot" />
                )}
                {config.requirementLabels[f] ?? f}
              </span>
            );
          })}
          <span className={`create-drawer__readout${isComplete ? " ready" : ""}`}>
            {isComplete ? "ready" : `${filledCount} / ${totalRequired}`}
          </span>
        </div>
      </div>

      {/* Success banner */}
      {successBanner && (
        <div className="create-drawer__success" role="status" data-testid="create-drawer-success">
          <Icon name="check" size={12} /> Created &ldquo;{successBanner}&rdquo;
        </div>
      )}

      {/* Submit error */}
      {submitError && (
        <div className="create-drawer__error" role="alert" data-testid="create-drawer-error">
          {submitError}
        </div>
      )}

      {/* Body */}
      <div className="create-drawer__body canvas-scroll">
        <div className="stack-lg">
          {/* Title + Identifier (shared, not for relationship) */}
          {!isRelationship && (
            <>
              <Field
                label="Title"
                required
                error={fieldError("title")}
                data-testid="create-drawer-title-field"
              >
                <TextInput
                  ref={titleRef as any}
                  type="text"
                  placeholder={`${config.title} name`}
                  value={values.title}
                  onChange={(e) => {
                    setValues((v) => ({ ...v, title: e.target.value }));
                    if (touched.has("title") || submitAttempted) touch("title");
                  }}
                  onBlur={() => touch("title")}
                  error={!!fieldError("title")}
                  data-testid="create-drawer-title-input"
                  autoComplete="off"
                />
              </Field>

              {config.idPrefix !== null && (
                <Field
                  label="Identifier"
                  hint={
                    identifierCustomized ? (
                      <span className="id-hint">
                        custom ·{" "}
                        <button
                          type="button"
                          className="id-relink"
                          onClick={() => {
                            setIdentifierCustomized(false);
                            const slug = toSlug(values.title);
                            setValues((v) => ({
                              ...v,
                              identifier: slug ? `${config.idPrefix}${slug}` : "",
                            }));
                          }}
                          data-testid="create-drawer-relink-btn"
                        >
                          Re-link to title
                        </button>
                      </span>
                    ) : (
                      <span className="id-hint">auto from title</span>
                    )
                  }
                >
                  <TextInput
                    type="text"
                    mono
                    placeholder={`${config.idPrefix}my_identifier`}
                    value={values.identifier}
                    onChange={(e) => {
                      setIdentifierCustomized(true);
                      setValues((v) => ({ ...v, identifier: e.target.value }));
                    }}
                    data-testid="create-drawer-identifier-input"
                    autoComplete="off"
                  />
                </Field>
              )}
            </>
          )}

          {/* Type-specific form body */}
          {entityType === "taxonomy" && (
            <TaxonomyBody values={values} setValues={setValues} touch={touch} />
          )}

          {entityType === "scheme" && (
            <SchemeBody
              values={values}
              setValues={setValues}
              touch={touch}
              showError={showError}
              fieldError={fieldError}
              taxonomies={taxonomies}
            />
          )}

          {entityType === "class" && (
            <ClassBody
              values={values}
              setValues={setValues}
              touch={touch}
              showError={showError}
              fieldError={fieldError}
              schemes={schemes}
              classes={classes}
            />
          )}

          {entityType === "property" && (
            <PropertyBody values={values} setValues={setValues} touch={touch} />
          )}

          {entityType === "individual" && (
            <IndividualBody
              values={values}
              setValues={setValues}
              touch={touch}
              showError={showError}
              fieldError={fieldError}
              allClasses={allClasses}
            />
          )}

          {entityType === "relationship" && (
            <RelationshipBody
              relValue={relValue}
              setRelValue={(v) => {
                setRelValue(v);
                // sync sourceId/targetId for progress tracking
                setValues((fv) => ({
                  ...fv,
                  sourceId: v.source?.id ?? "",
                  targetId: v.target?.id ?? "",
                  relationshipType: v.predicate,
                }));
              }}
              sourceQuery={sourceQuery}
              setSourceQuery={setSourceQuery}
              targetQuery={targetQuery}
              setTargetQuery={setTargetQuery}
              sourceResults={classPickerResults}
              targetResults={targetPickerResults}
              predicates={predicates}
              values={values}
              setValues={setValues}
              submitAttempted={submitAttempted}
              touched={touched}
              touch={touch}
            />
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="create-drawer__footer">
        <label className="create-drawer__another" data-testid="create-drawer-another-label">
          <input
            type="checkbox"
            checked={createAnother}
            onChange={(e) => setCreateAnother(e.target.checked)}
            data-testid="create-drawer-another-checkbox"
          />
          Create another
        </label>
        <Button
          variant="ghost"
          size="sm"
          onClick={onClose}
          data-testid="create-drawer-cancel-btn"
        >
          Cancel
        </Button>
        <Button
          variant="primary"
          size="sm"
          onClick={() => void handleCreate()}
          disabled={isSubmitting}
          aria-disabled={!isComplete}
          data-testid="create-drawer-create-btn"
          title={!isComplete ? "Fill all required fields to create" : undefined}
        >
          Create{" "}
          <kbd className="create-drawer__kbd">⌘↵</kbd>
        </Button>
      </div>
    </div>
  );

  if (variant === "inline") {
    if (!isOpen) return null;
    return <div className="create-drawer-inline" data-testid="create-drawer-inline">{content}</div>;
  }

  if (!isOpen) return null;

  return (
    <div
      className="create-drawer-overlay"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={`Create ${config.title}`}
    >
      <div
        className="create-drawer-panel"
        onClick={(e) => e.stopPropagation()}
        data-testid="create-drawer-panel"
      >
        {content}
      </div>
    </div>
  );
}

// ─── Form body sub-components ────────────────────────────────────────────────

interface BaseBodyProps {
  values: FormValues;
  setValues: React.Dispatch<React.SetStateAction<FormValues>>;
  touch: (field: string) => void;
}

interface WithValidation extends BaseBodyProps {
  showError: (field: string) => boolean;
  fieldError: (field: string) => string | undefined;
}

function TaxonomyBody({ values, setValues, touch }: BaseBodyProps) {
  return (
    <Field label="Description">
      <TextArea
        placeholder="Describe this taxonomy's scope and purpose…"
        value={values.description}
        onChange={(e) => {
          setValues((v) => ({ ...v, description: e.target.value }));
          touch("description");
        }}
        rows={3}
        data-testid="create-drawer-description-input"
      />
    </Field>
  );
}

function SchemeBody({
  values,
  setValues,
  touch,
  showError: _showError,
  fieldError,
  taxonomies,
}: WithValidation & {
  taxonomies: Array<{ id: string; title: string }>;
}) {
  const selectedTaxonomy = taxonomies.find((t) => t.id === values.taxonomyId);

  return (
    <>
      <Field
        label="Taxonomy"
        required
        error={fieldError("taxonomyId")}
        data-testid="create-drawer-taxonomy-field"
      >
        <Select
          value={values.taxonomyId}
          placeholder="Select a taxonomy…"
          onChange={(value) => {
            setValues((v) => ({ ...v, taxonomyId: value }));
            touch("taxonomyId");
          }}
          error={!!fieldError("taxonomyId")}
          data-testid="create-drawer-taxonomy-select"
        >
          {taxonomies.map((t) => (
            <Select.Item key={t.id} value={t.id}>
              {t.title}
            </Select.Item>
          ))}
        </Select>
      </Field>

      {selectedTaxonomy && (
        <div className="create-drawer__domain-pill" data-testid="create-drawer-domain-pill">
          <Icon name="schema" size={11} />
          {selectedTaxonomy.title}
        </div>
      )}

      <Field label="Description">
        <TextArea
          placeholder="Describe the scope of this concept scheme…"
          value={values.description}
          onChange={(e) => setValues((v) => ({ ...v, description: e.target.value }))}
          rows={3}
          data-testid="create-drawer-description-input"
        />
      </Field>
    </>
  );
}

function ClassBody({
  values,
  setValues,
  touch,
  showError: _showError,
  fieldError,
  schemes,
  classes,
}: WithValidation & {
  schemes: Array<{ id: string; title: string; taxonomy_id?: string }>;
  classes: Array<{ id: string; title: string }>;
}) {
  return (
    <>
      <Field
        label="Concept Scheme"
        required
        error={fieldError("schemeId")}
        data-testid="create-drawer-scheme-field"
      >
        <Select
          value={values.schemeId}
          placeholder="Select a concept scheme…"
          onChange={(value) => {
            setValues((v) => ({ ...v, schemeId: value, parentClassId: "" }));
            touch("schemeId");
          }}
          error={!!fieldError("schemeId")}
          data-testid="create-drawer-scheme-select"
        >
          {schemes.map((s) => (
            <Select.Item key={s.id} value={s.id}>
              {s.title}
            </Select.Item>
          ))}
        </Select>
      </Field>

      <Field label="Parent class" hint="optional">
        <Select
          value={values.parentClassId}
          placeholder="None (top-level class)"
          onChange={(value) => setValues((v) => ({ ...v, parentClassId: value }))}
          disabled={!values.schemeId}
          data-testid="create-drawer-parent-class-select"
        >
          {classes.map((c) => (
            <Select.Item key={c.id} value={c.id}>
              {c.title}
            </Select.Item>
          ))}
        </Select>
      </Field>

      <Field label="Description">
        <TextArea
          placeholder="Describe what this class represents…"
          value={values.description}
          onChange={(e) => setValues((v) => ({ ...v, description: e.target.value }))}
          rows={3}
          data-testid="create-drawer-description-input"
        />
      </Field>
    </>
  );
}

function PropertyBody({ values, setValues, touch: _touch }: BaseBodyProps) {
  return (
    <>
      <Field label="Description">
        <TextArea
          placeholder="Describe this property's meaning and usage…"
          value={values.description}
          onChange={(e) => setValues((v) => ({ ...v, description: e.target.value }))}
          rows={3}
          data-testid="create-drawer-description-input"
        />
      </Field>

      <Field label="Relevance">
        <SegmentedControl
          value={values.relevance}
          onChange={(v) => setValues((vals) => ({ ...vals, relevance: v as string }))}
          options={[
            { value: "relevant", label: "Relevant" },
            { value: "optional", label: "Optional" },
            { value: "excluded", label: "Excluded" },
          ]}
          data-testid="create-drawer-relevance-control"
        />
      </Field>
    </>
  );
}

function IndividualBody({
  values,
  setValues,
  touch,
  showError: _showError,
  fieldError,
  allClasses,
}: WithValidation & { allClasses: Array<{ id: string; title: string }> }) {
  const toggleClass = (classId: string) => {
    setValues((v) => ({
      ...v,
      classIds: v.classIds.includes(classId)
        ? v.classIds.filter((id) => id !== classId)
        : [...v.classIds, classId],
    }));
    touch("classIds");
  };

  return (
    <>
      <Field
        label="Classes"
        required
        error={fieldError("classIds")}
        data-testid="create-drawer-classes-field"
      >
        <div
          className={`class-multi-select${fieldError("classIds") ? " error" : ""}`}
          role="group"
          aria-label="Select classes"
          data-testid="create-drawer-classes-list"
        >
          {allClasses.length === 0 && (
            <div className="class-option-empty">No classes available</div>
          )}
          {allClasses.map((c) => (
            <label key={c.id} className="class-option">
              <input
                type="checkbox"
                checked={values.classIds.includes(c.id)}
                onChange={() => toggleClass(c.id)}
                data-testid={`create-drawer-class-${c.id}`}
              />
              {c.title}
            </label>
          ))}
        </div>
      </Field>

      <Field label="Description">
        <TextArea
          placeholder="Describe this individual…"
          value={values.description}
          onChange={(e) => setValues((v) => ({ ...v, description: e.target.value }))}
          rows={3}
          data-testid="create-drawer-description-input"
        />
      </Field>

      <Field label="Source text" hint="optional">
        <TextArea
          placeholder="Paste the source passage that mentions this individual…"
          value={values.sourceText}
          onChange={(e) => setValues((v) => ({ ...v, sourceText: e.target.value }))}
          rows={2}
          data-testid="create-drawer-source-text-input"
        />
      </Field>

      <div className="ce-param" data-testid="create-drawer-confidence-field">
        <div className="ce-param__top">
          <span className="ce-param__label">Confidence</span>
          <span className="ce-param__val">{(values.confidence * 100).toFixed(0)}%</span>
        </div>
        <input
          type="range"
          className="ce-range"
          min={0}
          max={1}
          step={0.01}
          value={values.confidence}
          onChange={(e) => setValues((v) => ({ ...v, confidence: parseFloat(e.target.value) }))}
          data-testid="create-drawer-confidence-input"
          aria-label="Confidence"
        />
      </div>
    </>
  );
}

interface RelationshipBodyProps {
  relValue: RelationshipBuilderValue;
  setRelValue: (v: RelationshipBuilderValue) => void;
  sourceQuery: string;
  setSourceQuery: (q: string) => void;
  targetQuery: string;
  setTargetQuery: (q: string) => void;
  sourceResults: Array<{ id: string; label: string }>;
  targetResults: Array<{ id: string; label: string }>;
  predicates: string[];
  values: FormValues;
  setValues: React.Dispatch<React.SetStateAction<FormValues>>;
  submitAttempted: boolean;
  touched: Set<string>;
  touch: (field: string) => void;
}

function RelationshipBody({
  relValue,
  setRelValue,
  sourceQuery,
  setSourceQuery,
  targetQuery,
  setTargetQuery,
  sourceResults,
  targetResults,
  predicates,
  values,
  setValues,
  submitAttempted,
  touched,
  touch,
}: RelationshipBodyProps) {
  const showFieldError = (field: string) => submitAttempted || touched.has(field);

  return (
    <>
      <RelationshipBuilder
        value={relValue}
        onChange={(v) => {
          setRelValue(v);
          touch("sourceId");
          touch("targetId");
          touch("relationshipType");
        }}
        sourceQuery={sourceQuery}
        onSourceQueryChange={setSourceQuery}
        targetQuery={targetQuery}
        onTargetQueryChange={setTargetQuery}
        sourceResults={sourceResults}
        targetResults={targetResults}
        onSourceClear={() => {
          setSourceQuery("");
          setRelValue({ ...relValue, source: undefined });
        }}
        onTargetClear={() => {
          setTargetQuery("");
          setRelValue({ ...relValue, target: undefined });
        }}
        predicates={predicates.length > 0 ? predicates : undefined}
        data-testid="create-drawer-relationship-builder"
      />

      {submitAttempted && !relValue.source?.id && (
        <div className="field-error" role="alert">Source is required</div>
      )}
      {submitAttempted && !relValue.target?.id && (
        <div className="field-error" role="alert">Target is required</div>
      )}
      {submitAttempted && !relValue.predicate && (
        <div className="field-error" role="alert">Predicate is required</div>
      )}

      <Field label="Source text" hint="optional">
        <TextArea
          placeholder="Paste the source passage that supports this relationship…"
          value={values.sourceText}
          onChange={(e) => setValues((v) => ({ ...v, sourceText: e.target.value }))}
          rows={2}
          data-testid="create-drawer-source-text-input"
        />
      </Field>

      <div className="ce-param" data-testid="create-drawer-confidence-field">
        <div className="ce-param__top">
          <span className="ce-param__label">Confidence</span>
          <span className="ce-param__val">{(values.confidence * 100).toFixed(0)}%</span>
        </div>
        <input
          type="range"
          className="ce-range"
          min={0}
          max={1}
          step={0.01}
          value={values.confidence}
          onChange={(e) =>
            setValues((v) => ({ ...v, confidence: parseFloat(e.target.value) }))
          }
          data-testid="create-drawer-confidence-input"
          aria-label="Confidence"
        />
      </div>
    </>
  );
}
