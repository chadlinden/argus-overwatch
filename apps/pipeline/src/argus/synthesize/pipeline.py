"""The synthesis state machine: one cluster in, one Story out.

PENDING -> SYNTHESIZING -> EVAL_CHECK -> PUBLISHED | NEEDS_REVIEW | STUB

The LLM makes a bounded decision (write the story and self-report confidence)
inside SYNTHESIZING; everything
about whether that decision is trustworthy enough to ship is decided by
deterministic application code in EVAL_CHECK. The model cannot publish its
own output -- there is no code path from SYNTHESIZING straight to PUBLISHED.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from ..eval.quality import evaluate_story
from ..models import Cluster, EvalResult, ReviewStatus, Story, SynthesisResult
from .backends import synthesize_via_anthropic, synthesize_via_local
from .context import prioritize_articles
from .router import DEFAULT_LOCAL_MODEL, ModelChoice, choose_model

logger = logging.getLogger("argus.synthesize.pipeline")

MIN_CONFIDENCE_TO_PUBLISH = 0.6  # Below this, the model itself was not confident.


def _stub_story(cluster: Cluster) -> Story:
    lines = ["*Stub report -- no LLM backend available.*", ""]
    for a in sorted(cluster.articles, key=lambda x: x.published_at):
        lines.append(f"- **{a.source}**: {a.title}")
    return Story(
        cluster=cluster,
        title=cluster.label,
        body_markdown="\n".join(lines),
        citations=[a.url for a in cluster.articles],
        review_status=ReviewStatus.STUB,
        synthesis_backend="stub",
        synthesis_confidence=None,
        eval=None,
    )


def _run_synthesis(
    cluster: Cluster,
    choice: ModelChoice,
    api_key: str | None,
    backend: str,
    local_host: str,
    local_timeout: float,
) -> SynthesisResult | None:
    prioritized = prioritize_articles(cluster.articles)

    if backend in {"auto", "anthropic"} and api_key:
        result = synthesize_via_anthropic(prioritized, api_key, choice.anthropic_model)
        if result is not None:
            return result
        if backend == "anthropic":
            return None

    if backend in {"auto", "local"}:
        # Single local model, so there is nothing to de-escalate to. The v4
        # de-escalation fallback was removed 2026-09-05 along with the fake
        # strong local tier (docs/adr/0002). If a second local model ever
        # becomes real, reintroduce the retry with a capability check rather
        # than a string comparison against the fast-tier constant -- the old
        # guard fired on any failure, not on the missing-chat-template case
        # it was written for.
        result = synthesize_via_local(prioritized, choice.local_model, local_host, local_timeout)
        if result is not None:
            return result

    return None


def run_cluster(
    cluster: Cluster,
    rank: int,
    api_key: str | None,
    backend: str = "auto",
    local_host: str = "http://localhost:11434",
    local_timeout: float = 180.0,
    local_model: str = DEFAULT_LOCAL_MODEL,
) -> Story:
    """SYNTHESIZING -> EVAL_CHECK -> terminal, for one cluster. Every branch
    below is deterministic; the only non-deterministic step is the single
    model call inside _run_synthesis.
    """
    choice = choose_model(rank, local_model)
    logger.info(
        "cluster %s: rank=%d local=%s cloud_tier=%s",
        cluster.id[:12], rank, choice.local_model, choice.cloud_tier,
    )

    # STATE: SYNTHESIZING
    synthesis = _run_synthesis(cluster, choice, api_key, backend, local_host, local_timeout)

    if synthesis is None:
        # No backend produced output -- this is the STUB path, not a quality
        # failure. It never reaches EVAL_CHECK because there's nothing to
        # evaluate yet.
        logger.info("cluster %s: no backend available, stub", cluster.id[:12])
        return _stub_story(cluster)

    citations = [a.url for a in cluster.articles]

    # STATE: EVAL_CHECK
    eval_result: EvalResult = evaluate_story(
        synthesis, citations, prioritize_articles(cluster.articles),
        host=local_host, model=choice.local_model, timeout=local_timeout,
    )

    confidence_ok = synthesis.confidence >= MIN_CONFIDENCE_TO_PUBLISH
    status = (
        ReviewStatus.PUBLISHED if (eval_result.passed and confidence_ok)
        else ReviewStatus.NEEDS_REVIEW
    )

    if status is ReviewStatus.NEEDS_REVIEW:
        reason = (
            f"eval failed: {eval_result.notes}" if not eval_result.passed
            else f"low confidence: {synthesis.confidence:.2f} < {MIN_CONFIDENCE_TO_PUBLISH}"
        )
        logger.info("cluster %s: NEEDS_REVIEW -- %s", cluster.id[:12], reason)
    else:
        logger.info(
            "cluster %s: PUBLISHED (confidence=%.2f, via=%s)",
            cluster.id[:12], synthesis.confidence, synthesis.backend,
        )

    return Story(
        cluster=cluster,
        title=synthesis.title or cluster.label,
        body_markdown=synthesis.body_markdown,
        citations=citations,
        review_status=status,
        synthesis_backend=synthesis.backend,
        synthesis_confidence=synthesis.confidence,
        eval=eval_result,
    )


def run_clusters(
    clusters: list[Cluster],
    api_key: str | None,
    max_stories: int,
    backend: str = "auto",
    local_host: str = "http://localhost:11434",
    local_timeout: float = 180.0,
    local_model: str = DEFAULT_LOCAL_MODEL,
    done_stories: dict[str, Story] | None = None,
    on_story: Callable[[Story], None] | None = None,
) -> list[Story]:
    top = clusters[:max_stories]
    done = done_stories or {}
    stories: list[Story] = []
    reused = 0

    for rank, cluster in enumerate(top):
        existing = done.get(cluster.id)
        if existing is not None:
            # Rank is positional and stable for a given processed checkpoint,
            # so a resumed story keeps the standing it was synthesized under.
            logger.info("cluster %s: resumed from checkpoint", cluster.id[:12])
            stories.append(existing)
            reused += 1
            continue

        story = run_cluster(cluster, rank, api_key, backend, local_host, local_timeout, local_model)
        stories.append(story)
        if on_story is not None:
            # Persist immediately: the next story may take minutes, and an
            # interrupted run should not lose work already paid for.
            on_story(story)

    counts: dict[str, int] = {}
    for s in stories:
        counts[s.review_status.value] = counts.get(s.review_status.value, 0) + 1
    logger.info(
        "synthesized %d stories (%d resumed, %d new): %s",
        len(stories), reused, len(stories) - reused, counts,
    )
    return stories
