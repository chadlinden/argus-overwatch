"""Fetch RSS/Atom feeds. Per-source failures are logged and skipped, not fatal."""

from __future__ import annotations

import logging

import feedparser
import httpx

logger = logging.getLogger("argus.collect.fetch")

DEFAULT_TIMEOUT = 10.0
USER_AGENT = "ArgusOverwatch/4.0 (+https://github.com/; single-container news synthesizer)"


def fetch_feed(url: str, timeout: float = DEFAULT_TIMEOUT) -> bytes | None:
    try:
        resp = httpx.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT}, follow_redirects=True)
        resp.raise_for_status()
        return resp.content
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        logger.warning("fetch failed for %s: %s", url, exc)
        return None


def collect(sources: list[dict], timeout: float = DEFAULT_TIMEOUT) -> list[dict]:
    """Fetch every configured source. Returns raw feed entries tagged with
    the source name/category_hint, ready for normalize().
    """
    raw_entries: list[dict] = []
    for src in sources:
        name = src["name"]
        url = src["url"]
        category_hint = src.get("category_hint", "general")

        content = fetch_feed(url, timeout=timeout)
        if content is None:
            continue

        parsed = feedparser.parse(content)
        if parsed.bozo and not parsed.entries:
            logger.warning("unparseable feed for %s (%s): %s", name, url, parsed.bozo_exception)
            continue

        for entry in parsed.entries:
            raw_entries.append(
                {
                    "source": name,
                    "category_hint": category_hint,
                    "entry": entry,
                }
            )

    logger.info("collected %d raw entries from %d sources", len(raw_entries), len(sources))
    return raw_entries
