#!/usr/bin/env python3
"""Build an allowlisted, history-free snapshot from tracked repository files."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    'README.md', 'LICENSE', 'CONTRIBUTING.md', '.editorconfig', '.gitignore',
    '.env.example', '.github/workflows/ci.yml', 'pyrightconfig.json',
    'config/sources.yaml', 'apps/pipeline/pyproject.toml', 'apps/pipeline/uv.lock',
    'docs/ARCHITECTURE.md', 'docs/ROADMAP.md', 'docs/EVALUATION.md',
    'docs/pipeline-flow.md', 'examples/README.md',
    'scripts/export_portfolio.py', 'scripts/prepare_sample.py',
    'examples/real-run/README.md', 'examples/real-run/REVIEW.md',
    'examples/real-run/provenance.json', 'examples/real-run/story.json',
    'examples/real-run/source-context.json', 'examples/real-run/2026-09-10/index.md',
    ('examples/real-run/2026-09-10/'
     'apple-unveils-first-foldable-iphone-in-major-product-update.md'),
}
DIRECTORIES = {
    'apps/pipeline/src/': '.py', 'apps/pipeline/scripts/': '.py',
    'apps/pipeline/tests/': '.py', 'docs/adr/': '.md', 'evals/golden/': '.jsonl',
}


def included(name: str) -> bool:
    if name in REQUIRED:
        return True
    if name.startswith('apps/pipeline/src/argus/mcp/'):
        return False
    if any(part.startswith('.') for part in PurePosixPath(name).parts):
        return False
    return any(name.startswith(prefix) and name.endswith(suffix)
               for prefix, suffix in DIRECTORIES.items())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--source-ref', required=True, help='Reviewed upstream commit SHA')
    args = parser.parse_args()
    output = args.output.resolve()
    if output == ROOT or ROOT in output.parents:
        parser.error('Choose an output directory outside this repository.')
    if output.exists():
        parser.error('Output already exists; choose a new directory.')
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    missing = REQUIRED - set(tracked)
    if missing:
        parser.error(f'Required files are not tracked: {sorted(missing)}')
    names = sorted(name for name in tracked if name and included(name))
    for name in names:
        source = ROOT / name
        if source.is_symlink() or not source.is_file() or ROOT not in source.resolve().parents:
            parser.error(f'Not a regular repository file: {name}')
    output.mkdir(parents=True)
    files = []
    for name in names:
        source, target = ROOT / name, output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        files.append({'path': name, 'bytes': target.stat().st_size,
                      'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    manifest = {
        'source_ref': args.source_ref,
        'scope': 'Current allowlisted working-tree files and one reviewed saved-run sample; '
                 'no Git history or other runtime data.',
        'files': files,
    }
    (output / 'SNAPSHOT.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Exported {len(files)} files to {output}')


if __name__ == '__main__':
    main()
