# Architecture (v4)

## File-first, bounded synthesis

This source snapshot runs as a Python application. The single-container design
in ADR 0001 is historical context; no current Dockerfile is included.

Same file-first shape as v3 (ADR 0001) for collection/clustering. Synthesis
is no longer a single blind call -- it's a bounded-agent state machine
(ADR 0002).

```text
config/sources.yaml
      |
      v
collect -> normalize -> dedupe -> filter -> embed -> cluster -> rank
      |                                                            |
      v                                                            v
data/raw/*.jsonl                                          data/processed/*.jsonl
                                                                    |
                                                                    v
                                                    PENDING -> SYNTHESIZING -> EVAL_CHECK
                                                                    |
                                          PUBLISHED | NEEDS_REVIEW | STUB
                                                                    |
                                                                    v
                                                        reports/YYYY-MM-DD/*.md
```

## Why file-first

Unchanged from ADR 0001: the product is the daily set of articles. Files
give simple debugging, reproducible runs, and trivially publishable output.

## Resumability (added 2026-09-05)

The checkpoints above are read as well as written. A run reuses whatever
already exists for its date and recomputes only the rest:

```text
data/raw/<date>.jsonl        -> skip collect/normalize/dedupe/filter
data/processed/<date>.jsonl  -> skip cluster/rank
data/stories/<date>.jsonl    -> skip synthesis, per story
```

Stories are appended one at a time as each completes, keyed by cluster id,
because synthesis is the only stage that costs real time (up to
`ARGUS_LOCAL_LLM_TIMEOUT_SECONDS` per story on CPU) and the only one likely
to be interrupted. A run killed on story 12 of 15 resumes having paid for
11, not 0.

Staleness rule: a persisted story whose cluster id is no longer present in
the processed checkpoint is dropped and re-synthesized. Cluster IDs hash sorted
article URL hashes. They detect changed membership, not edits to source text,
prompts, model settings, or evaluation rules. Use `--fresh` after such changes.

`run(fresh=True)` (or `run_daily.py --fresh`) ignores all three and
recomputes from scratch.

## Data contracts

### Article

```json
{
  "id": "sha256(url)",
  "source": "AP News",
  "title": "Headline",
  "url": "https://...",
  "published_at": "2026-08-27T14:00:00Z",
  "summary": "Short feed summary/description",
  "fetched_at": "2026-08-27T19:00:00Z",
  "category_hint": "world"
}
```

### Cluster

```json
{
  "id": "sha256(sorted article ids)",
  "label": "Working title derived from top article",
  "category": "world",
  "articles": ["article_id_1", "article_id_2"],
  "sources": ["AP News", "BBC World"],
  "score": 8.4
}
```

### Story (post-synthesis)

```json
{
  "cluster_id": "sha256(...)",
  "title": "Generated headline",
  "body_markdown": "...",
  "citations": ["https://...", "https://..."],
  "review_status": "published | needs_review | stub",
  "synthesis_backend": "local:qwen3:14b | anthropic | stub",
  "synthesis_confidence": 0.8,
  "eval": {
    "cites_sources": true,
    "distinguishes_fact_from_synthesis": true,
    "no_unsupported_claims": true,
    "notes": "...",
    "passed": true
  }
}
```

## Stage responsibilities

Deterministic stages (unchanged from v3, no LLM decides these):

- **collect** -- fetch each configured feed (RSS/Atom) with a per-source
  timeout; failures are logged and skipped, not fatal.
- **normalize** -- map raw feed entries onto the Article contract.
- **dedupe** -- drop articles with a duplicate URL hash or near-duplicate
  title seen earlier in the same run.
- **filter** -- drop obviously low-value items (too short, no title, stale).
- **embed** -- local embeddings (`model2vec`) for clustering only.
- **cluster** -- deterministic: embedding similarity within a rolling time
  window.
- **rank** -- score by source diversity (linear), article count
  (log1p -- see ADR 0002), and recency.

The bounded-agent stage:

- **synthesize** -- one cluster in, one Story out, through a real state
  machine (`apps/pipeline/src/argus/synthesize/pipeline.py`):
  1. `context.prioritize_articles` caps the prompt to the most
     source-diverse/recent articles (fixes the real 42-article timeout
     ADR 0002 documents).
  2. `router.choose_model` picks a cloud model tier by cluster rank.
     Local inference uses one configured model at every rank, including
     the judge; no extra classification call is made.
  3. `backends.synthesize_via_*` returns structured output: title, body,
     and the model's own self-reported confidence.
  4. `eval.evaluate_story` judges the output against the quality bar
     below.
  5. Deterministic gate: passes eval AND confidence >= 0.6 -> PUBLISHED;
     otherwise NEEDS_REVIEW. No backend available -> STUB (a different
     category -- there's nothing to have failed a quality check on).

- **report** -- writes one markdown file per story to `reports/<date>/`,
  with an `index.md` that separates Published / Needs Review / Stub.

## Quality bar and its limits

The intended quality bar for a PUBLISHED report is:

- cite source links (`cites_sources`, deterministic check),
- distinguish established facts from model-written synthesis
  (`distinguishes_fact_from_synthesis`, LLM-judged),
- avoid unsupported claims (`no_unsupported_claims`, LLM-judged against the
  selected source titles and feed summaries),
- expose source diversity (surfaced via `rank.py`, not re-litigated here),
- be readable by a human in under 10 minutes per story (unchanged
  target, not currently machine-checked).

A story that fails any of the LLM-judged checks, or where the model's own
confidence was low, lands in NEEDS_REVIEW instead -- it's still written to
disk, just not presented as finished.

`PUBLISHED` means the local gate passed, not independently verified truth or
external publication. The citation check tests for a nonempty source-URL list;
it does not validate claim-level citations. The same local model synthesizes
and judges, and confidence is self-reported. Transport and JSON parsing errors
fail closed, but strict validation of decoded response types is still incomplete.
