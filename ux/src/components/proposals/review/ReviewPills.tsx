import {
  createContext,
  useContext,
  useId,
  type FocusEvent,
  type MouseEvent,
  type ReactNode,
} from "react";
import { ArrowDown, ArrowRight, Info } from "lucide-react";
import { Chip } from "@tinkermonkey/heimdall-ui";
import { entityPath } from "@/lib/entityPaths";
import type { HoverOverlay } from "../HoverOverlay";
import { VERDICT_CHIP, type Verdict } from "./reviewModel";
import type { ReviewSchema } from "./reviewSchema";

/**
 * The review page's three kinds, the same everywhere on the page, each with a
 * hover card in the app's hover overlay (beside the inspector):
 *
 * - an individual: plain bold text with a dot and a dotted underline, not a
 *   pill (it is the thing being reviewed); a link that selects it;
 * - a class: a small violet tag, square-cornered, monospace, with a diamond;
 * - a predicate: a round cyan pill, monospace, with an arrow for its direction.
 *
 * Inside a link (a relationship card) they render as static tags without a
 * hover, since a link can't hold another control.
 */

/** How to open an operation of the proposal: a real href, and a plain click selecting it. */
/** A plain left click selects in place; a modified one is left to the browser (new tab). */
export function plainClick(event: MouseEvent): boolean {
  return !(event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0);
}

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

/** How to open an operation of the proposal (a link's href and click). */
export function useOperationLink(): (operationId: string) => OperationLink {
  return usePills().link;
}

/** How many relationship types a class card lists in each direction before "n more". */
const TYPES_LISTED = 4;
/** How much of an individual's evidence its card quotes. */
const QUOTE_CHARS = 110;

/** The class diamond. */
export function Diamond({ size = 9 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 10 10" aria-hidden="true">
      <path d="M5 0.8 9.2 5 5 9.2 0.8 5Z" fill="none" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  );
}

/** An individual's dot. */
function Dot() {
  return (
    <svg className="review-ind__dot" width="8" height="8" viewBox="0 0 8 8" aria-hidden="true">
      <circle cx="4" cy="4" r="4" fill="currentColor" />
    </svg>
  );
}

function TypeLines({
  title,
  lines,
}: {
  title: string;
  lines: { predicate: string; other: string; into: boolean }[];
}) {
  const unique = lines.filter(
    (l, i) => lines.findIndex((x) => x.predicate === l.predicate && x.other === l.other) === i,
  );
  return (
    <>
      <span className="review-card__eyebrow">{title}</span>
      {unique.length === 0 ? (
        <span className="review-card__line review-card__muted">None in the schema</span>
      ) : (
        <>
          {unique.slice(0, TYPES_LISTED).map((l) => (
            <span key={`${l.predicate}-${l.other}`} className="review-card__line">
              {l.into && <span className="review-card__class">{l.other} </span>}
              <span className="review-card__predicate">{l.predicate} →</span>
              {!l.into && <span className="review-card__class"> {l.other}</span>}
            </span>
          ))}
          {unique.length > TYPES_LISTED && (
            <span className="review-card__line review-card__muted">
              and {unique.length - TYPES_LISTED} more
            </span>
          )}
        </>
      )}
    </>
  );
}

/**
 * A class's card: its name, what it means, the relationships the schema
 * allows from it and into it, and a link to the class.
 */
export function ClassCard({ classId, schema }: { classId?: string; schema: ReviewSchema }) {
  const cls = schema.classOf(classId);
  const from = schema.typesFrom(classId).map((p) => ({
    predicate: schema.predicateLabel(p.id),
    other: schema.classLabel(p.range_class_id),
    into: false,
  }));
  const into = schema.typesTo(classId).map((p) => ({
    predicate: schema.predicateLabel(p.id),
    other: schema.classLabel(p.domain_class_id),
    into: true,
  }));
  return (
    <div className="review-card">
      <span className="review-card__name review-card__name--class">
        {schema.classLabel(classId)}
      </span>
      {cls && schema.layerOf(classId) && (
        <span className="review-card__muted">
          {[cls.title, schema.layerOf(classId)].filter(Boolean).join(" · ")}
        </span>
      )}
      <span className="review-card__text">{cls?.description || "No definition yet."}</span>
      <TypeLines title="ALLOWED FROM IT" lines={from} />
      <TypeLines title="ALLOWED INTO IT" lines={into} />
      {classId && cls && (
        <a className="review-card__link" href={entityPath("class", classId)}>
          Open the class
        </a>
      )}
    </div>
  );
}

/** A relationship type's card: what its predicate means, and the classes it joins. */
export function PredicateCard({
  propertyId,
  schema,
}: {
  propertyId?: string;
  schema: ReviewSchema;
}) {
  const property = schema.property(propertyId);
  return (
    <div className="review-card">
      <span className="review-card__name review-card__name--predicate">
        {schema.predicateLabel(propertyId)}
      </span>
      <span className="review-card__text">
        {schema.predicateDefinition(propertyId) ?? "No definition yet."}
      </span>
      {property && (
        <span className="review-card__line">
          From{" "}
          <span className="review-card__class">
            {property.domain_class_id ? schema.classLabel(property.domain_class_id) : "any class"}
          </span>{" "}
          to{" "}
          <span className="review-card__class">
            {property.range_class_id ? schema.classLabel(property.range_class_id) : "any class"}
          </span>
        </span>
      )}
    </div>
  );
}

/** An individual's card: its title and decision, its class, its evidence, its relationships. */
export function IndividualCard({
  title,
  classId,
  verdict,
  status,
  quote,
  relationships,
}: {
  title: string;
  classId?: string;
  verdict?: Verdict;
  status?: string;
  quote?: string;
  relationships?: number;
}) {
  const snippet =
    quote && (quote.length > QUOTE_CHARS ? `${quote.slice(0, QUOTE_CHARS).trimEnd()}…` : quote);
  return (
    <div className="review-card">
      <span className="review-card__head">
        <span className="review-card__name">{title}</span>
        {verdict && status ? (
          <Chip variant={VERDICT_CHIP[verdict]}>{status}</Chip>
        ) : (
          status && <span className="review-card__muted">{status}</span>
        )}
      </span>
      {classId && <ClassTag classId={classId} />}
      {snippet && <span className="review-card__text">“{snippet}”</span>}
      {relationships !== undefined && (
        <span className="review-card__muted">
          {relationships} {relationships === 1 ? "relationship" : "relationships"} in this proposal
        </span>
      )}
    </div>
  );
}

/** Hover and focus handlers that show `card` in the overlay. */
function useHover(card: () => ReactNode, testId = "review-pill-overlay") {
  const { overlay } = usePills();
  const overlayId = useId();
  const show = (event: MouseEvent<HTMLElement> | FocusEvent<HTMLElement>) =>
    overlay.show(overlayId, card(), event.currentTarget, testId);
  return {
    onMouseEnter: show,
    onFocus: show,
    onMouseLeave: () => overlay.hide(overlayId),
    onBlur: () => overlay.hide(overlayId),
    "aria-describedby": overlay.openId === overlayId ? overlayId : undefined,
  };
}

function classes(...names: (string | false | undefined)[]) {
  return names.filter(Boolean).join(" ");
}

/**
 * A class: a small violet tag with a diamond (larger under an individual's
 * title). Hover shows its definition and the relationships it allows.
 */
export function ClassPill({
  classId,
  size = "md",
  "data-testid": testId,
}: {
  classId?: string;
  size?: "md" | "lg";
  "data-testid"?: string;
}) {
  const { schema } = usePills();
  const label = schema.classLabel(classId);
  const hover = useHover(() => <ClassCard classId={classId} schema={schema} />);
  return (
    <button
      type="button"
      {...hover}
      className={classes("review-pill", "review-pill--class", `review-pill--${size}`)}
      aria-label={`Class ${label}`}
      data-pill="class"
      data-testid={testId}
    >
      <span className="review-pill__icon">
        <Diamond size={size === "lg" ? 11 : 9} />
      </span>
      <span className="review-pill__text">{label}</span>
    </button>
  );
}

/** A class as a static tag (inside a link, where a hover control can't go). */
export function ClassTag({ classId, children }: { classId?: string; children?: ReactNode }) {
  const { schema } = usePills();
  return (
    <span className="review-pill review-pill--class review-pill--md" data-pill="class">
      <span className="review-pill__icon">
        <Diamond />
      </span>
      <span className="review-pill__text">{schema.classLabel(classId)}</span>
      {children}
    </span>
  );
}

/**
 * An individual: plain bold text with a dot and a dotted underline, a link
 * that selects its element when it is in the proposal. Hover shows its
 * decision, class, evidence and relationships.
 */
export function IndividualPill({
  title,
  classId,
  status,
  verdict,
  quote,
  relationships,
  operationId,
  "data-testid": testId,
}: {
  title: string;
  classId?: string;
  /** Where it stands: a verdict's label, or "in the workspace". */
  status?: string;
  verdict?: Verdict;
  /** A passage of its evidence, for the card. */
  quote?: string;
  /** How many relationships of the proposal it is an end of. */
  relationships?: number;
  operationId?: string;
  "data-testid"?: string;
}) {
  const { link } = usePills();
  const hover = useHover(() => (
    <IndividualCard
      title={title}
      classId={classId}
      verdict={verdict}
      status={status}
      quote={quote}
      relationships={relationships}
    />
  ));
  const props = {
    ...hover,
    className: "review-pill review-pill--individual",
    "data-pill": "individual",
    "data-testid": testId,
  };
  const content = (
    <>
      <Dot />
      <span className="review-pill__text">{title}</span>
    </>
  );
  if (operationId) {
    const { href, onClick } = link(operationId);
    return (
      <a {...props} href={href} onClick={onClick} aria-label={`Open ${title}`}>
        {content}
      </a>
    );
  }
  return (
    <button type="button" {...props} aria-label={title}>
      {content}
    </button>
  );
}

/**
 * A predicate: a round cyan pill with an arrow (down where it sits between a
 * relationship's ends). `misfit` marks one whose ends don't fit its type.
 * Hover shows its definition and the classes it joins.
 */
export function PredicatePill({
  propertyId,
  size = "md",
  direction = "right",
  misfit = false,
  "data-testid": testId,
}: {
  propertyId?: string;
  size?: "sm" | "md" | "lg";
  direction?: "right" | "down";
  misfit?: boolean;
  "data-testid"?: string;
}) {
  const { schema } = usePills();
  const label = schema.predicateLabel(propertyId);
  const hover = useHover(() => <PredicateCard propertyId={propertyId} schema={schema} />);
  const Arrow = direction === "down" ? ArrowDown : ArrowRight;
  return (
    <button
      type="button"
      {...hover}
      className={classes(
        "review-pill",
        "review-pill--predicate",
        `review-pill--${size}`,
        misfit && "review-pill--misfit",
      )}
      aria-label={`Predicate ${label}${misfit ? ", its ends don't fit" : ""}`}
      data-pill="predicate"
      data-testid={testId}
    >
      <span className="review-pill__text">{label}</span>
      {!misfit && (
        <span className="review-pill__icon">
          <Arrow size={size === "lg" ? 13 : 12} strokeWidth={2.4} aria-hidden="true" />
        </span>
      )}
    </button>
  );
}

/** A predicate as a static pill (inside a link). */
export function PredicateTag({ propertyId }: { propertyId?: string }) {
  const { schema } = usePills();
  return (
    <span className="review-pill review-pill--predicate review-pill--sm" data-pill="predicate">
      <span className="review-pill__text">{schema.predicateLabel(propertyId)} →</span>
    </span>
  );
}

/**
 * A label that explains itself: the text with an info mark, a button whose
 * hover or focus shows `hint` in the hover overlay.
 */
export function HintLabel({
  label,
  hint,
  id,
  className,
  "data-testid": testId,
}: {
  label: string;
  hint: ReactNode;
  id?: string;
  className?: string;
  "data-testid"?: string;
}) {
  const hover = useHover(() => hint, "review-hint-overlay");
  return (
    <button
      type="button"
      id={id}
      {...hover}
      className={classes("review-hint-label", className)}
      data-testid={testId}
    >
      {label}
      <Info size={12} aria-hidden="true" />
    </button>
  );
}
