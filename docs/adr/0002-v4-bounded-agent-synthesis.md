# ADR 0002: v4 rebuild — synthesis becomes a bounded-agent state machine

## Status

Accepted (2026-08-27).

Snapshot note (2026-09-11): this ADR preserves dated observations, including
superseded model routing and test counts. Archived source, machine-specific
run data, and previous Git history are not part of the public snapshot.
The September 5 amendment below describes current local routing; see the
current README and roadmap for setup, verification, and remaining limits.

## Context

This is the fourth rebuild of Argus Overwatch (v3: `archive/2026-08-27-v3-file-first-pipeline/`,
see its own `docs/adr/0001`). Unlike the prior rebuilds, this one is not a
response to v3 failing -- a real run the same day proved v3's deterministic
stages correct (904 articles -> 476 clusters, real cross-source merging).
The rebuild is deliberate: the synthesis stage needed explicit boundaries,
measurable quality checks, and reliable failure handling before the pipeline
could publish useful output.

## Decision

Keep collect/normalize/dedupe/filter/embed/cluster exactly as deterministic
as v3 made them -- LLMs still never decide cluster membership. Two real
things changed:

1. **`rank.py`'s formula was fixed, not just ported.** v3's live run the
   same day exposed a real bug: a 42-article single-source cluster (46.6)
   nearly outranked a genuinely cross-verified 10-source/15-article story
   (49.0) -- article count was linear and swamped source diversity, the
   signal this product is actually named after. Fixed to `log1p(count)`
   (diminishing returns) instead of raw count.

2. **`synthesize` is now a real state machine, not a single blind call.**
   `PENDING -> SYNTHESIZING -> EVAL_CHECK -> PUBLISHED | NEEDS_REVIEW | STUB`.
   The model makes one bounded decision (write the story, self-report
   confidence); deterministic code decides whether that's trustworthy
   enough to publish. There is no code path from SYNTHESIZING straight to
   PUBLISHED. Concretely, this pulled in:
   - **Context prioritization** (`synthesize/context.py`): caps prompt
     size to the 8 most source-diverse/recent articles per cluster --
     fixes a real bug the same live run exposed (the 42-article cluster
     timed out synthesis at 180s on every attempt).
   - **Model routing** (`synthesize/router.py`): top-3-ranked clusters get
     a stronger model, the rest get a faster one. Static, tier-based --
     the ranking the pipeline already computes IS the routing signal, no
     extra classification call needed.
   - **Prompt caching** (`synthesize/backends.py`, Anthropic path): the
     system prompt is cached (`cache_control`), since it's byte-identical
     across every call in a run. Written correctly per the API docs, not
     yet verified against a real call -- `ANTHROPIC_API_KEY` has a zero
     balance as of this writing. Same "written but unverified" honesty v3
     already practiced for its first synthesis implementation.
   - **Real evals** (`eval/quality.py`): every synthesized story is judged
     against `ARCHITECTURE.md`'s own quality bar (cites sources,
     distinguishes fact from synthesis, no unsupported claims) before it
     can be marked PUBLISHED. This is the ROADMAP item v3 stated but never
     did ("verify real synthesis output quality against real clusters").
   - **Escalation gate**: low eval score OR low model self-reported
     confidence -> `NEEDS_REVIEW`, not silently published. Fail-closed:
     if the judge call itself fails, that also routes to NEEDS_REVIEW,
     never a silent pass-through.

## A real finding from building this, not a hypothetical

`qwen:72b` was picked as the "strong" local-routing tier without checking
its capabilities first -- `ollama show qwen:72b` returns `capabilities:
None`, no chat template. It's not chat-capable at all; every real call to
it returned `400 "does not support chat"`. Fixed with a de-escalation
fallback (strong model unavailable -> retry on the known-working fast
model, mirroring the routing lab's cheap-then-strong escalation pattern,
run in reverse) rather than either (a) silently pointing both tiers at the
same model, or (b) letting an unavailable "strong" tier drop top-ranked
stories to stub. Verified live: both top-ranked clusters correctly
de-escalated and produced real output; one published, one correctly
NEEDS_REVIEW because the eval judge call itself timed out under load --
the fail-closed path working under a genuine failure.

## Consequences

- Every synthesized story now carries a real trust signal
  (`review_status`, `synthesis_confidence`, `eval`) instead of a bare
  `synthesized: bool`. `reports/<date>/index.md` separates Published from
  Needs Review from Stub -- nothing is silently hidden, same file-first
  transparency principle as ADR 0001.
- No second "strong" local model currently works for chat. Routing to a
  stronger tier is real machinery with nothing real to route to yet on
  this machine -- the de-escalation fallback covers it honestly, but a
  real strong-tier local model (or working Anthropic credits) is still an
  open item, not a "done."
  **SUPERSEDED 2026-09-05 -- see the amendment below.**
- Test suite is not yet ported/rewritten for v4 (v3 had 21 passing tests;
  v4 has none yet as of this ADR). Tracked as immediate next work, not
  silently skipped.


## Amendment, 2026-09-05: local routing collapsed to a single tier

The de-escalation fallback above was the right call in the moment but it
stopped being honest once it was the permanent state rather than a
stopgap. Three things forced the change:

1. `qwen:72b` is not merely missing a chat template. It is 41GB against
   32GB of RAM on the available machine, so it could never have loaded.
   The earlier GPU host was no longer available.
2. `ANTHROPIC_API_KEY` still returns `credit balance is too low`
   (re-verified 2026-09-05), so the cloud tier cannot substitute.
3. Consequently *both* tiers resolved to `qwen3:14b` at runtime, while
   `choose_model` still returned `tier="strong"` and the log line printed
   it. `Story.synthesis_backend` recorded `local:qwen3:14b`. The report and
   the log disagreed about what wrote the story.

The cost was one guaranteed-failing HTTP round trip per top-ranked story,
plus a log that could not be trusted.

What changed:

- `router.py` has one local model, `DEFAULT_LOCAL_MODEL`, overridable via
  `ARGUS_LOCAL_LLM_MODEL`. Rank no longer selects a local model.
- `ModelChoice.tier` is renamed `cloud_tier` and scoped to the Anthropic
  model only, so the label can no longer describe a story a local model
  wrote. Rank still picks haiku vs sonnet, because those are two real
  models; that path is unfunded, not fake.
- The de-escalation block in `synthesize/pipeline.py` is deleted. With one
  local model there is nothing to de-escalate to, and the guard was a
  string comparison that fired on *any* failure, not the
  missing-chat-template case it was written for. If a second local model
  becomes real, reintroduce it with a capability check.
- `ARGUS_LOCAL_LLM_MODEL` is now actually read. It was documented in
  `.env.example` but dropped from the v4 config plumbing, so setting it
  did nothing.
- The eval judge takes the model as a parameter instead of holding a
  second hardcoded reference, so synthesis and evaluation cannot diverge.

Note this changes no quality behavior. The escalation gate never consulted
tier -- `PUBLISHED` still requires `eval_result.passed` and confidence
>= 0.6. Collapsing the tiers cannot weaken the publish bar. The only
behavioral change is one fewer doomed HTTP call per top-ranked story.

Test consequence worth recording: `test_router.py` asserted
`choose_model(0).local_model == STRONG_LOCAL_MODEL` while importing that
same constant, so it passed for the entire period the strong tier was
broken. It has been rewritten to assert behavior (local does not vary with
rank; the configured model is honored) rather than restating a constant.
Suite went from 13 to 21 passing.
