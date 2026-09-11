"""Resume behavior.

Synthesis is the expensive stage (up to ARGUS_LOCAL_LLM_TIMEOUT_SECONDS per
story on CPU) and the one most likely to be interrupted, so the property
that matters is not "checkpoints exist" but "an interrupted run does not
re-pay for stories it already finished."
"""

from datetime import UTC, datetime

import pytest

from argus import checkpoints
from argus.models import Cluster, EvalResult, ReviewStatus, Story


@pytest.fixture
def run_date():
    return datetime.now(UTC).date()


def _story(cluster: Cluster, title="T", status=ReviewStatus.PUBLISHED) -> Story:
    return Story(
        cluster=cluster,
        title=title,
        body_markdown="B",
        citations=[a.url for a in cluster.articles],
        review_status=status,
        synthesis_backend="local:test-model",
        synthesis_confidence=0.9,
        eval=EvalResult(True, True, True, "ok", passed=True),
    )


def test_article_and_cluster_survive_a_round_trip(tmp_path, run_date, make_article):
    articles = [make_article(url=f"https://example.com/{i}") for i in range(3)]
    cluster = Cluster(articles=articles, label="L", category="world", score=4.2)

    checkpoints.write_jsonl(
        checkpoints.raw_path(tmp_path, run_date), [a.to_dict() for a in articles],
    )
    checkpoints.write_jsonl(
        checkpoints.processed_path(tmp_path, run_date), [cluster.to_dict()],
    )

    loaded_articles = checkpoints.load_articles(tmp_path, run_date)
    loaded_clusters = checkpoints.load_clusters(tmp_path, run_date, loaded_articles)

    assert {a.id for a in loaded_articles} == {a.id for a in articles}
    assert len(loaded_clusters) == 1
    assert loaded_clusters[0].id == cluster.id
    assert loaded_clusters[0].score == 4.2


def test_story_survives_a_round_trip(tmp_path, run_date, make_article):
    cluster = Cluster(articles=[make_article()], label="L")
    story = _story(cluster)

    checkpoints.append_jsonl(checkpoints.stories_path(tmp_path, run_date), story.to_dict())
    loaded = checkpoints.load_stories(tmp_path, run_date, [cluster])

    assert len(loaded) == 1
    assert loaded[0].cluster.id == cluster.id
    assert loaded[0].review_status is ReviewStatus.PUBLISHED
    assert loaded[0].eval is not None and loaded[0].eval.passed
    assert loaded[0].synthesis_confidence == 0.9


def test_missing_checkpoints_are_empty_not_an_error(tmp_path, run_date):
    assert checkpoints.load_articles(tmp_path, run_date) == []
    assert checkpoints.load_clusters(tmp_path, run_date, []) == []
    assert checkpoints.load_stories(tmp_path, run_date, []) == []


def test_truncated_final_line_does_not_discard_the_checkpoint(tmp_path, run_date, make_article):
    """The expected shape of "killed mid-append": the last record is half
    written. Everything before it is still good and must survive."""
    cluster = Cluster(articles=[make_article()], label="L")
    path = checkpoints.stories_path(tmp_path, run_date)
    checkpoints.append_jsonl(path, _story(cluster).to_dict())
    with path.open("a") as f:
        f.write('{"cluster_id": "abc", "title": "half-writ')

    loaded = checkpoints.load_stories(tmp_path, run_date, [cluster])
    assert len(loaded) == 1


def test_story_for_an_unknown_cluster_is_dropped(tmp_path, run_date, make_article):
    """If the processed checkpoint is regenerated, cluster IDs shift. A story
    whose cluster no longer exists is stale -- it must be dropped and
    re-synthesized, never silently reattached to a different cluster."""
    old_cluster = Cluster(articles=[make_article(url="https://example.com/old")])
    new_cluster = Cluster(articles=[make_article(url="https://example.com/new")])
    checkpoints.append_jsonl(
        checkpoints.stories_path(tmp_path, run_date), _story(old_cluster).to_dict(),
    )

    loaded = checkpoints.load_stories(tmp_path, run_date, [new_cluster])
    assert loaded == []


def test_latest_record_wins_for_a_recycled_cluster(tmp_path, run_date, make_article):
    """Stories are appended, never rewritten, so re-synthesizing a cluster
    leaves two records. The newer one is the current result."""
    cluster = Cluster(articles=[make_article()])
    path = checkpoints.stories_path(tmp_path, run_date)
    checkpoints.append_jsonl(path, _story(cluster, title="first").to_dict())
    checkpoints.append_jsonl(path, _story(cluster, title="second").to_dict())

    loaded = checkpoints.load_stories(tmp_path, run_date, [cluster])
    assert len(loaded) == 1
    assert loaded[0].title == "second"
