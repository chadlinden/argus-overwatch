"""Data contracts shared across pipeline stages. See docs/ARCHITECTURE.md.

v4 vs v3: Story is no longer "synthesized: bool" -- it carries a real
review_status, because synthesis is no longer a fire-and-forget call. It
goes through an eval gate before anything gets treated as publishable.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


def _sha256(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
    return h.hexdigest()


@dataclass(frozen=True, slots=True)
class Article:
    source: str
    title: str
    url: str
    published_at: datetime
    summary: str
    fetched_at: datetime
    category_hint: str = "general"

    @property
    def id(self) -> str:
        return _sha256(self.url)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "title": self.title,
            "url": self.url,
            "published_at": self.published_at.isoformat(),
            "summary": self.summary,
            "fetched_at": self.fetched_at.isoformat(),
            "category_hint": self.category_hint,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Article:
        return cls(
            source=d["source"],
            title=d["title"],
            url=d["url"],
            published_at=datetime.fromisoformat(d["published_at"]),
            summary=d["summary"],
            fetched_at=datetime.fromisoformat(d["fetched_at"]),
            category_hint=d.get("category_hint", "general"),
        )


@dataclass(slots=True)
class Cluster:
    articles: list[Article]
    label: str = ""
    category: str = "general"
    score: float = 0.0

    @property
    def id(self) -> str:
        return _sha256(*sorted(a.id for a in self.articles))

    @property
    def sources(self) -> list[str]:
        seen: list[str] = []
        for a in self.articles:
            if a.source not in seen:
                seen.append(a.source)
        return seen

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "category": self.category,
            "score": self.score,
            "articles": [a.id for a in self.articles],
            "sources": self.sources,
        }

    @classmethod
    def from_dict(cls, d: dict, articles_by_id: dict[str, Article]) -> Cluster:
        return cls(
            articles=[articles_by_id[aid] for aid in d["articles"] if aid in articles_by_id],
            label=d.get("label", ""),
            category=d.get("category", "general"),
            score=d.get("score", 0.0),
        )


class ReviewStatus(str, Enum):
    """The synthesis state machine's terminal states (see synthesize/pipeline.py).

    PENDING/SYNTHESIZING/EVAL_CHECK are transient -- a Story is only ever
    persisted in one of these three.
    """

    PUBLISHED = "published"
    NEEDS_REVIEW = "needs_review"
    STUB = "stub"  # no LLM available; deterministic fallback, not a quality judgment


@dataclass(slots=True)
class SynthesisResult:
    """What the model actually returned for one cluster -- kept distinct from
    Story so the model's self-report (confidence) and the deterministic eval
    score are never confused with each other. They're independent signals,
    same as 04C's value-threshold and confidence-threshold gates.
    """

    title: str
    body_markdown: str
    confidence: float  # model's own self-reported completeness/certainty, 0-1
    backend: str  # "local:<model>" | "anthropic" | "stub"


@dataclass(slots=True)
class EvalResult:
    """Deterministic-ish quality gate output. `passed` drives the state
    machine transition; the rest is for humans reviewing NEEDS_REVIEW stories.
    """

    cites_sources: bool
    distinguishes_fact_from_synthesis: bool
    no_unsupported_claims: bool
    notes: str
    passed: bool

    def to_dict(self) -> dict:
        return {
            "cites_sources": self.cites_sources,
            "distinguishes_fact_from_synthesis": self.distinguishes_fact_from_synthesis,
            "no_unsupported_claims": self.no_unsupported_claims,
            "notes": self.notes,
            "passed": self.passed,
        }

    @classmethod
    def from_dict(cls, d: dict) -> EvalResult:
        return cls(
            cites_sources=d["cites_sources"],
            distinguishes_fact_from_synthesis=d["distinguishes_fact_from_synthesis"],
            no_unsupported_claims=d["no_unsupported_claims"],
            notes=d["notes"],
            passed=d["passed"],
        )


@dataclass(slots=True)
class Story:
    cluster: Cluster
    title: str
    body_markdown: str
    citations: list[str] = field(default_factory=list)
    review_status: ReviewStatus = ReviewStatus.STUB
    synthesis_backend: str = "stub"
    synthesis_confidence: float | None = None
    eval: EvalResult | None = None

    def slug(self) -> str:
        import re

        base = re.sub(r"[^a-z0-9]+", "-", self.title.lower()).strip("-")
        return (base or self.cluster.id[:12])[:80]

    def to_dict(self) -> dict:
        """Persisted per-story so an interrupted synthesis run can resume
        without re-paying for stories that already completed. `cluster_id` is
        the resume key; the cluster itself is rehydrated from the processed
        checkpoint rather than duplicated here."""
        return {
            "cluster_id": self.cluster.id,
            "title": self.title,
            "body_markdown": self.body_markdown,
            "citations": list(self.citations),
            "review_status": self.review_status.value,
            "synthesis_backend": self.synthesis_backend,
            "synthesis_confidence": self.synthesis_confidence,
            "eval": self.eval.to_dict() if self.eval else None,
        }

    @classmethod
    def from_dict(cls, d: dict, clusters_by_id: dict[str, Cluster]) -> Story | None:
        """Returns None when the cluster is unknown -- e.g. the processed
        checkpoint was regenerated and cluster IDs shifted. A resumed story
        whose cluster no longer exists is stale, not recoverable, so it is
        dropped and re-synthesized rather than silently attached to the
        wrong cluster."""
        cluster = clusters_by_id.get(d["cluster_id"])
        if cluster is None:
            return None
        return cls(
            cluster=cluster,
            title=d["title"],
            body_markdown=d["body_markdown"],
            citations=list(d.get("citations", [])),
            review_status=ReviewStatus(d["review_status"]),
            synthesis_backend=d.get("synthesis_backend", "stub"),
            synthesis_confidence=d.get("synthesis_confidence"),
            eval=EvalResult.from_dict(d["eval"]) if d.get("eval") else None,
        )
