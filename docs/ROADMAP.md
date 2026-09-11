# Roadmap (v4)

This roadmap tracks product and engineering work for the pipeline.

## Done

- [x] Ported collect -> normalize -> dedupe -> filter -> embed -> cluster
      from v3, unchanged logic (already verified correct: real cross-source
      merging on 2026-08-27's live data).
- [x] **Fixed a real rank.py bug**: article count was linear and could
      nearly outrank source diversity (a 42-article single-source cluster
      almost beat a genuine 10-source story). Now log1p-scaled. Regression
      test uses the real numbers from the bug (`tests/test_rank.py`).
- [x] Synthesis rebuilt as a real state machine: context prioritization,
      model routing, structured output + confidence, real evals, an
      escalation/review gate. See `docs/adr/0002`.
- [x] Verified live against real 2026-08-27 news data: context capping,
      synthesis, evaluation, PUBLISHED and NEEDS_REVIEW paths all reached.
      One NEEDS_REVIEW path was caused by a genuine judge-call timeout under
      load rather than a staged failure.
- [x] Real bug found and fixed while verifying: `qwen:72b` was selected as a
      "strong" local model before its actual capabilities were checked. It
      does not support chat and was too large for the machine anyway. The
      temporary fallback was later removed and local inference was collapsed
      to one real configured model instead of preserving a misleading tier.
- [x] **Resumable runs (2026-09-05).** JSONL checkpoints are now read as well
      as written. Collection/clustering work is reused and synthesized stories
      persist individually so interrupted runs resume from completed work.
      Verified end-to-end: a second run over the same date performed 0 fetches
      and 0 inference calls.
- [x] Local model configuration is threaded consistently through synthesis and
      evaluation. Regression coverage protects against the evaluator silently
      using a different hardcoded model.
- [x] The configured inference timeout is now passed to both synthesis and the
      evaluation judge. This fixes a real 2026-09-10 failure where the judge
      silently used its shorter default timeout.
- [x] Config/data/report paths resolve from the repository root instead of the
      caller's working directory. Regression tests cover default, relative and
      absolute path behavior.
- [x] Test suite covers ranking, context prioritization, routing behavior,
      synthesis state transitions, review gating, resumability/config behavior,
      and the model/timeout regressions above. The unchanged portfolio source
      was checked on 2026-09-11 with 35 passing tests and a clean Ruff run.
- [x] GitHub Actions runs Ruff and pytest on pushes and pull requests.
- [x] ADRs document the major architecture changes and the failures that caused
      them rather than rewriting the history after the fact.
- [x] Public export includes evaluation definitions and contributor docs while
      omitting archived implementations, runtime artifacts, and unfinished MCP code.
- [x] Corrected local setup instructions: `.env` must be explicitly exported.
- [x] Added a saved-story extraction helper that preserves real outcomes and
      does not invoke a model; behavior is covered with controlled test inputs.

## Next

- [ ] Verify the Anthropic path (prompt caching included) against a funded real
      call. The code exists, but this path has not been claimed as verified.
- [ ] Add and verify current container packaging. No Dockerfile is included in
      this snapshot. An image would need the correct repository layout and a
      deliberate embedding-model cache/download strategy.
- [x] Included one September 10 v4 report with preserved provenance, reconstructed
      source context, and a review documenting attribution issues missed by the judge.
- [ ] Strictly validate decoded synthesis/judge response types before treating
      them as a valid result; requested JSON schemas are not application validation.
- [ ] Improve evaluation independence and calibrate confidence against outcomes.
- [ ] Expand `config/sources.yaml` beyond the current 27 verified feeds.
- [ ] Decide whether NEEDS_REVIEW has become the concrete reason to add a web
      review surface. ADR 0001 intentionally defers a web app until files stop
      being sufficient for an actual workflow.

## Later (not committed to)

- [ ] Cross-day story tracking ("what changed since yesterday").
- [ ] A second, independent eval dimension beyond fact-checking (for example,
      readability-under-10-minutes, currently unmeasured).
- [ ] Source-diversity scoring improvements beyond the log1p fix, once more
      real output has been reviewed.
