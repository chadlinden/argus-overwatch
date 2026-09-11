# Daily run flow

`scripts/run_daily.py` accepts `--date`, `--verbose`, and `--fresh`, loads
exported environment settings, and calls `argus.pipeline.run()`.

## Checkpoint reuse

```mermaid
flowchart TD
    A["Run date and settings"] --> B{"Reuse raw checkpoint?"}
    B -->|Yes| C["Load articles"]
    B -->|No| D["Collect and normalize feeds"]
    D --> E["Deduplicate, filter, save articles"]
    C --> F{"Reuse processed checkpoint?"}
    E --> F
    F -->|Yes| G["Load ranked clusters"]
    F -->|No| H["Embed, cluster, rank, save"]
    G --> I["Process top clusters"]
    H --> I
    I --> J{"Saved story for cluster ID?"}
    J -->|Yes| K["Reuse story"]
    J -->|No| L["Synthesize, evaluate, append story"]
    K --> M["Write grouped report index"]
    L --> M
```

`--fresh` bypasses reuse. Cluster IDs reflect article URL membership;
they do not detect changes to article text or inference configuration.

## Publication gate

```mermaid
flowchart TD
    A["Select cloud tier and configured local model"] --> B["Prioritize source context"]
    B --> C["Try configured synthesis backend"]
    C -->|No output| D["STUB"]
    C -->|Structured output| E["Check citations and call local judge"]
    E --> F{"Eval passes and confidence ≥ 0.6?"}
    F -->|Yes| G["PUBLISHED"]
    F -->|No or judge call fails| H["NEEDS_REVIEW"]
```

`auto` tries cloud synthesis when a key is set, then local synthesis, then
stub output. `local` uses one model at every rank. The judge is local even
when synthesis used Anthropic. Reports are written to disk; `PUBLISHED`
does not send a story to an external publishing service.

See [architecture](ARCHITECTURE.md) for the gate's validation and trust limits.
