"""Orchestrates the full pipeline end-to-end. Callable from the CLI or the scheduler.

Runs are RESUMABLE by default. Each stage checks for its checkpoint on disk
and reuses it rather than recomputing, and synthesis resumes per story. This
matters because the stages have wildly different costs: collection and
clustering are seconds, while synthesis is up to
ARGUS_LOCAL_LLM_TIMEOUT_SECONDS per story on CPU inference. A 15-story run
is dominated by synthesis, and synthesis is the stage most likely to be
interrupted.

It also makes the container safe to restart. `scheduler.py` runs the
pipeline once at startup, so without resume a restart loop is an inference
loop.

Pass fresh=True to ignore checkpoints and recompute everything.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from pathlib import Path

from . import checkpoints
from .cluster.clustering import cluster_articles
from .cluster.rank import rank_clusters
from .collect.dedupe import dedupe
from .collect.fetch import collect
from .collect.filter import filter_articles
from .collect.normalize import normalize
from .config import Settings, load_sources
from .models import Article, Cluster
from .report import write_report
from .synthesize.pipeline import run_clusters

logger = logging.getLogger("argus.pipeline")


def _collect_articles(settings: Settings, run_date: date, fresh: bool) -> list[Article]:
    if not fresh:
        cached = checkpoints.load_articles(settings.data_dir, run_date)
        if cached:
            logger.info("resume: %d articles from raw checkpoint", len(cached))
            return cached

    sources = load_sources(settings)
    logger.info("loaded %d sources from %s", len(sources), settings.sources_file)

    articles = filter_articles(dedupe(normalize(collect(sources))))
    checkpoints.write_jsonl(
        checkpoints.raw_path(settings.data_dir, run_date),
        [a.to_dict() for a in articles],
    )
    return articles


def _build_clusters(
    settings: Settings, run_date: date, articles: list[Article], fresh: bool,
) -> list[Cluster]:
    if not fresh:
        cached = checkpoints.load_clusters(settings.data_dir, run_date, articles)
        if cached:
            logger.info("resume: %d clusters from processed checkpoint", len(cached))
            return cached

    clusters = rank_clusters(
        cluster_articles(articles, window_hours=settings.cluster_window_hours)
    )
    checkpoints.write_jsonl(
        checkpoints.processed_path(settings.data_dir, run_date),
        [c.to_dict() for c in clusters],
    )
    return clusters


def run(settings: Settings, run_date: date | None = None, fresh: bool = False) -> Path:
    run_date = run_date or datetime.now(UTC).date()
    logger.info(
        "=== Argus Overwatch v4 run for %s%s ===",
        run_date.isoformat(), " (fresh)" if fresh else "",
    )

    articles = _collect_articles(settings, run_date, fresh)
    clusters = _build_clusters(settings, run_date, articles, fresh)

    stories_file = checkpoints.stories_path(settings.data_dir, run_date)
    if fresh and stories_file.exists():
        stories_file.unlink()

    done = {} if fresh else {
        s.cluster.id: s
        for s in checkpoints.load_stories(settings.data_dir, run_date, clusters)
    }
    if done:
        logger.info("resume: %d stories already synthesized for %s", len(done), run_date.isoformat())

    stories = run_clusters(
        clusters,
        api_key=settings.anthropic_api_key,
        max_stories=settings.max_stories,
        backend=settings.synthesis_backend,
        local_host=settings.local_llm_host,
        local_timeout=settings.local_llm_timeout_seconds,
        local_model=settings.local_llm_model,
        done_stories=done,
        on_story=lambda s: checkpoints.append_jsonl(stories_file, s.to_dict()),
    )

    index_path = write_report(stories, settings.reports_dir, run_date)
    logger.info(
        "=== run complete: %d articles -> %d clusters -> %d stories ===",
        len(articles), len(clusters), len(stories),
    )
    return index_path
