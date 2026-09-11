"""The behavior resume exists for: an interrupted run does not re-pay for
stories it already finished, and a crash mid-synthesis keeps what completed.
"""

import pytest

import argus.synthesize.pipeline as pipeline_mod
from argus.models import Cluster, EvalResult, ReviewStatus, Story, SynthesisResult


@pytest.fixture
def clusters(make_article):
    return [
        Cluster(articles=[make_article(url=f"https://example.com/{i}")], label=f"C{i}")
        for i in range(4)
    ]


@pytest.fixture(autouse=True)
def _passing_eval(monkeypatch):
    monkeypatch.setattr(
        pipeline_mod,
        "evaluate_story",
        lambda *a, **kw: EvalResult(True, True, True, "ok", passed=True),
    )


def _fake_backend(calls):
    def fake_local(articles, model, host, timeout):
        calls.append(model)
        return SynthesisResult(
            title="T", body_markdown="B", confidence=0.9, backend=f"local:{model}"
        )

    return fake_local


def _done_story(cluster: Cluster) -> Story:
    return Story(
        cluster=cluster,
        title="already done",
        body_markdown="B",
        citations=[],
        review_status=ReviewStatus.PUBLISHED,
        synthesis_backend="local:test",
        synthesis_confidence=0.9,
        eval=EvalResult(True, True, True, "ok", passed=True),
    )


def test_completed_stories_are_not_resynthesized(monkeypatch, clusters):
    calls = []
    monkeypatch.setattr(pipeline_mod, "synthesize_via_local", _fake_backend(calls))

    done = {
        clusters[0].id: _done_story(clusters[0]),
        clusters[2].id: _done_story(clusters[2]),
    }
    stories = pipeline_mod.run_clusters(
        clusters,
        api_key=None,
        max_stories=10,
        backend="local",
        done_stories=done,
    )

    # Four clusters, two already done -> only two model calls.
    assert len(calls) == 2
    assert len(stories) == 4
    assert stories[0].title == "already done"
    assert stories[2].title == "already done"
    assert stories[1].title == "T"


def test_each_story_is_persisted_as_it_completes(monkeypatch, clusters):
    """Not batched at the end: the next story may take minutes, so anything
    already finished must already be on disk."""
    monkeypatch.setattr(pipeline_mod, "synthesize_via_local", _fake_backend([]))
    persisted = []

    pipeline_mod.run_clusters(
        clusters,
        api_key=None,
        max_stories=10,
        backend="local",
        on_story=lambda s: persisted.append(s.cluster.id),
    )

    assert persisted == [c.id for c in clusters]


def test_a_crash_mid_synthesis_keeps_the_stories_already_written(monkeypatch, clusters):
    """The whole point. Story 3 blows up; stories 1 and 2 stay persisted."""
    persisted = []

    def exploding_backend(articles, model, host, timeout):
        if len(persisted) >= 2:
            raise RuntimeError("inference died")
        return SynthesisResult(
            title="T", body_markdown="B", confidence=0.9, backend="local:x"
        )

    monkeypatch.setattr(pipeline_mod, "synthesize_via_local", exploding_backend)

    with pytest.raises(RuntimeError):
        pipeline_mod.run_clusters(
            clusters,
            api_key=None,
            max_stories=10,
            backend="local",
            on_story=lambda s: persisted.append(s.cluster.id),
        )

    assert persisted == [clusters[0].id, clusters[1].id]


def test_resumed_stories_keep_their_original_rank_position(monkeypatch, clusters):
    """Rank is positional. A resumed story must land in the same slot it was
    synthesized under, or the report ordering silently changes on resume."""
    monkeypatch.setattr(pipeline_mod, "synthesize_via_local", _fake_backend([]))

    done = {clusters[3].id: _done_story(clusters[3])}
    stories = pipeline_mod.run_clusters(
        clusters,
        api_key=None,
        max_stories=10,
        backend="local",
        done_stories=done,
    )

    assert [s.cluster.id for s in stories] == [c.id for c in clusters]
    assert stories[3].title == "already done"


def test_max_stories_still_bounds_the_run_when_resuming(monkeypatch, clusters):
    monkeypatch.setattr(pipeline_mod, "synthesize_via_local", _fake_backend([]))

    stories = pipeline_mod.run_clusters(
        clusters,
        api_key=None,
        max_stories=2,
        backend="local",
        done_stories={clusters[0].id: _done_story(clusters[0])},
    )

    assert len(stories) == 2
