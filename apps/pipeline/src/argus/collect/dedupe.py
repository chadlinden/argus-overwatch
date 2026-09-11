"""Drop duplicate articles: exact URL match, then near-duplicate title match."""

from __future__ import annotations

import logging
import re

from ..models import Article

logger = logging.getLogger("argus.collect.dedupe")


def _normalize_title(title: str) -> str:
    t = title.lower().strip()
    t = re.sub(r"[^a-z0-9\s]", "", t)
    t = re.sub(r"\s+", " ", t)
    return t


def dedupe(articles: list[Article]) -> list[Article]:
    seen_ids: set[str] = set()
    seen_titles: set[str] = set()
    result: list[Article] = []

    for a in articles:
        if a.id in seen_ids:
            continue
        norm_title = _normalize_title(a.title)
        if norm_title and norm_title in seen_titles:
            continue

        seen_ids.add(a.id)
        if norm_title:
            seen_titles.add(norm_title)
        result.append(a)

    dropped = len(articles) - len(result)
    if dropped:
        logger.info("dedupe dropped %d/%d articles", dropped, len(articles))
    return result
