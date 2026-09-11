"""The synthesis state machine's branching logic, tested against fake backends.

You cannot reliably provoke an exact model output on demand, so the
deterministic gate gets tested as a unit, not by hoping a live call behaves
a certain way. Live-model behavior is what the manual verification runs
(ADR 0002) are for.
"""

from datetime import UTC, datetime

import argus.synthesize.pipeline as pipeline_mod
from argus.models import Cluster, EvalResult, ReviewStatus, SynthesisResult


def _cluster(make_article) -> Cluster:
    return Cluster(articles=[make_article(published_at=datetime.now(UTC))])


def test_high_confidence_and_passing_eval_publishes(monkeypatch, make_article):
    monkeypatch.setattr(
        pipeline_mod, "synthesize_via_local",
        lambda *a, **kw: SynthesisResult(title="T", body_markdown="B", confidence=0.9, backend="local:test"),
    )
    monkeypatch.setattr(
        pipeline_mod, "evaluate_story",
        lambda *a, **kw: EvalResult(True, True, True, "looks good", passed=True),
    )

    story = pipeline_mod.run_cluster(_cluster(make_article), rank=5, api_key=None, backend="local")

    assert story.review_status == ReviewStatus.PUBLISHED


def test_low_confidence_forces_review_even_if_eval_passes(monkeypatch, make_article):
    # This is the case that matters most: the model can be right and still
    # not be trusted, same as escalation.py's high-value-but-correct case.
    monkeypatch.setattr(
        pipeline_mod, "synthesize_via_local",
        lambda *a, **kw: SynthesisResult(title="T", body_markdown="B", confidence=0.3, backend="local:test"),
    )
    monkeypatch.setattr(
        pipeline_mod, "evaluate_story",
        lambda *a, **kw: EvalResult(True, True, True, "looks good", passed=True),
    )

    story = pipeline_mod.run_cluster(_cluster(make_article), rank=5, api_key=None, backend="local")

    assert story.review_status == ReviewStatus.NEEDS_REVIEW


def test_failed_eval_forces_review_even_with_high_confidence(monkeypatch, make_article):
    monkeypatch.setattr(
        pipeline_mod, "synthesize_via_local",
        lambda *a, **kw: SynthesisResult(title="T", body_markdown="B", confidence=0.95, backend="local:test"),
    )
    monkeypatch.setattr(
        pipeline_mod, "evaluate_story",
        lambda *a, **kw: EvalResult(True, False, True, "invented a quote", passed=False),
    )

    story = pipeline_mod.run_cluster(_cluster(make_article), rank=5, api_key=None, backend="local")

    assert story.review_status == ReviewStatus.NEEDS_REVIEW


def test_no_backend_available_is_stub_not_needs_review(monkeypatch, make_article):
    # STUB is a different category from NEEDS_REVIEW -- there's no synthesis
    # to have failed an eval on. evaluate_story should never even be called.
    monkeypatch.setattr(pipeline_mod, "synthesize_via_local", lambda *a, **kw: None)
    called = []
    monkeypatch.setattr(pipeline_mod, "evaluate_story", lambda *a, **kw: called.append(1))

    story = pipeline_mod.run_cluster(_cluster(make_article), rank=5, api_key=None, backend="local")

    assert story.review_status == ReviewStatus.STUB
    assert called == []


def test_configured_local_model_is_the_one_called(monkeypatch, make_article):
    """Replaces test_strong_tier_failure_deescalates_to_fast_model.

    That test asserted the call sequence [STRONG_LOCAL_MODEL,
    FAST_LOCAL_MODEL] -- it pinned the two-tier design in place, including
    the guaranteed-failing first call. Local is single-tier now, so the
    property worth protecting is the opposite one: exactly one local call
    is made, using exactly the model the caller configured, at any rank.
    """
    calls = []

    def fake_local(articles, model, host, timeout):
        calls.append(model)
        return SynthesisResult(title="T", body_markdown="B", confidence=0.9, backend=f"local:{model}")

    monkeypatch.setattr(pipeline_mod, "synthesize_via_local", fake_local)
    monkeypatch.setattr(
        pipeline_mod, "evaluate_story",
        lambda *a, **kw: EvalResult(True, True, True, "ok", passed=True),
    )

    # rank=0 is the old "strong tier" position; it must not try a second model.
    story = pipeline_mod.run_cluster(
        _cluster(make_article), rank=0, api_key=None, backend="local",
        local_model="configured-model",
    )

    assert calls == ["configured-model"]
    assert story.review_status == ReviewStatus.PUBLISHED
    assert story.synthesis_backend == "local:configured-model"


def test_judge_uses_the_same_model_as_synthesis(monkeypatch, make_article):
    """The judge used to hold its own hardcoded reference to the fast-tier
    constant, so a configured synthesis model and the evaluator could
    silently diverge. They are threaded from one place now.
    """
    seen = {}

    monkeypatch.setattr(
        pipeline_mod, "synthesize_via_local",
        lambda articles, model, host, timeout: SynthesisResult(
            title="T", body_markdown="B", confidence=0.9, backend=f"local:{model}",
        ),
    )

    def fake_eval(*args, **kwargs):
        seen["model"] = kwargs.get("model")
        return EvalResult(True, True, True, "ok", passed=True)

    monkeypatch.setattr(pipeline_mod, "evaluate_story", fake_eval)

    pipeline_mod.run_cluster(
        _cluster(make_article), rank=0, api_key=None, backend="local",
        local_model="configured-model",
    )

    assert seen["model"] == "configured-model"


def test_judge_gets_the_configured_timeout(monkeypatch, make_article):
    """The judge was called without a timeout, so it always used
    evaluate_story's 120s default while synthesis got
    ARGUS_LOCAL_LLM_TIMEOUT_SECONDS. On the 2026-09-10 run both NEEDS_REVIEW
    stories were judge timeouts on stories with 0.8+ confidence.
    """
    seen = {}

    monkeypatch.setattr(
        pipeline_mod, "synthesize_via_local",
        lambda articles, model, host, timeout: SynthesisResult(
            title="T", body_markdown="B", confidence=0.9, backend=f"local:{model}",
        ),
    )

    def fake_eval(*args, **kwargs):
        seen["timeout"] = kwargs.get("timeout")
        return EvalResult(True, True, True, "ok", passed=True)

    monkeypatch.setattr(pipeline_mod, "evaluate_story", fake_eval)

    pipeline_mod.run_cluster(
        _cluster(make_article), rank=0, api_key=None, backend="local",
        local_timeout=600.0,
    )

    assert seen["timeout"] == 600.0
