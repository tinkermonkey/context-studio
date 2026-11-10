import { useEffect, useState } from "react";
import { Button, Field, Modal, Select, TextInput } from "@tinkermonkey/heimdall-ui";
import { ApiError } from "@/api/client/interceptors";
import { useCreateDataset } from "@/api/hooks/ontology/useDatasets";
import { datasetsCopy } from "./copy";
import type { components } from "@/api/types";

type TaxonomyResponse = components["schemas"]["TaxonomyResponse"];
type DatasetResponse = components["schemas"]["DatasetResponse"];

const IDENTIFIER_PATTERN = /^[a-z][a-z0-9_-]*$/;
const copy = datasetsCopy.create;

/** A dataset identifier from a title: lowercase words joined by "-", starting with a letter. */
export function datasetSlug(title: string): string {
  return title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^[^a-z]+/, "")
    .replace(/-+$/, "");
}

interface FieldErrors {
  taxonomy?: string;
  title?: string;
  identifier?: string;
}

interface CreateDatasetModalProps {
  isOpen: boolean;
  onClose: () => void;
  taxonomies: TaxonomyResponse[];
  /** Taxonomy chosen when the modal opens (the page's taxonomy filter). */
  initialTaxonomyId?: string;
  onCreated: (dataset: DatasetResponse) => void;
}

/** Create a dataset over one taxonomy's schema: taxonomy, title and identifier slug. */
export function CreateDatasetModal({
  isOpen,
  onClose,
  taxonomies,
  initialTaxonomyId,
  onCreated,
}: CreateDatasetModalProps) {
  const createDataset = useCreateDataset();
  const [taxonomyId, setTaxonomyId] = useState("");
  const [title, setTitle] = useState("");
  const [identifier, setIdentifier] = useState("");
  const [identifierEdited, setIdentifierEdited] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitError, setSubmitError] = useState<string>();

  useEffect(() => {
    if (!isOpen) return;
    setTaxonomyId(initialTaxonomyId ?? (taxonomies.length === 1 ? taxonomies[0].id : ""));
    setTitle("");
    setIdentifier("");
    setIdentifierEdited(false);
    setErrors({});
    setSubmitError(undefined);
    // Reset only when the modal opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  const validate = (): FieldErrors => {
    const next: FieldErrors = {};
    if (!taxonomyId) next.taxonomy = copy.taxonomyRequired;
    if (!title.trim()) next.title = copy.titleRequired;
    if (!identifier) next.identifier = copy.identifierRequired;
    else if (!IDENTIFIER_PATTERN.test(identifier)) next.identifier = copy.identifierInvalid;
    return next;
  };

  const handleSubmit = async () => {
    const found = validate();
    setErrors(found);
    setSubmitError(undefined);
    if (Object.keys(found).length > 0) return;
    try {
      const created = await createDataset.mutateAsync({
        taxonomy_id: taxonomyId,
        identifier,
        title: title.trim(),
      });
      onCreated(created);
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setErrors({ identifier: copy.duplicateIdentifier });
      } else {
        setSubmitError(error instanceof ApiError && error.detail ? error.detail : copy.failed);
      }
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={copy.title}
      subtitle={copy.subtitle}
      data-testid="dataset-create-modal"
      footer={
        <div className="form-actions">
          <Button variant="ghost" onClick={onClose}>
            {copy.cancel}
          </Button>
          <Button
            variant="primary"
            onClick={handleSubmit}
            disabled={createDataset.isPending}
            aria-busy={createDataset.isPending}
            data-testid="dataset-submit-button"
          >
            {copy.submit}
          </Button>
        </div>
      }
    >
      <form
        className="stack-lg"
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          void handleSubmit();
        }}
      >
        <Field
          label={copy.taxonomyLabel}
          htmlFor="dataset-taxonomy"
          required
          error={errors.taxonomy}
        >
          <Select
            id="dataset-taxonomy"
            value={taxonomyId}
            onChange={(value) => {
              setTaxonomyId(value);
              setErrors((e) => ({ ...e, taxonomy: undefined, identifier: undefined }));
            }}
            placeholder={copy.taxonomyPlaceholder}
            error={!!errors.taxonomy}
            data-testid="dataset-taxonomy-select"
          >
            {taxonomies.map((t) => (
              <Select.Item key={t.id} value={t.id}>
                {t.title} · {t.identifier}
              </Select.Item>
            ))}
          </Select>
        </Field>
        <Field label={copy.titleLabel} htmlFor="dataset-title" required error={errors.title}>
          <TextInput
            id="dataset-title"
            value={title}
            onChange={(e) => {
              setTitle(e.target.value);
              if (!identifierEdited) setIdentifier(datasetSlug(e.target.value));
              setErrors((prev) => ({
                ...prev,
                title: undefined,
                ...(identifierEdited ? {} : { identifier: undefined }),
              }));
            }}
            error={!!errors.title}
            data-testid="dataset-title-input"
          />
        </Field>
        <Field
          label={copy.identifierLabel}
          htmlFor="dataset-identifier"
          hint={copy.identifierHint}
          required
          error={errors.identifier}
        >
          <TextInput
            id="dataset-identifier"
            mono
            value={identifier}
            onChange={(e) => {
              setIdentifier(e.target.value);
              setIdentifierEdited(true);
              setErrors((prev) => ({ ...prev, identifier: undefined }));
            }}
            error={!!errors.identifier}
            data-testid="dataset-identifier-input"
          />
        </Field>
        {submitError && (
          <p className="form-error" role="alert" data-testid="dataset-create-error">
            {submitError}
          </p>
        )}
      </form>
    </Modal>
  );
}
