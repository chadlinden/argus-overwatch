"""Evaluate saved Argus cluster outputs against the golden pair constraints."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from argus.eval.clusters import (
    ClusterConstraint,
    article_cluster_index,
    evaluate_constraint,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def _read_jsonl(path: Path) -> list[dict]:
    with path.open() as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--constraints",
        type=Path,
        default=REPO_ROOT / "evals/golden/cluster_constraints.jsonl",
    )
    parser.add_argument(
        "--status",
        choices=("accepted", "proposed", "all"),
        default="accepted",
        help="Evaluate accepted product decisions by default.",
    )
    args = parser.parse_args()

    constraints = [ClusterConstraint.from_dict(row) for row in _read_jsonl(args.constraints)]
    if args.status != "all":
        constraints = [item for item in constraints if item.status == args.status]

    by_date: dict[str, list[ClusterConstraint]] = defaultdict(list)
    for constraint in constraints:
        by_date[constraint.run_date].append(constraint)

    results = []
    for run_date, dated_constraints in sorted(by_date.items()):
        cluster_path = REPO_ROOT / f"data/processed/{run_date}.jsonl"
        index = article_cluster_index(_read_jsonl(cluster_path))
        results.extend(evaluate_constraint(item, index) for item in dated_constraints)

    for result in results:
        marker = "PASS" if result.passed else "FAIL"
        print(f"{marker} {result.constraint.case_id}: {result.detail}")

    passed = sum(result.passed for result in results)
    print(f"\n{passed}/{len(results)} constraints passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
