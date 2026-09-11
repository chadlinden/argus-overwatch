"""Routing tests.

The previous version asserted `choose_model(0).local_model ==
STRONG_LOCAL_MODEL` by importing the same constant the router returned, so
it held no matter what string that constant contained -- including a model
that could not serve /api/chat. The suite stayed green through the entire
period the strong local tier was broken. These tests assert behavior
instead: local routing does not vary, and the caller's model is honored.
"""

from argus.synthesize.router import (
    DEFAULT_LOCAL_MODEL,
    FAST_ANTHROPIC_MODEL,
    STRONG_ANTHROPIC_MODEL,
    TOP_TIER_RANK_CUTOFF,
    choose_model,
)


def test_local_model_does_not_vary_with_rank():
    """Local is single-tier: every rank gets the same local model."""
    models = {choose_model(rank).local_model for rank in (0, 1, 2, 3, 5, 100)}
    assert len(models) == 1


def test_caller_supplied_local_model_is_honored_at_every_rank():
    """The configured model reaches synthesis regardless of rank, so
    ARGUS_LOCAL_LLM_MODEL actually controls what runs."""
    for rank in (0, TOP_TIER_RANK_CUTOFF - 1, TOP_TIER_RANK_CUTOFF, 100):
        assert choose_model(rank, "some-other-model").local_model == "some-other-model"


def test_default_local_model_used_when_caller_supplies_nothing():
    assert choose_model(0).local_model == DEFAULT_LOCAL_MODEL


def test_rank_still_selects_a_cloud_tier():
    """Anthropic has two genuinely distinct models, so rank remains a real
    signal there even though the path is unfunded."""
    for rank in range(TOP_TIER_RANK_CUTOFF):
        choice = choose_model(rank)
        assert choice.cloud_tier == "strong"
        assert choice.anthropic_model == STRONG_ANTHROPIC_MODEL

    for rank in (TOP_TIER_RANK_CUTOFF, 100):
        choice = choose_model(rank)
        assert choice.cloud_tier == "fast"
        assert choice.anthropic_model == FAST_ANTHROPIC_MODEL


def test_cloud_tier_label_never_describes_the_local_model():
    """Regression guard for the bug this change fixed: a top-ranked story
    written locally used to log tier=strong while qwen3:14b wrote it. The
    label is now explicitly scoped to the cloud model."""
    choice = choose_model(0, "qwen3:14b")
    assert choice.cloud_tier == "strong"
    assert choice.local_model == "qwen3:14b"
    assert not hasattr(choice, "tier")
