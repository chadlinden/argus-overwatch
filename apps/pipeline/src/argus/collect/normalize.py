"""Map raw feedparser entries onto the Article contract."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

from ..models import Article

logger = logging.getLogger("argus.collect.normalize")


def _parsed_time_to_dt(struct_time) -> datetime | None:
    if struct_time is None:
        return None
    try:
        return datetime.fromtimestamp(time.mktime(struct_time), tz=UTC)
    except (OverflowError, ValueError):
        return None


def _entry_published_at(entry) -> datetime:
    for key in ("published_parsed", "updated_parsed"):
        dt = _parsed_time_to_dt(getattr(entry, key, None))
        if dt is not None:
            return dt
    return datetime.now(UTC)


def _entry_summary(entry) -> str:
    for key in ("summary", "description"):
        val = getattr(entry, key, None)
        if val:
            return val
    return ""


def normalize(raw_entries: list[dict]) -> list[Article]:
    now = datetime.now(UTC)
    articles: list[Article] = []

    for item in raw_entries:
        entry = item["entry"]
        title = getattr(entry, "title", None)
        url = getattr(entry, "link", None)
        if not title or not url:
            continue

        articles.append(
            Article(
                source=item["source"],
                title=title.strip(),
                url=url.strip(),
                published_at=_entry_published_at(entry),
                summary=_entry_summary(entry).strip(),
                fetched_at=now,
                category_hint=item.get("category_hint", "general"),
            )
        )

    logger.info("normalized %d/%d entries into articles", len(articles), len(raw_entries))
    return articles
