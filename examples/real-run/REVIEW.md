# Sample review — 2026-09-11

This sample is included as evidence of an inspectable pipeline outcome, including
the limitations of its evaluation gate. It is not an independently fact-checked
news article or a claim of benchmark accuracy.

## Recorded outcome

| Field | Saved value |
| --- | --- |
| Run date | 2026-09-10 |
| Synthesis backend | local:qwen3:14b |
| Review status | published |
| Model confidence | 0.85 |
| Evaluation | passed |
| Source links | 11, spanning eight outlets |
| Reconstructed bounded context | Eight articles, one per outlet |

The six original extraction files are preserved byte-for-byte. No synthesis,
evaluation, source text, URLs, or metadata were changed. The original README and
provenance retain their extraction-time `pending` review label; this note records
the later source-consistency and inclusion review. It does not change the
pipeline's historical verdict.

## What can be checked from these files

- Saved story fields agree with the provenance record.
- The Markdown report contains the saved prose and all 11 source URLs.
- Hashing the sorted article URL hashes reproduces the saved cluster ID.
- All eight context article IDs match their URLs and belong to the cited cluster.
- The supplied titles and summaries support the central product, pricing,
  leadership, and availability details at the level visible in feed excerpts.
- A credential/private-address/user-home-path pattern scan found no matches.
  The bundle contains public article links and short feed excerpts, not full
  source articles or local runtime configuration.

## What the judge missed

The judge passed the report and described its attribution as appropriate, but
comparison against the supplied context reveals attribution imprecision:

1. The sentence ending with attribution to CNBC includes the CEO succession date.
   In the reconstructed context, that date appears in the ABC summary; the CNBC
   summary only establishes the launch event, CEO, and announced devices.
2. The sentence attributed to Fortune includes the CEO's first public appearance.
   That detail appears in The Hill's summary, while Fortune's summary supports
   the description of the size of the iPhone update.
3. The closing sentence adds interpretation about a shift in strategy without
   clearly labeling it as synthesis or explaining the supporting evidence.

These observations do not establish that the underlying facts are false. They
show that support somewhere in a cluster is weaker than precise attribution to
the cited source, and that the current judge did not enforce that distinction.
Keeping this passing example intact makes that limitation visible.

## Evidence limits and next improvement

This review compares the saved output with the uploaded context. It does not
independently retrieve or verify the current source pages. The context was
reconstructed using the current prioritizer; exact original requests and runtime
settings were not captured. The 0.85 confidence is the model's own estimate,
not a measured probability of correctness. One selected passing sample does
not measure the rate of false passes or demonstrate every failure path.

A concrete next evaluation improvement is to check each attributed claim against
the specifically named source, retain source identifiers in the prompt, and add
accepted attribution-error cases to a separate synthesis benchmark. Exact
request/configuration capture would also make future run reviews stronger.
