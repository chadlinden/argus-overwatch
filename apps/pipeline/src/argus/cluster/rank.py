"""Score clusters by source diversity, article count, and recency.

v4 fix: today's real run (2026-08-27) exposed a real bug in v3's formula --
a 42-article SINGLE-source cluster scored 46.6, nearly beating a genuinely
cross-verified 10-source/15-article story at 49.0. Raw article count was
linear in the score, so volume from one source could nearly match
independent corroboration from ten. That's backwards: this product's whole
premise is "clusters public news from a few hundred sources" -- source
diversity is the signal that means something got independently reported,
not just posted a lot.

Fix: article count moves from linear to log1p (diminishing returns -- the
11th article from the same story is much less informative than the 2nd),
and its weight goes up slightly so it still matters as corroborating
volume, just can no longer dominate. Verified against the real 2026-08-27
data in tests/test_rank.py using the exact two clusters that exposed this.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

from ..models import Cluster

SOURCE_DIVERSITY_WEIGHT = 3.0
ARTICLE_COUNT_WEIGHT = 2.0  # applied to log1p(count), not raw count -- see module docstring
RECENCY_WEIGHT = 4.0
RECENCY_HALF_LIFE_HOURS = 12.0


def _recency_score(cluster: Cluster, now: datetime) -> float:
    most_recent = max(a.published_at for a in cluster.articles)
    age_hours = max(0.0, (now - most_recent).total_seconds() / 3600.0)
    return 0.5 ** (age_hours / RECENCY_HALF_LIFE_HOURS)


def _article_count_score(article_count: int) -> float:
    return math.log1p(article_count)


def rank_clusters(clusters: list[Cluster], now: datetime | None = None) -> list[Cluster]:
    now = now or datetime.now(UTC)

    for c in clusters:
        source_diversity = len(c.sources)
        article_count = len(c.articles)
        recency = _recency_score(c, now)
        c.score = (
            source_diversity * SOURCE_DIVERSITY_WEIGHT
            + _article_count_score(article_count) * ARTICLE_COUNT_WEIGHT
            + recency * RECENCY_WEIGHT
        )

    return sorted(clusters, key=lambda c: c.score, reverse=True)
