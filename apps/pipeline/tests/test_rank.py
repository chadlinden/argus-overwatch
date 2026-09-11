"""Regression test for the real bug ADR 0002 fixed: article count must not
be able to outweigh source diversity. Uses the exact shape of the two real
clusters that exposed this on 2026-08-27, not synthetic numbers picked to
make the test pass.
"""

from datetime import UTC, datetime, timedelta

from argus.cluster.rank import rank_clusters
from argus.models import Cluster


def _cluster(make_article, n_articles: int, n_sources: int, age_hours: float = 0.5) -> Cluster:
    published = datetime.now(UTC) - timedelta(hours=age_hours)
    articles = [
        make_article(
            source=f"Source {i % n_sources}",
            url=f"https://example.com/{i}",
            published_at=published,
        )
        for i in range(n_articles)
    ]
    return Cluster(articles=articles)


def test_cross_verified_story_outranks_single_source_volume(make_article):
    # Real shape from 2026-08-27: a 42-article/1-source cluster nearly beat
    # a 15-article/10-source cluster under the old linear formula (46.6 vs
    # 49.0 -- a 5% margin on what should not have been close at all).
    volume_cluster = _cluster(make_article, n_articles=42, n_sources=1)
    cross_verified_cluster = _cluster(make_article, n_articles=15, n_sources=10)

    ranked = rank_clusters([volume_cluster, cross_verified_cluster])

    assert ranked[0] is cross_verified_cluster
    # Not just "wins" -- wins by a real margin, not a coin-flip margin.
    assert ranked[0].score > ranked[1].score * 1.5


def test_article_count_has_diminishing_returns(make_article):
    ten = _cluster(make_article, n_articles=10, n_sources=1)
    hundred = _cluster(make_article, n_articles=100, n_sources=1)

    ranked = rank_clusters([ten, hundred])
    ten_score, hundred_score = (
        (ranked[0].score, ranked[1].score) if ranked[0] is ten
        else (ranked[1].score, ranked[0].score)
    )

    # 10x the articles should not come close to 10x the score.
    assert hundred_score < ten_score * 2


def test_more_sources_always_beats_fewer_at_equal_article_count(make_article):
    two_sources = _cluster(make_article, n_articles=6, n_sources=2)
    six_sources = _cluster(make_article, n_articles=6, n_sources=6)

    ranked = rank_clusters([two_sources, six_sources])
    assert ranked[0] is six_sources
