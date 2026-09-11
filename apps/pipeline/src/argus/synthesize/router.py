"""Model routing for synthesis: static, tier-based, deterministic.

Routing by task tier is easier to reason about and test than routing by an
LLM's "is this hard" classification, and this pipeline already has a tier
signal available -- cluster rank. The top story of
the day gets read by more people and is worth a stronger model; story #40
of 40 doesn't need the same spend. No extra model call to decide this,
because the ranking the pipeline already computes is the routing signal.

Local routing is SINGLE-TIER as of 2026-09-05. There is exactly one local
model, supplied by config, and rank does not change it. Rank still selects
an Anthropic tier, because those two models are real and distinct -- that
path is simply unfunded right now.

Why single-tier locally: qwen:72b was the intended strong tier and cannot
serve /api/chat at all (no chat template, see docs/adr/0002). It is also
41GB against 32GB of RAM on the current machine, so it could not load even
if the template existed. Claiming a strong local tier cost one
guaranteed-failing HTTP call per top-ranked story and made the logs report
`tier=strong` for stories the fast model actually wrote.
"""

from __future__ import annotations

from dataclasses import dataclass

# The single local model. Overridden by ARGUS_LOCAL_LLM_MODEL; this constant
# is only the fallback used when config supplies nothing.
DEFAULT_LOCAL_MODEL = "qwen3:14b"

# Anthropic tiers, for when ANTHROPIC_API_KEY has a real balance again.
# These two are genuinely different models, so rank-based selection is
# meaningful here even though local routing is not.
FAST_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
STRONG_ANTHROPIC_MODEL = "claude-sonnet-5"

TOP_TIER_RANK_CUTOFF = 3  # top-N clusters by rank get the strong cloud model


@dataclass(frozen=True, slots=True)
class ModelChoice:
    local_model: str
    anthropic_model: str
    cloud_tier: str  # "strong" | "fast" -- describes the ANTHROPIC model only


def choose_model(rank: int, local_model: str = DEFAULT_LOCAL_MODEL) -> ModelChoice:
    """rank is 0-indexed position in the ranked cluster list, not the score.

    `local_model` is returned unchanged regardless of rank: local is
    single-tier. Rank selects the Anthropic tier only.
    """
    if rank < TOP_TIER_RANK_CUTOFF:
        return ModelChoice(local_model, STRONG_ANTHROPIC_MODEL, cloud_tier="strong")
    return ModelChoice(local_model, FAST_ANTHROPIC_MODEL, cloud_tier="fast")
