"""Drop obviously low-value articles before the expensive stages."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from ..models import Article

logger = logging.getLogger("argus.collect.filter")

MIN_TITLE_LEN = 8
MAX_AGE_DAYS = 7


def filter_articles(
    articles: list[Article],
    now: datetime | None = None,
    max_age_days: int = MAX_AGE_DAYS,
) -> list[Article]:
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=max_age_days)

    result = [
        a
        for a in articles
        if len(a.title.strip()) >= MIN_TITLE_LEN and a.published_at >= cutoff
    ]

    dropped = len(articles) - len(result)
    if dropped:
        logger.info("filter dropped %d/%d articles", dropped, len(articles))
    return result
