#!/usr/bin/env python3
"""Extract one real saved v4 story for review, without invoking a model."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from argus import checkpoints
from argus.config import Settings
from argus.models import ReviewStatus
from argus.report import write_report
from argus.synthesize.context import prioritize_articles


def prepare_sample(data_dir: Path, run_date: date, output: Path, cluster_id: str | None) -> Path:
    if output.exists():
        raise ValueError('Output already exists; choose a new directory.')
    articles = checkpoints.load_articles(data_dir, run_date)
    by_id = {article.id: article for article in articles}
    # Reject incomplete joins instead of quietly changing a saved cluster.
    processed = checkpoints.processed_path(data_dir, run_date)
    if not processed.is_file():
        raise ValueError('The processed checkpoint is missing for this date.')
    for line in processed.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if any(article_id not in by_id for article_id in row['articles']):
            raise ValueError('Raw and processed checkpoints do not match; no sample written.')
    clusters = checkpoints.load_clusters(data_dir, run_date, articles)
    stories = checkpoints.load_stories(data_dir, run_date, clusters)
    candidates = [story for story in stories if story.review_status != ReviewStatus.STUB
                  and story.synthesis_backend != 'stub']
    if cluster_id:
        candidates = [story for story in candidates if story.cluster.id == cluster_id]
    if not candidates:
        raise ValueError('No saved, non-stub v4 story matched. No sample was fabricated.')
    # Prefer a passing story; otherwise retain the real needs_review outcome.
    story = next((s for s in candidates if s.review_status == ReviewStatus.PUBLISHED), candidates[0])
    context = prioritize_articles(story.cluster.articles)
    output.mkdir(parents=True)
    index = write_report([story], output, run_date)
    (output / 'story.json').write_text(json.dumps(story.to_dict(), indent=2) + '\n')
    (output / 'source-context.json').write_text(json.dumps({
        'note': 'Context reconstructed with the current prioritizer, not a captured request. '
                'Review feed text and URLs before public redistribution.',
        'articles': [{k: v for k, v in a.to_dict().items() if k != 'fetched_at'} for a in context],
    }, indent=2) + '\n')
    (output / 'provenance.json').write_text(json.dumps({
        'run_date': run_date.isoformat(),
        'cluster_id': story.cluster.id,
        'review_status': story.review_status.value,
        'synthesis_backend': story.synthesis_backend,
        'synthesis_confidence': story.synthesis_confidence,
        'eval': story.eval.to_dict() if story.eval else None,
        'original_run_configuration': 'Not persisted in these checkpoints; not inferred.',
        'model_invoked_by_this_script': False,
        'public_release_review': 'pending',
    }, indent=2) + '\n')
    (output / 'README.md').write_text(
        '# Real Argus sample — pending publication review\n\n'
        f'Extracted one saved story for {run_date.isoformat()}. '
        f'Status: `{story.review_status.value}`; backend: `{story.synthesis_backend}`.\n\n'
        f'[Report]({index.relative_to(output).as_posix()}) · '
        '[Provenance](provenance.json) · [Source context](source-context.json)\n\n'
        'The report is rendered from the saved story without rewriting its prose or verdict. '
        'No model call was made. Configuration and exact original prompts cannot be '
        'recovered from these checkpoints. This is an extraction, not automatic sanitization: '
        'review the report, eval notes, URLs, and feed text before publishing.\n'
    )
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date', required=True, type=date.fromisoformat)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--cluster-id', help='Exact cluster ID; otherwise prefer a published story')
    args = parser.parse_args()
    data_dir = args.data_dir if args.data_dir is not None else Settings().data_dir
    try:
        result = prepare_sample(data_dir, args.date, args.output, args.cluster_id)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(1, f'Sample extraction failed: {exc}\n')
    print(f'Real sample prepared for review: {result}')


if __name__ == '__main__':
    main()
