import {
  createContext,
  useContext,
  useId,
  type FocusEvent,
  type MouseEvent,
  type ReactNode,
} from "react";
import type { HoverOverlay } from "../HoverOverlay";
import type { ReviewSchema } from "./reviewSchema";

/**
 * The Review page's pills: a class, an individual or a relationship's
 * predicate, each a small tag that shows more about it in the app's hover
 * overlay (beside the inspector) while hovered or focused. An individual or
 * relationship of the proposal is also a link that opens it (?selected=...).
 */

/** How to open an operation of the proposal: a real href, and a plain click selecting it. */
export interface OperationLink {
  href: string;
  onClick: (event: MouseEvent<HTMLAnchorElement>) => void;
}

export interface ReviewPillsValue {
  schema: ReviewSchema;
  overlay: HoverOverlay;
  link: (operationId: string) => OperationLink;
}

const ReviewPillsContext = createContext<ReviewPillsValue | null>(null);

export const ReviewPillsProvider = ReviewPillsContext.Provider;

function usePills(): ReviewPillsValue {
  const value = useContext(ReviewPillsContext);
  if (!value) throw new Error("Review pills need a ReviewPillsProvider");
  return value;
}

/** How many relationship types an overlay lists before "and N more". */
const TYPES_LISTED = 8;

function TypeList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  const unique = [...new Set(items)];
  return (
    <div className="review-card__section">
      <span className="review-card__eyebrow">{`${title} · ${unique.length}`}</span>
      <ul className="review-card__list">
        {unique.slice(0, TYPES_LISTED).map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      {unique.length > TYPES_LISTED && (
        <span className="review-card__more">and {unique.length - TYPES_LISTED} more</span>
      )}
    </div>
  );
}

/** A class's overlay: its definition, layer, and the relationships the schema allows from and to it. */
export function ClassCard({ classId, schema }: { classId?: string; schema: ReviewSchema }) {
  const cls = schema.classOf(classId);
  const from = schema
    .typesFrom(classId)
    .map((p) => `${schema.predicateLabel(p.id)} → ${schema.classLabel(p.range_class_id)}`);
  const to = schema
    .typesTo(classId)
    .map((p) => `${schema.classLabel(p.domain_class_id)} → ${schema.predicateLabel(p.id)}`);
  const layer = schema.layerOf(classId);
  return (
    <>
      <span className="definition-overlay__term">{schema.classLabel(classId)}</span>
      {cls && (
        <span className="review-card__sub">{[cls.title, layer].filter(Boolean).join(" · ")}</span>
      )}
      <p className="definition-overlay__text review-card__clamp">
        {cls?.description || "No definition yet."}
      </p>
      <TypeList title="Relationships from it" items={from} />
      <TypeList title="Relationships to it" items={to} />
    </>
  );
}

/** A relationship type's overlay: what its predicate means, and the classes it joins. */
export function PredicateCard({
  propertyId,
  schema,
}: {
  propertyId?: string;
  schema: ReviewSchema;
}) {
  const property = schema.property(propertyId);
  return (
    <>
      <span className="definition-overlay__term">{schema.predicateLabel(propertyId)}</span>
      {property && <span className="review-card__sub">{property.title}</span>}
      <p className="definition-overlay__text review-card__clamp">
        {schema.predicateDefinition(propertyId) ?? "No definition yet."}
      </p>
      {property && (
        <div className="review-card__section">
          <span className="review-card__eyebrow">Allowed</span>
          <span className="review-card__line">
            {schema.classLabel(property.domain_class_id) || "any"} →{" "}
            {schema.classLabel(property.range_class_id) || "any"}
          </span>
        </div>
      )}
    </>
  );
}

/** An individual's overlay: its class and what that means, and where it stands. */
function IndividualCard({
  title,
  classId,
  status,
  schema,
}: {
  title: string;
  classId?: string;
  status?: string;
  schema: ReviewSchema;
}) {
  const cls = schema.classOf(classId);
  return (
    <>
      <span className="definition-overlay__term">{title}</span>
      <span className="review-card__sub">
        {[schema.classLabel(classId), status].filter(Boolean).join(" · ")}
      </span>
      {cls?.description && (
        <p className="definition-overlay__text review-card__clamp review-card__clamp--short">
          {cls.description}
        </p>
      )}
    </>
  );
}

interface PillProps {
  kind: "class" | "individual" | "predicate";
  label: string;
  card: () => ReactNode;
  /** An operation of the proposal: the pill is a link that opens it. */
  operationId?: string;
  size?: "md" | "lg";
  /** Extra classes, e.g. a verdict tint. */
  className?: string;
  "aria-label"?: string;
  "data-testid"?: string;
}

/** A pill with a hover overlay: a link to an operation, else a button that only explains. */
function Pill({
  kind,
  label,
  card,
  operationId,
  size = "md",
  className,
  "aria-label": ariaLabel,
  "data-testid": testId,
}: PillProps) {
  const { overlay, link } = usePills();
  const overlayId = useId();
  const show = (event: MouseEvent<HTMLElement> | FocusEvent<HTMLElement>) =>
    overlay.show(overlayId, card(), event.currentTarget, "review-pill-overlay");
  const handlers = {
    onMouseEnter: show,
    onFocus: show,
    onMouseLeave: () => overlay.hide(overlayId),
    onBlur: () => overlay.hide(overlayId),
    "aria-describedby": overlay.openId === overlayId ? overlayId : undefined,
    "aria-label": ariaLabel,
    "data-testid": testId,
    "data-pill": kind,
    className: ["review-pill", `review-pill--${kind}`, `review-pill--${size}`, className]
      .filter(Boolean)
      .join(" "),
  };
  const text = <span className="review-pill__text">{label}</span>;
  if (operationId) {
    const { href, onClick } = link(operationId);
    return (
      <a {...handlers} href={href} onClick={onClick}>
        {text}
      </a>
    );
  }
  return (
    <button type="button" {...handlers}>
      {text}
    </button>
  );
}

/** A class as a pill; hover shows its definition and the relationships it allows. */
export function ClassPill({
  classId,
  size,
  "data-testid": testId,
}: {
  classId?: string;
  size?: "md" | "lg";
  "data-testid"?: string;
}) {
  const { schema } = usePills();
  const label = schema.classLabel(classId);
  return (
    <Pill
      kind="class"
      size={size}
      label={label}
      aria-label={`Class ${label}`}
      card={() => <ClassCard classId={classId} schema={schema} />}
      data-testid={testId}
    />
  );
}

/** An individual as a pill, linking to its operation when it is in the proposal. */
export function IndividualPill({
  title,
  classId,
  status,
  operationId,
  "data-testid": testId,
}: {
  title: string;
  classId?: string;
  /** Where it stands: a verdict, or "in the workspace". */
  status?: string;
  operationId?: string;
  "data-testid"?: string;
}) {
  const { schema } = usePills();
  return (
    <Pill
      kind="individual"
      label={title}
      operationId={operationId}
      aria-label={operationId ? `Open ${title}` : title}
      card={() => (
        <IndividualCard title={title} classId={classId} status={status} schema={schema} />
      )}
      data-testid={testId}
    />
  );
}

/** A relationship's predicate as a pill, linking to the relationship when given. */
export function PredicatePill({
  propertyId,
  operationId,
  "data-testid": testId,
}: {
  propertyId?: string;
  /** The relationship operation the pill opens. */
  operationId?: string;
  "data-testid"?: string;
}) {
  const { schema } = usePills();
  const label = schema.predicateLabel(propertyId);
  return (
    <Pill
      kind="predicate"
      label={label}
      operationId={operationId}
      aria-label={operationId ? `Open relationship ${label}` : `Predicate ${label}`}
      card={() => <PredicateCard propertyId={propertyId} schema={schema} />}
      data-testid={testId}
    />
  );
}
