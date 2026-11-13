"""
Scoring an individual-extraction run against a hand-made benchmark extraction.

A benchmark document (tests/integration/fixtures/pipelines/extraction_benchmark/
<doc>/) is a prose source plus `gold.json`: every individual a careful modeller
finds in it, typed against the Documentation Robotics schema, with the passages
that evidence each one. See that directory's README for how the gold files were
made and what their fields mean.

Scoring answers four questions about a run:

- Did it find the individuals? (recall over the gold set, and over its `core`
  tier: the ones the document names and describes)
- Is what it found real? (precision; a prediction that matches nothing in gold
  is spurious, one that matches a gold `excluded` entry is a known distractor)
- Did it type them correctly? (the gold type, or one of the types gold lists as
  acceptable where the schema leaves a judgment call)
- Did it state the relationships? (recall over the gold relationships, and
  over those whose two ends it found; gold relationships are the plainly stated
  ones, not all the correct ones, so there is no relationship precision)

A predicted individual matches a gold individual by name (title or alias,
ignoring case, markdown and a plural ending; deliberately not the pipeline's
own merge key, which is part of what is being measured). A gold individual that states
something (a goal, requirement, finding: the motivation layer) has no name in
the text, so it also matches a motivation-layer prediction whose passage
overlaps its evidence, or whose title is drawn from that evidence.
"""

from __future__ import annotations

import json
import lzma
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

GOLD_FORMAT = "extraction-benchmark/1"
BENCHMARK_DIR = (
    Path(__file__).resolve().parents[2] / "fixtures" / "pipelines" / "extraction_benchmark"
)
# The DR taxonomy the gold files were made against, as a schema-only Context Studio bundle.
SCHEMA_BUNDLE = "dr_spec.bundle.json.xz"

TIERS = ("core", "supporting")
# The layer whose individuals are statements rather than named things.
STATEMENT_LAYER = "motivation"
# Share of the shorter passage two passages must have in common to be the same passage.
MIN_PASSAGE_OVERLAP = 0.5
# Share of a predicted title's words that must come from a gold passage, and the fewest words.
MIN_TITLE_COVERAGE = 0.7
MIN_TITLE_WORDS = 3

_PUNCTUATION = re.compile(r"[`*_\"“”()\[\]{}<>]")
_APOSTROPHES = re.compile(r"['‘’ʼ´]")
_TRAILING = ".,;:"
_WORD = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    (
        "a an and are as at be by for from in is it its of on or that the their this to will with"
    ).split()
)


def layer_of(class_ref: str) -> str:
    """The layer of a DR class reference ("application.applicationcomponent" -> "application")."""
    return class_ref.split(".", 1)[0]


def name_key(label: str | None) -> str:
    """
    A label's match key: lowercased, without markdown, brackets or apostrophes,
    whitespace collapsed, and the last word singular ("`Runners`" -> "runner").
    """
    text = _APOSTROPHES.sub("", _PUNCTUATION.sub(" ", str(label or ""))).lower()
    tokens = [t for t in (token.strip(_TRAILING) for token in text.split()) if t]
    if tokens:
        tokens[-1] = _singular(tokens[-1])
    return " ".join(tokens)


def _singular(word: str) -> str:
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def _words(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in _STOPWORDS]


@dataclass(frozen=True)
class Passage:
    """A passage of the source: character offsets (end exclusive) and its text."""

    start: int
    end: int
    quote: str = ""

    def overlap(self, other: "Passage") -> float:
        """The share of the shorter passage the two have in common (0 when either is empty)."""
        shorter = min(self.end - self.start, other.end - other.start)
        if shorter <= 0:
            return 0.0
        common = min(self.end, other.end) - max(self.start, other.start)
        return max(0, common) / shorter


@dataclass(frozen=True)
class GoldIndividual:
    """One individual of a gold extraction."""

    key: str
    title: str
    class_ref: str
    tier: str
    acceptable: frozenset[str] = frozenset()
    aliases: tuple[str, ...] = ()
    evidence: tuple[Passage, ...] = ()

    @property
    def layer(self) -> str:
        return layer_of(self.class_ref)

    @property
    def is_statement(self) -> bool:
        return self.layer == STATEMENT_LAYER

    @property
    def names(self) -> frozenset[str]:
        return frozenset(k for k in (name_key(n) for n in (self.title, *self.aliases)) if k)

    def accepts(self, class_ref: str) -> bool:
        return class_ref == self.class_ref or class_ref in self.acceptable


@dataclass(frozen=True)
class GoldRelationship:
    """One relationship of a gold extraction, between two gold individuals' keys."""

    source: str
    predicate: str
    target: str
    tier: str = "core"


@dataclass(frozen=True)
class Gold:
    """A document's gold extraction."""

    document_id: str
    individuals: tuple[GoldIndividual, ...]
    relationships: tuple[GoldRelationship, ...]
    excluded: frozenset[str]
    source_text: str = ""
    document: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Predicted:
    """An individual a run extracted."""

    title: str
    class_refs: tuple[str, ...]
    evidence: tuple[Passage, ...] = ()


@dataclass(frozen=True)
class PredictedRelationship:
    """A relationship a run extracted, between two predicted titles."""

    source: str
    predicate: str
    target: str


def benchmark_documents(directory: Path = BENCHMARK_DIR) -> list[str]:
    """The ids of the benchmark documents on disk, sorted."""
    return sorted(p.parent.name for p in directory.glob("*/gold.json"))


def load_gold(document_id: str, directory: Path = BENCHMARK_DIR) -> Gold:
    """Read a document's gold extraction and its source text."""
    folder = directory / document_id
    data = json.loads((folder / "gold.json").read_text(encoding="utf-8"))
    if data.get("format") != GOLD_FORMAT:
        raise ValueError(f"{folder / 'gold.json'}: expected format {GOLD_FORMAT!r}")
    return Gold(
        document_id=document_id,
        individuals=tuple(
            GoldIndividual(
                key=item["key"],
                title=item["title"],
                class_ref=item["class"],
                tier=item["tier"],
                acceptable=frozenset(item.get("acceptable_classes", ())),
                aliases=tuple(item.get("aliases", ())),
                evidence=tuple(_passage(e) for e in item.get("evidence", ())),
            )
            for item in data["individuals"]
        ),
        relationships=tuple(
            GoldRelationship(r["source"], r["predicate"], r["target"], r.get("tier", "core"))
            for r in data["relationships"]
        ),
        excluded=frozenset(
            key
            for entry in data.get("excluded", ())
            for key in (name_key(part) for part in str(entry["label"]).split(" / "))
            if key
        ),
        source_text=(folder / "source.md").read_text(encoding="utf-8"),
        document=data.get("document", {}),
    )


def _passage(item: Mapping[str, Any]) -> Passage:
    return Passage(int(item["start"]), int(item["end"]), str(item.get("quote", "")))


def load_schema_bundle(directory: Path = BENCHMARK_DIR) -> dict[str, Any]:
    """The schema bundle the gold files were made against."""
    return json.loads(lzma.decompress((directory / SCHEMA_BUNDLE).read_bytes()))


def class_reference(cls: Mapping[str, Any]) -> str:
    """A bundle class's DR reference ("application.applicationcomponent"), else its identifier."""
    references = cls.get("external_references") or []
    return str(references[0]["identifier"] if references else cls["identifier"])


@dataclass(frozen=True)
class SchemaSnapshot:
    """What validation needs of the schema: each class's attributes, and the relationship types."""

    attributes: Mapping[str, Mapping[str, Mapping[str, Any]]]
    relationship_types: frozenset[tuple[str, str, str]]
    spec_version: str | None = None

    @classmethod
    def load(cls, directory: Path = BENCHMARK_DIR) -> "SchemaSnapshot":
        bundle = load_schema_bundle(directory)
        refs = {c["identifier"]: class_reference(c) for c in bundle["classes"]}
        return cls(
            attributes={
                refs[c["identifier"]]: {a["identifier"]: a for a in c.get("attributes", ())}
                for c in bundle["classes"]
            },
            relationship_types=frozenset(
                (refs[p["domain"]], p["predicate"], refs[p["range"]])
                for p in bundle["properties"]
                if p.get("domain") in refs and p.get("range") in refs
            ),
        )


def validate_gold(document_id: str, directory: Path = BENCHMARK_DIR) -> list[str]:
    """
    Problems with a document's gold file, empty when it is sound: every quote
    is where it says in the source, every class and relationship type exists
    in the schema snapshot, keys and titles are unique, relationship ends exist.
    """
    folder = directory / document_id
    data = json.loads((folder / "gold.json").read_text(encoding="utf-8"))
    source = (folder / "source.md").read_text(encoding="utf-8")
    schema = SchemaSnapshot.load(directory)
    classes, types = schema.attributes, schema.relationship_types
    problems: list[str] = []

    def check_evidence(owner: str, evidence: Sequence[Mapping[str, Any]]) -> None:
        if not evidence:
            problems.append(f"{owner}: no evidence")
        for item in evidence:
            if source[item["start"] : item["end"]] != item["quote"]:
                problems.append(f"{owner}: quote is not at {item['start']}..{item['end']}")

    class_of: dict[str, str] = {}
    for item in data["individuals"]:
        key = item["key"]
        if key in class_of:
            problems.append(f"{key}: duplicate key")
        class_of[key] = item["class"]
        for ref in (item["class"], *item.get("acceptable_classes", ())):
            if ref not in classes:
                problems.append(f"{key}: unknown class {ref}")
        if item["tier"] not in TIERS:
            problems.append(f"{key}: unknown tier {item['tier']}")
        attributes = classes.get(item["class"], {})
        for name, value in (item.get("data") or {}).items():
            allowed = attributes.get(name, {}).get("allowed_values")
            if name not in attributes:
                problems.append(f"{key}: {item['class']} has no attribute {name}")
            elif allowed and value not in allowed:
                problems.append(f"{key}: {name}={value!r} is not one of {allowed}")
        check_evidence(key, item.get("evidence", ()))
    titles = Counter(name_key(item["title"]) for item in data["individuals"])
    problems += [f"duplicate title {title!r}" for title, count in titles.items() if count > 1]
    names = {
        name_key(n)
        for item in data["individuals"]
        for n in (item["title"], *item.get("aliases", ()))
    }
    for entry in data.get("excluded", ()):
        for part in str(entry["label"]).split(" / "):
            if name_key(part) in names:
                problems.append(f"excluded label {part!r} is also the name of an individual")
    seen: set[tuple[str, str, str]] = set()
    for rel in data["relationships"]:
        triple = (rel["source"], rel["predicate"], rel["target"])
        label = " ".join(triple)
        if triple in seen:
            problems.append(f"{label}: duplicate relationship")
        seen.add(triple)
        if rel["source"] not in class_of or rel["target"] not in class_of:
            problems.append(f"{label}: unknown individual")
        elif (class_of[rel["source"]], rel["predicate"], class_of[rel["target"]]) not in types:
            problems.append(f"{label}: not a relationship type of the schema")
        check_evidence(label, rel.get("evidence", ()))
    return problems


# ---------------------------------------------------------------- predictions


def predictions_from_triples(
    triples: Iterable[Mapping[str, Any]], class_refs: Mapping[str, str] | None = None
) -> tuple[list[Predicted], list[PredictedRelationship]]:
    """
    A run's triples as predicted individuals and relationships.

    A typing triple (predicate "is_a", object a class) gives an individual its
    class; every other triple between two individuals is a relationship.
    Individuals sharing a merge key are one prediction with all their classes
    and passages.

    Args:
        triples: The run's triples (subject, predicate, object, provenance or passages)
        class_refs: Class id, identifier or title (lowercased) -> DR class
            reference, for runs whose typing objects aren't DR references
    """
    refs = {str(k).lower(): v for k, v in (class_refs or {}).items()}
    order: list[str] = []
    titles: dict[str, str] = {}
    classes: dict[str, list[str]] = {}
    passages: dict[str, list[Passage]] = {}
    relationships: list[PredictedRelationship] = []
    for triple in triples:
        subject, obj = triple.get("subject") or {}, triple.get("object") or {}
        predicate = str((triple.get("predicate") or {}).get("label") or "").strip()
        title = str(subject.get("label") or "").strip()
        if not title or not predicate:
            continue
        if predicate.lower() in ("is_a", "is a", "rdf:type") or obj.get("kind") == "class":
            key = name_key(title)
            if key not in titles:
                order.append(key)
                titles[key] = title
            for form in (obj.get("label"), obj.get("id")):
                ref = _class_ref(form, refs)
                if ref and ref not in classes.setdefault(key, []):
                    classes[key].append(ref)
            passages.setdefault(key, []).extend(_triple_passages(triple))
        elif str(obj.get("label") or "").strip():
            relationships.append(
                PredictedRelationship(title, predicate.lower(), str(obj["label"]).strip())
            )
    individuals = [
        Predicted(titles[key], tuple(classes.get(key, ())), tuple(passages.get(key, ())))
        for key in order
    ]
    return individuals, relationships


def _class_ref(form: Any, refs: Mapping[str, str]) -> str | None:
    text = str(form or "").strip()
    if not text:
        return None
    return refs.get(text.lower()) or (text.lower() if "." in text else None)


def _triple_passages(triple: Mapping[str, Any]) -> list[Passage]:
    spans = list(triple.get("passages") or [])
    provenance = triple.get("provenance")
    if isinstance(provenance, Mapping):
        spans.append(
            {
                "start": provenance.get("text_offset_start"),
                "end": provenance.get("text_offset_end"),
                "quote": provenance.get("raw"),
            }
        )
    found = []
    for span in spans:
        start, end = span.get("start"), span.get("end")
        if isinstance(start, int) and isinstance(end, int) and 0 <= start < end:
            found.append(Passage(start, end, str(span.get("quote") or "")))
    return found


# ---------------------------------------------------------------- scoring


@dataclass
class BenchmarkScore:
    """How one run did on one document. Ratios are 0..1; `counts` holds what they came from."""

    document_id: str
    metrics: dict[str, float]
    counts: dict[str, int]
    by_layer: dict[str, dict[str, float]]
    missed: list[dict[str, str]]
    mistyped: list[dict[str, Any]]
    spurious: list[dict[str, Any]]
    duplicates: list[str]
    excluded_hits: list[str]
    missed_relationships: list[str]

    def to_json(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "metrics": self.metrics,
            "counts": self.counts,
            "by_layer": self.by_layer,
            "missed": self.missed,
            "mistyped": self.mistyped,
            "spurious": self.spurious,
            "duplicates": self.duplicates,
            "excluded_hits": self.excluded_hits,
            "missed_relationships": self.missed_relationships,
        }


def match_individuals(gold: Gold, predicted: Sequence[Predicted]) -> dict[int, GoldIndividual]:
    """
    Pair predictions with gold individuals, one to one: index of the
    prediction -> the gold individual it found. Names are matched first; what
    is left is matched to gold statements by passage.
    """
    by_name: dict[str, GoldIndividual] = {}
    for individual in gold.individuals:
        for name in individual.names:
            by_name.setdefault(name, individual)
    matches: dict[int, GoldIndividual] = {}
    taken: set[str] = set()
    for index, prediction in enumerate(predicted):
        found = by_name.get(name_key(prediction.title))
        if found is not None and found.key not in taken:
            matches[index] = found
            taken.add(found.key)
    statements = [g for g in gold.individuals if g.is_statement and g.key not in taken]
    for index, prediction in enumerate(predicted):
        if index in matches or not _may_be_statement(prediction):
            continue
        best = max(
            (g for g in statements if g.key not in taken),
            key=lambda g: _statement_affinity(g, prediction),
            default=None,
        )
        if best is not None and _statement_affinity(best, prediction) > 0:
            matches[index] = best
            taken.add(best.key)
    return matches


def _may_be_statement(prediction: Predicted) -> bool:
    return not prediction.class_refs or any(
        layer_of(ref) == STATEMENT_LAYER for ref in prediction.class_refs
    )


def _statement_affinity(gold: GoldIndividual, prediction: Predicted) -> float:
    """How strongly a prediction is the same statement as a gold individual (0: it isn't)."""
    overlap = max(
        (p.overlap(g) for p in prediction.evidence for g in gold.evidence),
        default=0.0,
    )
    if overlap >= MIN_PASSAGE_OVERLAP:
        return 1.0 + overlap
    words = _words(prediction.title)
    if len(words) < MIN_TITLE_WORDS:
        return 0.0
    gold_words = set(_words(" ".join([gold.title, *(g.quote for g in gold.evidence)])))
    coverage = sum(1 for w in words if w in gold_words) / len(words)
    return coverage if coverage >= MIN_TITLE_COVERAGE else 0.0


def score(
    gold: Gold,
    predicted: Sequence[Predicted],
    relationships: Sequence[PredictedRelationship] = (),
) -> BenchmarkScore:
    """Score a run's individuals and relationships against a document's gold extraction."""
    matches = match_individuals(gold, predicted)
    found = {g.key: index for index, g in matches.items()}
    typed = {
        index
        for index, g in matches.items()
        if any(g.accepts(ref) for ref in predicted[index].class_refs)
    }
    exact = {index for index, g in matches.items() if g.class_ref in predicted[index].class_refs}
    same_layer = {
        index
        for index, g in matches.items()
        if any(layer_of(ref) == g.layer for ref in predicted[index].class_refs)
    }
    grounded = {
        index
        for index, g in matches.items()
        if any(
            p.overlap(e) >= MIN_PASSAGE_OVERLAP
            for p in predicted[index].evidence
            for e in g.evidence
        )
    }
    # A prediction under another name of an individual already found (gold merges
    # "Link check and Reference reliability"; a run may extract the two apart) is
    # neither a find nor an error: it is left out of precision.
    gold_names = {name for g in gold.individuals for name in g.names}
    unmatched = [i for i in range(len(predicted)) if i not in matches]
    duplicates = [i for i in unmatched if name_key(predicted[i].title) in gold_names]
    rest = [i for i in unmatched if i not in duplicates]
    excluded_hits = [
        predicted[i].title for i in rest if name_key(predicted[i].title) in gold.excluded
    ]
    spurious = [i for i in rest if name_key(predicted[i].title) not in gold.excluded]
    counted = len(predicted) - len(duplicates)

    core = [g for g in gold.individuals if g.tier == "core"]
    typed_keys = {matches[i].key for i in typed}
    metrics = {
        "recall": _ratio(len(found), len(gold.individuals)),
        "recall_core": _ratio(sum(1 for g in core if g.key in found), len(core)),
        "precision": _ratio(len(matches), counted),
        "typed_recall": _ratio(len(typed), len(gold.individuals)),
        "typed_recall_core": _ratio(sum(1 for g in core if g.key in typed_keys), len(core)),
        "typed_precision": _ratio(len(typed), counted),
        "type_accuracy": _ratio(len(typed), len(matches)),
        "type_accuracy_exact": _ratio(len(exact), len(matches)),
        "layer_accuracy": _ratio(len(same_layer), len(matches)),
        "evidence_agreement": _ratio(len(grounded), len(matches)),
    }
    metrics["f1"] = _f1(metrics["precision"], metrics["recall"])
    metrics["typed_f1"] = _f1(metrics["typed_precision"], metrics["typed_recall"])

    gold_by_key = {g.key: g for g in gold.individuals}
    pred_gold = {name_key(predicted[i].title): g.key for i, g in matches.items()}
    stated = {
        (pred_gold[name_key(r.source)], r.predicate, pred_gold[name_key(r.target)])
        for r in relationships
        if name_key(r.source) in pred_gold and name_key(r.target) in pred_gold
    }
    gold_triples = {(r.source, r.predicate, r.target) for r in gold.relationships}
    reachable = {t for t in gold_triples if t[0] in found and t[2] in found}
    metrics["relationship_recall"] = _ratio(len(stated & gold_triples), len(gold_triples))
    metrics["relationship_recall_reachable"] = _ratio(len(stated & reachable), len(reachable))
    # No relationship precision: gold holds the relationships the text states most
    # plainly, not every one a run could correctly derive (see the fixtures' README).

    by_layer: dict[str, dict[str, float]] = {}
    for layer in sorted({g.layer for g in gold.individuals}):
        members = [g for g in gold.individuals if g.layer == layer]
        by_layer[layer] = {
            "gold": len(members),
            "recall": _ratio(sum(1 for g in members if g.key in found), len(members)),
            "typed_recall": _ratio(sum(1 for g in members if g.key in typed_keys), len(members)),
        }
    return BenchmarkScore(
        document_id=gold.document_id,
        metrics={name: round(value, 4) for name, value in metrics.items()},
        counts={
            "gold": len(gold.individuals),
            "gold_core": len(core),
            "predicted": len(predicted),
            "matched": len(matches),
            "typed": len(typed),
            "spurious": len(spurious),
            "duplicates": len(duplicates),
            "excluded_hits": len(excluded_hits),
            "gold_relationships": len(gold_triples),
            "predicted_relationships": len(relationships),
            "matched_relationships": len(stated & gold_triples),
        },
        by_layer=by_layer,
        missed=[
            {"key": g.key, "title": g.title, "class": g.class_ref, "tier": g.tier}
            for g in gold.individuals
            if g.key not in found
        ],
        mistyped=[
            {
                "key": g.key,
                "title": predicted[i].title,
                "gold": g.class_ref,
                "predicted": list(predicted[i].class_refs),
            }
            for i, g in matches.items()
            if i not in typed
        ],
        spurious=[
            {"title": predicted[i].title, "predicted": list(predicted[i].class_refs)}
            for i in spurious
        ],
        duplicates=[predicted[i].title for i in duplicates],
        excluded_hits=excluded_hits,
        missed_relationships=[
            f"{gold_by_key[s].title} {p} {gold_by_key[o].title}"
            for s, p, o in sorted(gold_triples - stated)
        ],
    )


def mean_metrics(scores: Sequence[BenchmarkScore]) -> dict[str, float]:
    """The mean of each metric over several documents' scores ({} for none)."""
    if not scores:
        return {}
    names = scores[0].metrics.keys()
    return {name: round(sum(s.metrics[name] for s in scores) / len(scores), 4) for name in names}


def failure_counts(scores: Sequence[BenchmarkScore]) -> dict[str, int]:
    """
    What went wrong across documents, by kind, for choosing what to work on
    next: gold individuals missed (by tier), found but mistyped, predictions
    that match nothing, known distractors extracted, relationships missed.
    """
    counts: Counter[str] = Counter()
    for item in scores:
        for missed in item.missed:
            counts[f"missed_{missed['tier']}"] += 1
        counts["mistyped"] += len(item.mistyped)
        counts["spurious"] += len(item.spurious)
        counts["excluded_extracted"] += len(item.excluded_hits)
        counts["relationship_missed"] += len(item.missed_relationships)
    return dict(counts)


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0
