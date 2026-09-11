"""context.prioritize_articles -- the fix for the real 42-article timeout."""

from datetime import UTC, datetime, timedelta

from argus.synthesize.context import MAX_ARTICLES_IN_PROMPT, prioritize_articles


def test_under_limit_returns_all_sorted_by_recency(make_article):
    now = datetime.now(UTC)
    older = make_article(url="https://a", published_at=now - timedelta(hours=2))
    newer = make_article(url="https://b", published_at=now)

    result = prioritize_articles([older, newer])

    assert result == [newer, older]


def test_caps_at_limit(make_article):
    now = datetime.now(UTC)
    articles = [
        make_article(source=f"Source {i}", url=f"https://example.com/{i}", published_at=now - timedelta(hours=i))
        for i in range(42)  # the real cluster size that caused the timeout
    ]

    result = prioritize_articles(articles)

    assert len(result) == MAX_ARTICLES_IN_PROMPT


def test_prefers_source_diversity_over_pure_recency(make_article):
    now = datetime.now(UTC)
    # One source dumps 10 very recent articles; five other sources each
    # have one older article. Source diversity should still get represented,
    # not get crowded out by one prolific source's recency advantage.
    flood = [
        make_article(source="Flooder", url=f"https://flood/{i}", published_at=now - timedelta(minutes=i))
        for i in range(10)
    ]
    diverse = [
        make_article(source=f"Source {i}", url=f"https://diverse/{i}", published_at=now - timedelta(hours=i + 1))
        for i in range(5)
    ]

    result = prioritize_articles(flood + diverse, limit=6)

    sources_represented = {a.source for a in result}
    assert "Flooder" in sources_represented
    assert len(sources_represented) > 1  # not entirely swallowed by the flood
