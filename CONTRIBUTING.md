# Contributing

## Repo shape

This is a monorepo. `apps/pipeline` is the only working app right now — see
the root [`README.md`](README.md) for the full layout and
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for how the pipeline stages
fit together.

## Working on `apps/pipeline`

```bash
cd apps/pipeline
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[llm,dev]"
```

Run tests: `pytest` (from `apps/pipeline`).
Run the pipeline: `python apps/pipeline/scripts/run_daily.py` (from the repo root).

## Principles (read before adding anything)

- **Deterministic before probabilistic.** Collection, dedupe, filtering, and
  clustering are pure functions with no API cost. LLMs label/explain and
  synthesize — they don't decide article membership or run silently in a
  path that costs money without an explicit opt-in.
- **No speculative infrastructure.** See [ADR 0001](docs/adr/0001-single-container-no-web-app-for-v1.md).
  If you're adding a new service, a new framework, or a new persistent
  process, that needs an ADR justifying it first, not just a PR.
- **File-first output.** The product is the report. Don't hide behind a
  database or a UI if the underlying markdown isn't good.
- **Every generated article must cite its sources** and distinguish
  reported fact from model synthesis. See the quality bar in
  `docs/ARCHITECTURE.md`.

## Adding an ADR

New architectural decisions (new dependency category, new service, changing
a data contract in a breaking way) get a numbered file in `docs/adr/`,
following the shape of `0001-single-container-no-web-app-for-v1.md`: Status,
Context, Decision, Consequences.
