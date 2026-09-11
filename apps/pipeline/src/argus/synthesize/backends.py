"""LLM backends for synthesis. Structured output + a self-reported confidence
signal, not raw prose -- the confidence field lets the eval gate in pipeline.py
distinguish "the model wasn't sure" from "the model was confidently wrong."

Verified: local Ollama path, against real clusters, 2026-08-27 (see
docs/adr/0002). NOT verified: Anthropic path -- ANTHROPIC_API_KEY has a
zero balance right now. Written correctly per the API docs, same
"written but unverified" honesty the v3 pipeline already practiced for its
own first synthesis implementation (see archive/.../docs/ROADMAP.md).
"""

from __future__ import annotations

import json
import logging

import httpx

from ..models import Article, SynthesisResult

logger = logging.getLogger("argus.synthesize.backends")

SYSTEM_PROMPT = """You are a news synthesis assistant. Given a cluster of articles \
about the same story from multiple sources, write ONE clear, neutral article \
covering what happened. Rules:
- Distinguish established facts (reported by sources) from any inference you make.
- Do not invent facts, quotes, or figures not present in the provided material.
- Attribute claims by source name when sources disagree or when it adds credibility \
(e.g. "according to Reuters").
- Be concise: 150-300 words.
- confidence is YOUR self-assessment of how complete and well-supported this \
article is given the source material -- not a rhetorical flourish. A confident \
tone with low actual confidence is worse than an honest low number."""

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "body_markdown": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["title", "body_markdown", "confidence"],
}


def _build_user_prompt(articles: list[Article]) -> str:
    n_sources = len({a.source for a in articles})
    parts = [f"Story cluster: {len(articles)} articles (context-prioritized) from {n_sources} sources.\n"]
    for a in sorted(articles, key=lambda x: x.published_at):
        parts.append(f"### {a.source}\nTitle: {a.title}\nSummary: {a.summary or '(no summary provided)'}\n")
    return "\n".join(parts)


def synthesize_via_local(
    articles: list[Article],
    model: str,
    host: str = "http://localhost:11434",
    timeout: float = 180.0,
) -> SynthesisResult | None:
    try:
        resp = httpx.post(
            f"{host.rstrip('/')}/api/chat",
            json={
                "model": model,
                "stream": False,
                "think": False,  # reasoning preamble is pure overhead for fixed-format writing
                "format": RESPONSE_SCHEMA,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": _build_user_prompt(articles)},
                ],
            },
            timeout=httpx.Timeout(connect=5.0, read=timeout, write=timeout, pool=timeout),
        )
        resp.raise_for_status()
        parsed = json.loads(resp.json()["message"]["content"])
    except (httpx.HTTPError, KeyError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("local synthesis (%s) failed: %s", model, exc)
        return None

    try:
        confidence = max(0.0, min(1.0, float(parsed["confidence"])))
    except (KeyError, TypeError, ValueError):
        confidence = 0.0  # missing/malformed confidence is itself low confidence

    return SynthesisResult(
        title=parsed.get("title", "").strip(),
        body_markdown=parsed.get("body_markdown", "").strip(),
        confidence=confidence,
        backend=f"local:{model}",
    )


def synthesize_via_anthropic(
    articles: list[Article],
    api_key: str,
    model: str,
) -> SynthesisResult | None:
    """NOT verified against a real call -- see module docstring."""
    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic package not installed; skipping. pip install -e '.[llm]'")
        return None

    tool = {
        "name": "write_story",
        "description": "Submit the synthesized story.",
        "input_schema": RESPONSE_SCHEMA,
    }

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            # Prompt caching: SYSTEM_PROMPT is byte-identical across every
            # cluster in a run (and across runs, until this file changes).
            # Marking it cacheable means only the per-cluster user turn is
            # paid for at full price after the first call.
            system=[
                {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
            ],
            tools=[tool],
            tool_choice={"type": "tool", "name": "write_story"},
            messages=[{"role": "user", "content": _build_user_prompt(articles)}],
        )
        tool_use = next(b for b in response.content if b.type == "tool_use")
        parsed = tool_use.input
    except Exception as exc:  # noqa: BLE001 - a failed call must not crash the run
        logger.warning("anthropic synthesis failed: %s", exc)
        return None

    try:
        confidence = max(0.0, min(1.0, float(parsed["confidence"])))
    except (KeyError, TypeError, ValueError):
        confidence = 0.0

    return SynthesisResult(
        title=str(parsed.get("title", "")).strip(),
        body_markdown=str(parsed.get("body_markdown", "")).strip(),
        confidence=confidence,
        backend="anthropic",
    )
