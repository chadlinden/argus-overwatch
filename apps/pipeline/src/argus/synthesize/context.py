"""Context prioritization for synthesis prompts.

Real bug this fixes: a live run had a top-ranked cluster with 42
articles. Dumping all 42 into one prompt is why local synthesis timed out
at 180s on every top-N story. The pipeline must prioritize useful context
rather than increase the timeout for an oversized prompt.
"""

from __future__ import annotations

from ..models import Article

MAX_ARTICLES_IN_PROMPT = 8


def prioritize_articles(articles: list[Article], limit: int = MAX_ARTICLES_IN_PROMPT) -> list[Article]:
    """Pick the subset of a cluster's articles worth spending prompt tokens on.

    Priority: one article per source first (source diversity is the whole
    point of cross-verification -- ten headlines from one outlet add
    nothing a single one didn't already say), then fill remaining slots by
    recency. Deterministic, same rationale as rank.py: this is not a
    semantic judgment call, so it doesn't need a model.
    """
    if len(articles) <= limit:
        return sorted(articles, key=lambda a: a.published_at, reverse=True)

    by_source: dict[str, list[Article]] = {}
    for a in articles:
        by_source.setdefault(a.source, []).append(a)
    for group in by_source.values():
        group.sort(key=lambda a: a.published_at, reverse=True)

    selected: list[Article] = []
    remaining: list[Article] = []

    # Round 1: newest article from each distinct source.
    for group in by_source.values():
        selected.append(group[0])
        remaining.extend(group[1:])

    selected.sort(key=lambda a: a.published_at, reverse=True)

    if len(selected) > limit:
        # More sources than slots -- keep the newest N sources. Losing
        # source coverage is worse than losing recency here, but you have
        # to lose something; this is the one branch where that's true.
        return selected[:limit]

    remaining.sort(key=lambda a: a.published_at, reverse=True)
    selected.extend(remaining[: limit - len(selected)])
    selected.sort(key=lambda a: a.published_at, reverse=True)
    return selected
