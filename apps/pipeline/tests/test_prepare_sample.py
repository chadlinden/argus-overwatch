"""Portfolio extraction must preserve saved evidence and reject incomplete input."""

import importlib.util
import json
from datetime import date
from pathlib import Path

import pytest

from argus import checkpoints
from argus.models import Cluster, EvalResult, ReviewStatus, Story

SCRIPT = Path(__file__).resolve().parents[3] / 'scripts/prepare_sample.py'
spec = importlib.util.spec_from_file_location('prepare_sample', SCRIPT)
sample = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sample)
RUN_DATE = date(2026, 9, 10)


def save_story(tmp_path, make_article, status):
    data = tmp_path / 'data'
    article = make_article()
    cluster = Cluster(articles=[article], label='Saved headline')
    story = Story(
        cluster=cluster, title='Saved headline', body_markdown='Original saved prose.',
        citations=[article.url], review_status=status,
        synthesis_backend='stub' if status == ReviewStatus.STUB else 'local:test-model',
        synthesis_confidence=0.4,
        eval=EvalResult(True, True, False, 'Unsupported claim.', False),
    )
    checkpoints.write_jsonl(checkpoints.raw_path(data, RUN_DATE), [article.to_dict()])
    checkpoints.write_jsonl(checkpoints.processed_path(data, RUN_DATE), [cluster.to_dict()])
    checkpoints.write_jsonl(checkpoints.stories_path(data, RUN_DATE), [story.to_dict()])
    return data, story


def test_preserves_real_review_failure_and_prose(tmp_path, make_article):
    data, story = save_story(tmp_path, make_article, ReviewStatus.NEEDS_REVIEW)
    output = tmp_path / 'sample'
    sample.prepare_sample(data, RUN_DATE, output, None)
    assert json.loads((output / 'story.json').read_text()) == story.to_dict()
    provenance = json.loads((output / 'provenance.json').read_text())
    assert provenance['review_status'] == 'needs_review'
    assert provenance['model_invoked_by_this_script'] is False
    assert 'Original saved prose.' in (output / str(RUN_DATE) / 'saved-headline.md').read_text()


def test_rejects_stub_only_run(tmp_path, make_article):
    data, _ = save_story(tmp_path, make_article, ReviewStatus.STUB)
    output = tmp_path / 'sample'
    with pytest.raises(ValueError, match='No saved, non-stub'):
        sample.prepare_sample(data, RUN_DATE, output, None)
    assert not output.exists()


def test_rejects_incomplete_checkpoint_join(tmp_path, make_article):
    data, _ = save_story(tmp_path, make_article, ReviewStatus.NEEDS_REVIEW)
    checkpoints.raw_path(data, RUN_DATE).write_text('')
    output = tmp_path / 'sample'
    with pytest.raises(ValueError, match='do not match'):
        sample.prepare_sample(data, RUN_DATE, output, None)
    assert not output.exists()


def test_does_not_overwrite_existing_output(tmp_path, make_article):
    data, _ = save_story(tmp_path, make_article, ReviewStatus.NEEDS_REVIEW)
    output = tmp_path / 'sample'
    output.mkdir()
    marker = output / 'keep.txt'
    marker.write_text('existing content')
    with pytest.raises(ValueError, match='already exists'):
        sample.prepare_sample(data, RUN_DATE, output, None)
    assert marker.read_text() == 'existing content'
