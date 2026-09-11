"""Evaluate synthesized stories against the product's quality bar.

The bar comes straight from docs/ARCHITECTURE.md's "Quality bar" (v3's
copy, preserved in archive/): cite source links, distinguish facts from
synthesis, avoid unsupported claims, expose source diversity, readable in
under 10 minutes. Four of those five are structural/deterministic and don't
need a model at all -- only "distinguishes fact from synthesis" and "no
unsupported claims" require actually reading the source material and
judging faithfulness, which is the one place an LLM judge belongs here.
"""

from __future__ import annotations

import json
import logging

import httpx

from ..models import Article, EvalResult, SynthesisResult
from ..synthesize.router import DEFAULT_LOCAL_MODEL

logger = logging.getLogger("argus.eval.quality")

JUDGE_SYSTEM_PROMPT = """You are a strict fact-checker reviewing a generated news \
article against its source material. You are not the article's author -- be \
skeptical, not charitable.

Check two things:
1. distinguishes_fact_from_synthesis: does the article make clear what is
   reported by sources vs. the writer's own inference/framing? An article
   that states everything as flat fact with no attribution fails this.
2. no_unsupported_claims: does every specific claim (numbers, quotes, named
   entities, causal claims) trace back to something actually in the source
   material below? Any invented detail fails this, even a plausible-sounding
   one."""

JUDGE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "distinguishes_fact_from_synthesis": {"type": "boolean"},
        "no_unsupported_claims": {"type": "boolean"},
        "notes": {"type": "string"},
    },
    "required": ["distinguishes_fact_from_synthesis", "no_unsupported_claims", "notes"],
}

MIN_SOURCES_FOR_DIVERSITY = 1  # a single-source cluster can still pass -- rank.py penalizes it, eval doesn't re-litigate it


def _build_judge_prompt(story_body: str, source_articles: list[Article]) -> str:
    sources = "\n".join(
        f"### {a.source}\nTitle: {a.title}\nSummary: {a.summary or '(no summary)'}"
        for a in source_articles
    )
    return f"GENERATED ARTICLE:\n{story_body}\n\nSOURCE MATERIAL:\n{sources}"


def evaluate_story(
    result: SynthesisResult,
    citations: list[str],
    source_articles: list[Article],
    host: str = "http://localhost:11434",
    timeout: float = 120.0,
    model: str = DEFAULT_LOCAL_MODEL,
) -> EvalResult:
    # Deterministic checks first -- no reason to spend a model call on facts
    # the pipeline already knows for certain.
    cites_sources = len(citations) > 0

    if result.backend == "stub":
        # Stub output is a deterministic list of headlines, not synthesized
        # prose -- there's nothing for a fact-checker to judge here. It's
        # neither a pass nor a failure of quality; it's a different category
        # (ReviewStatus.STUB), so short-circuit rather than ask a model to
        # evaluate text nobody claimed was synthesized.
        return EvalResult(
            cites_sources=cites_sources,
            distinguishes_fact_from_synthesis=True,
            no_unsupported_claims=True,
            notes="stub output, not synthesized -- eval skipped",
            passed=True,
        )

    try:
        resp = httpx.post(
            f"{host.rstrip('/')}/api/chat",
            json={
                "model": model,  # Same local model as synthesis; the judge task is bounded.
                "stream": False,
                "think": False,
                "format": JUDGE_RESPONSE_SCHEMA,
                "messages": [
                    {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": _build_judge_prompt(result.body_markdown, source_articles)},
                ],
            },
            timeout=httpx.Timeout(connect=5.0, read=timeout, write=timeout, pool=timeout),
        )
        resp.raise_for_status()
        judged = json.loads(resp.json()["message"]["content"])
    except Exception as exc:  # noqa: BLE001 - judge failure must not crash the run
        logger.warning("eval judge call failed: %s", exc)
        # Fail closed: if the judge itself broke, don't silently pass the
        # story through to PUBLISHED. Route to review instead.
        return EvalResult(
            cites_sources=cites_sources,
            distinguishes_fact_from_synthesis=False,
            no_unsupported_claims=False,
            notes=f"judge call failed: {exc}",
            passed=False,
        )

    distinguishes = bool(judged.get("distinguishes_fact_from_synthesis", False))
    unsupported_ok = bool(judged.get("no_unsupported_claims", False))
    notes = str(judged.get("notes", ""))

    return EvalResult(
        cites_sources=cites_sources,
        distinguishes_fact_from_synthesis=distinguishes,
        no_unsupported_claims=unsupported_ok,
        notes=notes,
        passed=cites_sources and distinguishes and unsupported_ok,
    )
