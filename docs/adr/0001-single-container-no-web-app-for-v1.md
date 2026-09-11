# ADR 0001: Single container, no web app, for v1

## Status

Accepted (2026-08-25).

## Context

This is the third rebuild of Argus Overwatch. Git history on this repo shows
the previous iteration sprawled into a multi-service stack: a Dagster
orchestration layer, a Discord bot, an auth system, a dashboard MVP,
websocket infra, Postgres+pgvector, and a Next.js web app — most of it never
finished (dozens of abandoned branches). The project's own README had
already drifted from its stated "no web app" principle by the time it was
rebuilt.

## Decision

v1 is a single Docker container running a daily batch pipeline that writes
markdown files. No database service, no web server, no orchestration
framework, no user accounts.

## Consequences

- Output is `reports/<date>/*.md` — reviewable, diffable, publishable, and
  requires zero infrastructure to consume.
- A frontend (`apps/web`) is deliberately deferred. It's scaffolded as a
  design doc, not built, so the monorepo shape is ready without the
  complexity being live yet.
- Before building `apps/web`, the bar is: the pipeline has been running
  reliably for real, the data contracts in `docs/ARCHITECTURE.md` are stable
  (not still changing week to week), and there's a concrete reason files on
  disk aren't good enough anymore (e.g. wanting to browse history across
  days, not just today's run).
- If/when `apps/web` is built, it should read `reports/`/`data/` directly or
  through a thin read-only API — it should not require the pipeline to
  become a persistent service, and it must not reintroduce auth/accounts
  unless there's a real multi-user need.
