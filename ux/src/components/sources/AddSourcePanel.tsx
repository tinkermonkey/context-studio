import { useState, type DragEvent } from "react";
import {
  Button,
  Field,
  Icon,
  SegmentedControl,
  TextArea,
  TextInput,
} from "@tinkermonkey/heimdall-ui";
import { ApiError } from "@/api/client/interceptors";
import { useAddSource } from "@/api/hooks/sources/useAddSource";
import type { NewSource } from "@/api/services/sources";
import { useToasts } from "@/components/ui/Toast";
import { sourcesCopy } from "./copy";
import type { components } from "@/api/types";

type DatasetResponse = components["schemas"]["DatasetResponse"];
type Mode = "file" | "url" | "text";

const copy = sourcesCopy.add;
const ACCEPT = ".pdf,.md,.markdown,.html,.htm,.txt";

interface AddSourcePanelProps {
  taxonomyId: string;
  /** The dataset new sources go to; undefined when the user must choose one here. */
  datasetId?: string;
  /** The taxonomy's datasets, offered when `datasetId` is undefined and there are several. */
  datasets: DatasetResponse[];
}

interface Errors {
  url?: string;
  title?: string;
  text?: string;
}

/** Add a source three ways: drop or choose a file, fetch a web page, or paste text. */
export function AddSourcePanel({ taxonomyId, datasetId, datasets }: AddSourcePanelProps) {
  const { toast } = useToasts();
  const addSource = useAddSource();
  const [mode, setMode] = useState<Mode>("file");
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [errors, setErrors] = useState<Errors>({});
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState<string | null>(null);
  const [chosenDataset, setChosenDataset] = useState<string>("");

  // With several datasets and none chosen above, new sources need one chosen here.
  const mustChooseDataset = !datasetId && datasets.length > 1;
  const dataset = datasetId ?? (mustChooseDataset ? chosenDataset || datasets[0]?.id : undefined);

  const add = (source: NewSource, onAdded?: () => void) => {
    addSource.mutate(
      { scope: { taxonomy_id: taxonomyId, dataset }, source },
      {
        onSuccess: (added) => {
          onAdded?.();
          toast(
            "success",
            copy.added(added.title),
            added.status === "fetching" ? copy.fetching : undefined,
          );
        },
        onError: (err) =>
          toast(
            "error",
            copy.failed,
            err instanceof ApiError && err.detail ? err.detail : undefined,
          ),
        onSettled: () => setUploading(null),
      },
    );
  };

  const upload = (file: File | undefined) => {
    if (!file) return;
    setUploading(file.name);
    add({ kind: "file", file });
  };

  const onDrop = (e: DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    setDragging(false);
    upload(e.dataTransfer.files?.[0]);
  };

  const fetchUrl = () => {
    const trimmed = url.trim();
    const error = !trimmed
      ? copy.urlRequired
      : /^https?:\/\/\S+$/i.test(trimmed)
        ? undefined
        : copy.urlInvalid;
    setErrors({ url: error });
    if (error) return;
    add({ kind: "url", url: trimmed }, () => setUrl(""));
  };

  const addText = () => {
    const next: Errors = {
      title: title.trim() ? undefined : copy.titleRequired,
      text: text.trim() ? undefined : copy.textRequired,
    };
    setErrors(next);
    if (next.title || next.text) return;
    add({ kind: "text", title: title.trim(), text }, () => {
      setTitle("");
      setText("");
    });
  };

  return (
    <section className="add-source" aria-label="Add a source" data-testid="add-source-panel">
      <div className="add-source__head">
        <span className="sources-eyebrow">{copy.heading}</span>
        <SegmentedControl
          value={mode}
          onChange={(v) => {
            setMode(v as Mode);
            setErrors({});
          }}
          options={[
            { value: "file", label: copy.modes.file },
            { value: "url", label: copy.modes.url },
            { value: "text", label: copy.modes.text },
          ]}
          aria-label={copy.modeLabel}
          data-testid="add-source-mode"
        />
      </div>

      {mustChooseDataset && (
        <Field label={copy.datasetLabel}>
          <SegmentedControl
            value={dataset ?? ""}
            onChange={(v) => setChosenDataset(String(v))}
            options={datasets.map((d) => ({ value: d.id, label: d.identifier }))}
            aria-label={copy.datasetLabel}
            data-testid="add-source-dataset"
          />
        </Field>
      )}

      {mode === "file" && (
        <label
          htmlFor="source-file"
          className={dragging ? "add-source__drop add-source__drop--over" : "add-source__drop"}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          aria-busy={!!uploading}
          data-testid="add-source-dropzone"
        >
          <Icon name="file" size={22} aria-hidden="true" />
          <span className="add-source__drop-title">
            {uploading ? copy.uploading(uploading) : copy.dropTitle}
          </span>
          <span className="add-source__drop-hint">{copy.dropHint}</span>
          <input
            id="source-file"
            type="file"
            accept={ACCEPT}
            className="add-source__file-input"
            disabled={!!uploading}
            onChange={(e) => {
              upload(e.target.files?.[0]);
              e.target.value = "";
            }}
            data-testid="add-source-file-input"
          />
        </label>
      )}

      {mode === "url" && (
        <div className="add-source__row">
          <Field
            label={copy.urlLabel}
            htmlFor="source-url"
            hint={copy.urlHint}
            error={errors.url}
            errorId="source-url-error"
            className="add-source__grow"
          >
            <TextInput
              id="source-url"
              mono
              placeholder="https://"
              value={url}
              onChange={(e) => {
                setUrl(e.target.value);
                setErrors({});
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") fetchUrl();
              }}
              error={!!errors.url}
              aria-invalid={!!errors.url}
              aria-describedby={errors.url ? "source-url-error" : undefined}
              data-testid="add-source-url-input"
            />
          </Field>
          <Button
            variant="primary"
            size="sm"
            onClick={fetchUrl}
            disabled={addSource.isPending}
            data-testid="add-source-fetch-button"
          >
            {copy.fetchButton}
          </Button>
        </div>
      )}

      {mode === "text" && (
        <div className="add-source__stack">
          <Field
            label={copy.titleLabel}
            htmlFor="source-title"
            error={errors.title}
            errorId="source-title-error"
          >
            <TextInput
              id="source-title"
              placeholder={copy.titlePlaceholder}
              value={title}
              onChange={(e) => {
                setTitle(e.target.value);
                setErrors((prev) => ({ ...prev, title: undefined }));
              }}
              error={!!errors.title}
              aria-invalid={!!errors.title}
              aria-describedby={errors.title ? "source-title-error" : undefined}
              data-testid="add-source-title-input"
            />
          </Field>
          <Field
            label={copy.textLabel}
            htmlFor="source-text"
            hint={copy.textHint}
            error={errors.text}
            errorId="source-text-error"
          >
            <TextArea
              id="source-text"
              rows={4}
              placeholder={copy.textPlaceholder}
              value={text}
              onChange={(e) => {
                setText(e.target.value);
                setErrors((prev) => ({ ...prev, text: undefined }));
              }}
              error={!!errors.text}
              aria-invalid={!!errors.text}
              aria-describedby={errors.text ? "source-text-error" : undefined}
              data-testid="add-source-text-input"
            />
          </Field>
          <div>
            <Button
              variant="primary"
              size="sm"
              onClick={addText}
              disabled={addSource.isPending}
              data-testid="add-source-submit"
            >
              {copy.addButton}
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}
