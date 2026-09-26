# Repository context

The magazine is produced by a small pipeline with three kinds of material:

```text
library/sources/<id>/   captured sources: record.yaml + article.md + media/
editions/<edition>/     plans, manuscripts, art, edition.yaml, render output dirs
prompts/                the hand-tested writer, plan, art, and translate prompts
```

`mag` (Rust, `mag/`) drives the workflow: `plan` proposes an edition from
unused sources, `produce` writes the articles, `art` and `translate` do what
they say, and `render` stages an edition and typesets it through Typst
(`mag/src/typeset/`), writing the PDF, booklet, and web outputs.

`library/release-state.yaml` records which sources are queued for or released
in each edition. `sources.md` is generated from the source records.

There is no run engine, no artifact graph, and no bookkeeping beyond the
files above. A source is its text and images; an edition is its manuscripts
and one YAML manifest.
