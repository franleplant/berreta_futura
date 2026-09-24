# WP-5.6 verify: ACCEPTED

Verifier (WP-4.1 gate), tip `fa3fe15`, clean clone `.../tmp/g41/v`, release binary.

## Replay

```sh
P=<PATH minus the directory holding uv>; env PATH=$P sh -c 'command -v uv'   # exit 1
env PATH=$P mag render 010 --engine weasyprint --run editions/010/run-2026-09-13T01-34-51 --langs en --no-model
#   positive control: "spawning `uv run mag-render-adapter`: No such file or directory"
env PATH=$P mag render 010 --engine typst --run editions/010/run-2026-09-13T01-34-51 --langs en --no-model
#   exit 0; en/ has reader, booklet-a4{,-cover,-interior}.pdf, render-critic.json (result pass),
#   preflight.json, SHA256SUMS, studio/, web/, web-output.zip, package.zip
```

The typst reader.pdf rendered without uv is `6c03dda9...`, byte-equal to the gate's
typst leg (WP-4.1.md). So the cover faces this WP wires in are the pages 1 and 56 that
the gate compares at Tier E on every clause.

## Injected defect

`replace_outer_pages` (`typeset/cover.rs:501`) replaces only the front page (back
face dropped). `cargo test outer_pages_take_the_cover_faces` exit 101:
`outer_pages_take_the_cover_faces_and_keep_the_interiors_catalog` FAILED. Restored.

## What is and is not proven

Proven: the no-uv typst render and the cover step, now gated end to end by WP-4.1.
Not re-proven here: the package-entry table (WP-5.6.md). The gate compares reader.pdf
and the critic report, not package.zip.
