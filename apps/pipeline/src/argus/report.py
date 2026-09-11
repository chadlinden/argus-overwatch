"""Write one markdown file per story to reports/<date>/, plus an index.md
that separates PUBLISHED from NEEDS_REVIEW -- a story that failed the eval
gate is still written to disk (nothing silently disappears), just not
presented as a finished article.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from .models import ReviewStatus, Story

logger = logging.getLogger("argus.report")


def _story_markdown(story: Story) -> str:
    lines = [f"# {story.title}", ""]
    lines.append(f"*Category: {story.cluster.category} · Sources: {', '.join(story.cluster.sources)}*")
    lines.append(f"*Status: {story.review_status.value} · Backend: {story.synthesis_backend}*")
    if story.synthesis_confidence is not None:
        lines.append(f"*Model confidence: {story.synthesis_confidence:.2f}*")
    if story.eval is not None and not story.eval.passed:
        lines.append(f"*Eval notes: {story.eval.notes}*")
    lines.append("")
    lines.append(story.body_markdown)
    lines.append("")
    lines.append("## Sources")
    for a in sorted(story.cluster.articles, key=lambda x: x.published_at):
        lines.append(f"- [{a.source}: {a.title}]({a.url})")
    return "\n".join(lines) + "\n"


def write_report(stories: list[Story], reports_dir: Path, report_date: date) -> Path:
    day_dir = reports_dir / report_date.isoformat()
    day_dir.mkdir(parents=True, exist_ok=True)

    published = [s for s in stories if s.review_status == ReviewStatus.PUBLISHED]
    needs_review = [s for s in stories if s.review_status == ReviewStatus.NEEDS_REVIEW]
    stub = [s for s in stories if s.review_status == ReviewStatus.STUB]

    index_lines = [f"# Argus Overwatch — {report_date.isoformat()}", ""]
    index_lines.append(
        f"{len(published)} published · {len(needs_review)} needs review · {len(stub)} stub"
    )
    index_lines.append("")

    for label, group in [("Published", published), ("Needs Review", needs_review), ("Stub", stub)]:
        if not group:
            continue
        index_lines.append(f"## {label}")
        for story in group:
            slug = story.slug()
            path = day_dir / f"{slug}.md"
            path.write_text(_story_markdown(story))
            index_lines.append(f"- [{story.title}](./{slug}.md)")
        index_lines.append("")

    index_path = day_dir / "index.md"
    index_path.write_text("\n".join(index_lines) + "\n")

    logger.info(
        "wrote %d story files + index to %s (%d published, %d needs review, %d stub)",
        len(stories), day_dir, len(published), len(needs_review), len(stub),
    )
    return index_path
