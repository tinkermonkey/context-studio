"""
The pre-review stage's assessment harness
(documentation/extraction/experiments/2026-11-22-pre-review-stage.md).

Phase 0 only, free, no model calls:

    python scripts/benchmark_pre_review.py witness          # where the split question applies
    python scripts/benchmark_pre_review.py seeded --fake keep     # the seeds, scored with a stage that keeps all
    python scripts/benchmark_pre_review.py seeded --fake oracle   # ... with one that knows every seed

`witness` reports the split witness on Gate D's four splits (it must mark all
four), on each benchmark document's gold titles, and on single_call's recorded
titles. `seeded` builds the planted errors of the dev documents for takes 1-3
and scores a fake stage on them; the paid stage arrives with Phase 1.

Run from local-server/ with the venv active. Add --json for machine-readable output.
"""

import argparse
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.extraction.entities import (  # noqa: E402
    PreReviewAnswer,
    PreReviewPart,
    PreReviewQuestion,
    PreReviewVerdict,
)
from domain.extraction.pre_review import split_witness  # noqa: E402
from domain.extraction.single_call import parse_individuals  # noqa: E402
from tests.integration.pipelines._harness.benchmark import (  # noqa: E402
    DEV_DOCUMENTS,
    HOLDOUT_DOCUMENTS,
    load_gold,
    load_schema_bundle,
)
from tests.integration.pipelines._harness.pre_review_seeded import (  # noqa: E402
    MERGE,
    RETYPE_REALISTIC,
    RETYPE_SAME_LAYER,
    ClassCatalog,
    SeededDocument,
    SeededScore,
    build_seeded,
    gate,
    recorded_mistypes,
    score_seeded,
)

RECORDINGS = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "integration"
    / "fixtures"
    / "cassettes"
    / "extraction_benchmark_single_call"
)
TAKES = (1, 2, 3)

# The four items the person split by hand in Gate D
# (documentation/extraction/experiments/2026-11-21-gate-d-real-documents.md)
GATE_D_SPLITS = (
    "Torx T20, T25",
    "Copper water supply kits WX8X2, WX8X3, WX8X4",
    "Straight and Phillips blade screwdriver",
    "Compression nut and ferrule",
)


def recorded_titles(document_id: str) -> list[tuple[str, str]]:
    """single_call's recorded (title, class) answers for a document; empty when not recorded."""
    path = RECORDINGS / f"{document_id}.json"
    if not path.exists():
        return []
    found: list[tuple[str, str]] = []
    for response in json.loads(path.read_text(encoding="utf-8")).values():
        content = str(response.get("content") or "")
        if '"individuals"' not in content:
            continue
        # Every class is accepted here: the answer is read as recorded, not checked
        individuals, _ = parse_individuals(content, "", _AnyClass())
        found.extend((i.mention.name, i.class_ref) for i in individuals)
    return found


class _AnyClass(Mapping[str, str]):
    """A class-reference lookup that accepts every reference as written."""

    def __getitem__(self, key: str) -> str:
        return key

    def __iter__(self):  # pragma: no cover - never iterated
        return iter(())

    def __len__(self) -> int:  # pragma: no cover
        return 0

    def get(self, key: str, default: Any = None) -> str:  # type: ignore[override]
        return key


def witness_report() -> dict[str, Any]:
    gate_d = {title: split_witness(title) for title in GATE_D_SPLITS}
    documents = {}
    for document_id in (*DEV_DOCUMENTS, *HOLDOUT_DOCUMENTS):
        gold = load_gold(document_id)
        marked = [g.title for g in gold.individuals if split_witness(g.title)]
        recorded = [title for title, _ in recorded_titles(document_id)]
        documents[document_id] = {
            "gold_titles": len(gold.individuals),
            "gold_marked": len(marked),
            "gold_marked_examples": marked[:6],
            "recorded_titles": len(recorded),
            "recorded_marked": sum(1 for t in recorded if split_witness(t)),
        }
    return {
        "gate_d_splits": gate_d,
        "gate_d_all_marked": all(gate_d.values()),
        "documents": documents,
    }


def oracle_stage(
    document: SeededDocument, gold_titles: Mapping[str, Any]
) -> dict[int, PreReviewVerdict]:
    """A fake stage that knows every seed: it puts each one right and leaves the rest alone."""
    verdicts: dict[int, PreReviewVerdict] = {}
    for item in document.items:
        seed = document.seeds[item.index]
        if seed.stratum == MERGE:
            parts = tuple(
                PreReviewPart(gold_titles[key].title, gold_titles[key].class_ref)
                for key in seed.gold_keys
            )
            verdicts[item.index] = PreReviewVerdict(
                PreReviewAnswer.SPLIT,
                PreReviewQuestion.SPLIT,
                "oracle",
                item.title,
                item.class_ref,
                parts=parts,
            )
        elif seed.stratum in (RETYPE_REALISTIC, RETYPE_SAME_LAYER):
            verdicts[item.index] = PreReviewVerdict(
                PreReviewAnswer.RETYPE,
                PreReviewQuestion.RETYPE,
                "oracle",
                item.title,
                item.class_ref,
                class_ref=gold_titles[seed.gold_keys[0]].class_ref,
            )
    return verdicts


def seeded_report(fake: str) -> dict[str, Any]:
    catalog = ClassCatalog.from_bundle(load_schema_bundle())
    total = SeededScore()
    takes = []
    for document_id in DEV_DOCUMENTS:
        gold = load_gold(document_id)
        mistypes = recorded_mistypes(gold, recorded_titles(document_id))
        by_key = {g.key: g for g in gold.individuals}
        for take in TAKES:
            document = build_seeded(gold, catalog, take, mistypes)
            verdicts = oracle_stage(document, by_key) if fake == "oracle" else {}
            score = score_seeded(document, gold, verdicts)
            total.add(score)
            takes.append(
                {
                    "document": document_id,
                    "take": take,
                    "items": len(document.items),
                    "strata": document.stratum_counts(),
                    "merge_examples": [
                        document.items[i].title
                        for i, s in document.seeds.items()
                        if s.stratum == MERGE
                    ][:3],
                    "realistic_examples": [
                        f"{document.items[i].title}: {s.planted_class} (gold {by_key[s.gold_keys[0]].class_ref})"
                        for i, s in document.seeds.items()
                        if s.stratum == RETYPE_REALISTIC
                    ][:3],
                }
            )
    return {
        "fake_stage": fake,
        "takes": takes,
        "score": total.to_json(),
        "precision": total.precision(),
        "gate": [vars(g) for g in gate(total)],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)
    witness = commands.add_parser("witness", help="Where the split witness fires (free)")
    witness.add_argument("--json", action="store_true")
    seeded = commands.add_parser("seeded", help="Planted errors, scored with a fake stage (free)")
    seeded.add_argument("--fake", choices=("keep", "oracle"), required=True)
    seeded.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = witness_report() if args.command == "witness" else seeded_report(args.fake)
    if args.json:
        print(json.dumps(report, indent=2))
        return
    if args.command == "witness":
        print(
            f"Gate D splits marked: {sum(report['gate_d_splits'].values())} of {len(GATE_D_SPLITS)}"
        )
        for title, marked in report["gate_d_splits"].items():
            print(f"  {'yes' if marked else 'NO '}  {title}")
        print("\ndocument                gold marked   recorded marked")
        for document_id, row in report["documents"].items():
            print(
                f"{document_id:22}  {row['gold_marked']:>3} of {row['gold_titles']:<4}"
                f"  {row['recorded_marked']:>3} of {row['recorded_titles']}"
            )
        return
    print(f"Fake stage: {report['fake_stage']}")
    for take in report["takes"]:
        strata = ", ".join(f"{k} {v}" for k, v in take["strata"].items())
        print(f"  {take['document']} take {take['take']}: {take['items']} items ({strata})")
    print(f"precision: {report['precision']}")
    for g in report["gate"]:
        print(
            f"  {g['question']}: recovery {g['recovery']:.2f} (needs {g['needed']}),"
            f" harms {g['harms']}/{g['controls']} (upper {g['harm_upper']:.3f})"
            f" -> {'pass' if g['passed'] else 'fail'}"
        )


if __name__ == "__main__":
    main()
