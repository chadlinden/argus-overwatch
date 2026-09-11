# Example output

The [September 10 sample](real-run/2026-09-10/index.md) is a saved v4 report
from the author's local run. It covers an Apple product launch and was generated
using `local:qwen3:14b`. The saved gate result is `published`, with model-reported
confidence of 0.85 and a passing evaluation.

- [Original story and evaluation](real-run/story.json)
- [Recorded provenance](real-run/provenance.json)
- [Reconstructed source context](real-run/source-context.json)
- [Review: what passed, what the judge missed, and evidence limits](real-run/REVIEW.md)

The six original extraction files are preserved byte-for-byte. Their `pending`
publication-review label records the extraction-time state; `REVIEW.md` documents
the subsequent review. No model call was made during extraction or curation.
The 11 cluster source links span eight outlets; context was capped at eight
articles. This is one inspectable run outcome, not a model-quality benchmark.
The unit tests separately use controlled inputs and fake model responses.

## Extract a saved story

On the machine that ran Argus, activate the pipeline environment and run this
from the repository root, substituting the date of an existing v4 run:

```bash
python scripts/prepare_sample.py --date 2026-09-10 --output ../argus-real-sample
```

This reads the matching `data/raw/`, `data/processed/`, and `data/stories/`
checkpoints. It makes no network requests or model calls. It prefers one
`published` story; if none exists, it retains a real `needs_review` story.
Use `--cluster-id` to choose an exact story, or `--data-dir` for a custom data
location. The script refuses to overwrite a folder or manufacture a non-stub
sample when none exists.

The result includes a rendered report, the original saved story fields,
evaluation result, recorded model/backend, and bounded source context. Exact
original prompts and runtime settings were not persisted; the extraction
explicitly records that limit instead of reconstructing them as facts.

Review the folder before adding it to a public repository. In particular,
evaluation error messages may contain local service addresses, and source
text/URLs may need trimming for redistribution. Preserve the original verdict
and explain any redactions. The regular public export deliberately does not
copy arbitrary sample folders automatically. Only the explicitly reviewed files
under `examples/real-run/` are allowlisted for this snapshot.
