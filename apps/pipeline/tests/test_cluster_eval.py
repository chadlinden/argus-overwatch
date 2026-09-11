import pytest

from argus.eval.clusters import ClusterConstraint, article_cluster_index, evaluate_constraint


def _constraint(relation: str) -> ClusterConstraint:
    return ClusterConstraint.from_dict(
        {
            "case_id": "case-1",
            "run_date": "2026-08-27",
            "relation": relation,
            "left_article_id": "article-a",
            "right_article_id": "article-b",
            "status": "accepted",
            "reason": "test",
        }
    )


def test_must_link_passes_when_articles_share_a_cluster():
    result = evaluate_constraint(
        _constraint("must_link"),
        {"article-a": "cluster-1", "article-b": "cluster-1"},
    )
    assert result.passed


def test_cannot_link_passes_when_articles_are_separate():
    result = evaluate_constraint(
        _constraint("cannot_link"),
        {"article-a": "cluster-1", "article-b": "cluster-2"},
    )
    assert result.passed


def test_missing_article_fails_with_an_explicit_reason():
    result = evaluate_constraint(_constraint("must_link"), {"article-a": "cluster-1"})
    assert not result.passed
    assert "article-b" in result.detail


def test_article_cannot_belong_to_two_clusters():
    with pytest.raises(ValueError, match="belongs to both"):
        article_cluster_index(
            [
                {"id": "cluster-1", "articles": ["article-a"]},
                {"id": "cluster-2", "articles": ["article-a"]},
            ]
        )
