# Magazine project guidance

This repository builds private-first, source-faithful magazine editions.

## Non-negotiable rules

- Preserve provenance from the submitted lead to every underlying primary source.
- Treat `sources.md` as generated output. Human annotations belong in source records.
- Never replace a faithful source article with an AI summary unless an edition explicitly selects `original_synthesis` mode.
- AI proposes editorial patches; deterministic validation and human decisions advance workflow state.
- Label original editor text so it cannot be mistaken for a source author's words.
- Store third-party raw captures in the ignored `vault/` content store. Commit hashes and metadata, not private captures.
- Never claim an edition is press-ready without a named printer profile and a passing preflight.
- Cover art contains no baked-in masthead or cover lines. Layout code owns all typography.

## Verification

Use the bundled workspace Python runtime when available:

```sh
/Users/franguijarro/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest
```

Render generated PDFs to PNG and inspect every page before delivery.

