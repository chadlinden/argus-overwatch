from datetime import UTC, datetime

import pytest

from argus.models import Article


@pytest.fixture
def make_article():
    def _make(
        source="Test Source",
        title="A test headline",
        url="https://example.com/article-1",
        summary="A short summary.",
        published_at=None,
        category_hint="general",
    ):
        now = datetime.now(UTC)
        return Article(
            source=source,
            title=title,
            url=url,
            published_at=published_at or now,
            summary=summary,
            fetched_at=now,
            category_hint=category_hint,
        )

    return _make
