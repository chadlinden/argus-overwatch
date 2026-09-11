"""Deterministic evaluation for article-clustering constraints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Relation = Literal["must_link", "cannot_link"]


@dataclass(frozen=True, slots=True)
class ClusterConstraint:
    case_id: str
    run_date: str
    relation: Relation
    left_article_id: str
    right_article_id: str
    status: str
    reason: str

    @classmethod
    def from_dict(cls, value: dict) -> ClusterConstraint:
        relation = value["relation"]
        if relation not in {"must_link", "cannot_link"}:
            raise ValueError(f"unknown cluster relation: {relation}")
        return cls(
            case_id=value["case_id"],
            run_date=value["run_date"],
            relation=relation,
            left_article_id=value["left_article_id"],
            right_article_id=value["right_article_id"],
            status=value["status"],
            reason=value["reason"],
        )


@dataclass(frozen=True, slots=True)
class ConstraintResult:
    constraint: ClusterConstraint
    passed: bool
    detail: str


def article_cluster_index(clusters: list[dict]) -> dict[str, str]:
    """Map each article ID to its cluster ID, rejecting duplicate membership."""
    index: dict[str, str] = {}
    for cluster in clusters:
        cluster_id = cluster["id"]
        for article_id in cluster["articles"]:
            previous = index.setdefault(article_id, cluster_id)
            if previous != cluster_id:
                raise ValueError(
                    f"article {article_id} belongs to both {previous} and {cluster_id}"
                )
    return index


def evaluate_constraint(
    constraint: ClusterConstraint,
    article_to_cluster: dict[str, str],
) -> ConstraintResult:
    left_cluster = article_to_cluster.get(constraint.left_article_id)
    right_cluster = article_to_cluster.get(constraint.right_article_id)

    missing = [
        article_id
        for article_id, cluster_id in (
            (constraint.left_article_id, left_cluster),
            (constraint.right_article_id, right_cluster),
        )
        if cluster_id is None
    ]
    if missing:
        return ConstraintResult(
            constraint=constraint,
            passed=False,
            detail=f"missing article IDs: {', '.join(missing)}",
        )

    linked = left_cluster == right_cluster
    passed = linked if constraint.relation == "must_link" else not linked
    actual = "linked" if linked else "separate"
    return ConstraintResult(
        constraint=constraint,
        passed=passed,
        detail=f"expected {constraint.relation}; articles are {actual}",
    )
