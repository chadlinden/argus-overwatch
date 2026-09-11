# Evaluation strategy

Argus needs a stable benchmark before clustering, ranking, synthesis, or model
changes can be judged as improvements. Live runs show whether the system works;
the benchmark shows whether a change made the product better.

## First benchmark: cluster quality

Clustering is the first quality boundary. A polished synthesis cannot repair a
cluster that combines unrelated events, and split clusters create duplicate
stories that waste reading time.

Human-readable cases live in `evals/golden/cluster_cases.jsonl`. Executable
pairwise constraints live in `evals/golden/cluster_constraints.jsonl`. Each
constraint records:

- two immutable article IDs and their run date,
- whether they must be linked or cannot be linked,
- why that action matches the product goal,
- whether the judgment is proposed or accepted.

Proposed cases are engineering recommendations. They become accepted only after
product review, because boundaries such as “event report versus causal analysis”
are editorial decisions rather than objective facts.

Run accepted constraints from `apps/pipeline/`:

This requires the original `data/processed/<run-date>.jsonl` checkpoints.
They are private runtime artifacts and are not included in the public snapshot.
The constraint definitions are included to document the benchmark; a new run
against today's feeds cannot reconstruct those historical article IDs.
`pytest` exercises the constraint evaluator with self-contained fixtures.

```bash
uv run python scripts/evaluate_cluster_constraints.py
```

Use `--status all` to inspect proposed cases as well. Accepted failures return
a non-zero exit code so the evaluator can become a CI gate after the known
baseline failures are fixed.

## Acceptance criteria

A clustering change must:

1. fix at least one accepted failure case,
2. preserve every accepted `keep` case,
3. introduce no new false merges in the benchmark,
4. report results case by case rather than only as one aggregate score.

The benchmark starts small on purpose. Five carefully chosen real failures and
boundary cases are more useful than hundreds of synthetic examples nobody has
reviewed.

## Later benchmark layers

Once cluster behavior is measurable, add separate datasets for:

- ranking: which clusters belong in a ten-minute briefing,
- synthesis: essential facts, disagreements, and forbidden unsupported claims,
- publication: expected `published` versus `needs_review` verdicts,
- continuity: whether a report correctly identifies what changed since yesterday.

These stay separate because a single end-to-end score would hide which stage
actually regressed.
