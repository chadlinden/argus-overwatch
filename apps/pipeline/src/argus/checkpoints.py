"""Read/write the on-disk checkpoints a run can resume from.

v4 wrote `data/raw/<date>.jsonl` and `data/processed/<date>.jsonl` from the
start, and `Article.from_dict` / `Cluster.from_dict` existed -- but nothing
ever read them back. The files were write-only debugging artifacts, so a run
that died during synthesis re-fetched every feed and re-clustered from
scratch on the next attempt.

That is expensive in the wrong place. Collection and clustering take
seconds; synthesis is up to `ARGUS_LOCAL_LLM_TIMEOUT_SECONDS` per story on
CPU inference, so a 15-story run is the overwhelming majority of wall time
and it is the stage most likely to be interrupted. Stories are therefore
checkpointed individually, appended as each one completes, so a resumed run
only pays for what it has not already done.

File-first stays the principle (ADR 0001): these are the same plain JSONL
files, just now readable in both directions.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

from .models import Article, Cluster, Story

logger = logging.getLogger("argus.checkpoints")


def raw_path(data_dir: Path, run_date: date) -> Path:
    return data_dir / "raw" / f"{run_date.isoformat()}.jsonl"


def processed_path(data_dir: Path, run_date: date) -> Path:
    return data_dir / "processed" / f"{run_date.isoformat()}.jsonl"


def stories_path(data_dir: Path, run_date: date) -> Path:
    return data_dir / "stories" / f"{run_date.isoformat()}.jsonl"


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for i, line in enumerate(path.read_text().splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            # A partially-written final line is the expected shape of "the
            # process was killed mid-append". Drop it and keep the rest
            # rather than discarding an otherwise good checkpoint.
            logger.warning("%s: skipping malformed line %d", path.name, i)
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def append_jsonl(path: Path, row: dict) -> None:
    """Append one record and flush. Called once per completed story, so an
    interrupted run keeps everything finished up to the moment it died."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(row) + "\n")
        f.flush()


def load_articles(data_dir: Path, run_date: date) -> list[Article]:
    return [Article.from_dict(d) for d in _read_jsonl(raw_path(data_dir, run_date))]


def load_clusters(data_dir: Path, run_date: date, articles: list[Article]) -> list[Cluster]:
    by_id = {a.id: a for a in articles}
    clusters = []
    for d in _read_jsonl(processed_path(data_dir, run_date)):
        cluster = Cluster.from_dict(d, by_id)
        # from_dict drops unknown article ids; an empty cluster means the raw
        # checkpoint no longer matches the processed one, so it is not
        # resumable and gets rebuilt.
        if cluster.articles:
            clusters.append(cluster)
    return clusters


def load_stories(data_dir: Path, run_date: date, clusters: list[Cluster]) -> list[Story]:
    """Completed stories from a previous attempt at this date.

    Later records win: re-synthesizing a cluster (say after a --fresh
    synthesis retry) appends a new line rather than rewriting the file, and
    the newest result for a cluster is the current one.
    """
    by_id = {c.id: c for c in clusters}
    by_cluster: dict[str, Story] = {}
    for d in _read_jsonl(stories_path(data_dir, run_date)):
        story = Story.from_dict(d, by_id)
        if story is not None:
            by_cluster[story.cluster.id] = story
    return list(by_cluster.values())
