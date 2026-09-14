# WP-5.1a document model port

## Base

`0bd7cc0` (the tree at the start of this WP). This commit's parent is whatever
`art_directed` carried at commit time; concurrent Phase 1 spikes landed
evidence-only commits that touch none of the paths below, so the diff applies
on either.

Owns, as landed: `mag/src/model.rs`, `mag/src/model/doc.rs`,
`mag/src/main.rs` (module registration line only), `mag/tests/model_doc.rs`,
`mag/tests/model_doc_fixtures/*.md`, `mag/tests/model_doc_expected.json`,
`mag/tests/model_doc_settable.txt`, `mag/Cargo.toml`, `mag/Cargo.lock`, this
evidence file.

## Commands

The untracked run directory must be copied into the worktree before the
edition oracle runs:

```
cp -R /Users/franguijarro/code/magazine/editions/010/run-2026-09-13T01-34-51 editions/010/
```

Python oracle, edition 010 (all nine manuscripts):

```
uv run python -c '
import json, pathlib
from magazine.publication_document import parse_publication_document
from magazine.document_structure import visible_blocks, block_signature
from magazine.reader_text import educate_reader_quotes, fold_reader_characters
root = pathlib.Path("editions/010/run-2026-09-13T01-34-51/articles")
out = {}
for d in sorted(root.iterdir()):
    p = d / "final.md"
    if not p.is_file():
        continue
    doc = parse_publication_document(p.read_text(encoding="utf-8"))
    vb = visible_blocks(doc.blocks)
    text = "\n".join(t for _, t in vb)
    educated = educate_reader_quotes(text)
    out[d.name] = {
        "metadata_keys": sorted(doc.metadata),
        "visible_blocks": [list(x) for x in vb],
        "block_signature": block_signature(doc.blocks),
        "educated": educated,
        "folded": fold_reader_characters(educated),
    }
print(json.dumps(out, sort_keys=True, indent=1, ensure_ascii=True))
' > /tmp/py-projection.json
```

Rust projection compared against it, byte-for-byte as parsed JSON values:

```
cd mag && MAG_MODEL_ARTICLES=$PWD/../editions/010/run-2026-09-13T01-34-51/articles \
  MAG_MODEL_ORACLE=/tmp/py-projection.json \
  cargo test --test model_doc edition_manuscripts
```

Python oracle for the committed fixtures, which regenerates
`mag/tests/model_doc_expected.json` and must reproduce it byte-for-byte:

```
uv run python -c '
import json, pathlib
from magazine.publication_document import parse_publication_document
from magazine.document_structure import visible_blocks, block_signature
from magazine.reader_text import educate_reader_quotes, fold_reader_characters
root = pathlib.Path("mag/tests/model_doc_fixtures")
out = {}
for p in sorted(root.glob("*.md")):
    doc = parse_publication_document(p.read_text(encoding="utf-8"))
    vb = visible_blocks(doc.blocks)
    text = "\n".join(t for _, t in vb)
    educated = educate_reader_quotes(text)
    out[p.stem] = {
        "metadata_keys": sorted(doc.metadata),
        "visible_blocks": [list(x) for x in vb],
        "block_signature": block_signature(doc.blocks),
        "educated": educated,
        "folded": fold_reader_characters(educated),
    }
print(json.dumps(out, sort_keys=True, indent=1, ensure_ascii=True))
' | diff - mag/tests/model_doc_expected.json
```

Python oracle for the settable codepoint intersection, which regenerates
`mag/tests/model_doc_settable.txt`:

```
uv run python -c '
from magazine.reader_text import _settable_codepoints
print("\n".join(f"{cp:04X}" for cp in sorted(_settable_codepoints())))
' | diff - mag/tests/model_doc_settable.txt
```

Negative check, proving the edition oracle is not vacuous (one word changed
in the Python dump must fail the comparison):

```
python3 -c "
import json
d=json.load(open('/tmp/py-projection.json'))
k=sorted(d)[0]
d[k]['visible_blocks'][0][1]=d[k]['visible_blocks'][0][1].replace('Four times','Five times',1)
json.dump(d,open('/tmp/py-projection-doctored.json','w'),sort_keys=True,indent=1)
"
cd mag && MAG_MODEL_ARTICLES=$PWD/../editions/010/run-2026-09-13T01-34-51/articles \
  MAG_MODEL_ORACLE=/tmp/py-projection-doctored.json \
  cargo test --test model_doc edition_manuscripts
```

Repository gate:

```
cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test
```

## Tool versions

python 3.12.11, uv 0.8.17, markdown-it-py 4.2.0, PyYAML 6.0.3,
fontTools 4.63.0, rustc 1.96.0, pulldown-cmark 0.13.4, ttf-parser 0.25.1.

## Metrics

Edition 010 oracle: 9 manuscripts, 69176 bytes of Markdown, 199 visible
blocks, 183 block-signature entries, 65300 projected characters, compared as
whole JSON documents (208052 bytes of dump). Result: equal on the first run,
no divergence found or fixed.

Settable codepoints: 503, the intersection over all 12 vendored TTF faces,
equal to fontTools `getBestCmap` keys face for face.

Committed fixtures: 7 documents covering every construct the model supports,
including the three edition 010 does not carry (fenced code with and without
an info string, indented code, thematic rule, h1). Distinct visible kinds
exercised: bullet, code, h1, h2, h3, ordered, p, quote. Distinct signature
heads: body, code, h1, h2, h3, ol, quote, rule, ul.

Negative check: a single word altered in the Python dump fails the edition
comparison (exit 1, "the Rust projection diverged from the Python projection
of the edition").

`cargo test`: 3 model_doc tests green, whole suite green (nocomments and
parity_faults included), model_doc runtime 0.08 s.

## Verdicts

This WP produces no `mag parity` verdict; its oracle is the Python dump.

- Python edition projection `/tmp/py-projection.json`
  sha256 `e17ca71cffabe08b08820dd268863dcbda04615a871e5feaf52c34ca907cda50`
- committed fixture expectation `mag/tests/model_doc_expected.json`
  sha256 `e5275f180faff695dd4f48becc6b6daacd08dff41cd9b0d170fe10609bb85fad`
- committed codepoint intersection `mag/tests/model_doc_settable.txt`
  sha256 `df2687d0442c3b4f135ed7bf873a414bfaec787d793e46e0c52383cb0034a44f`

## Residuals

- Module registration carries `#[allow(dead_code)]` on `mod model;` in
  `mag/src/main.rs`: nothing in the binary consumes the model yet. WP-2.1 and
  WP-5.1c are its consumers and should remove the attribute when they wire it
  in. The module is compiled by the binary so errors surface at build time,
  and again by the test target through `#[path]`, because `mag` has no library
  target and an integration test cannot otherwise reach it.
- Crate choice: `pulldown-cmark` with `Options::empty()`, which is pure
  CommonMark with no extensions, matching markdown-it-py's `commonmark`
  preset. It does not percent-encode link destinations, which is what the
  Python side buys by overriding `normalizeLink` to the identity. `comrak`
  was not needed: the manuscripts carry no GFM extension syntax and
  CLAUDE.md forbids footnote syntax.
- One behavioral difference between the two parsers had to be ported
  explicitly: in a TIGHT list, markdown-it emits a hidden `paragraph_open`
  token, so the Python model wraps the item text in a `Paragraph`, while
  pulldown-cmark emits the inline events bare. `parse_blocks` wraps a bare
  inline run in a `Paragraph` to match. Without this the 010 corpus fails to
  parse at all, so it is covered by the edition oracle as well as the
  fixtures.
- `FencedCode.info` is carried through raw from pulldown-cmark. Neither
  projection reads it, so the oracle does not constrain it; a consumer that
  needs the highlight language (WP-5.5's web path) should confirm the
  trimming behavior against markdown-it before relying on it.
- `Block::BlockQuote` was renamed `Block::Quote` to satisfy
  `clippy::enum_variant_names` under `-D warnings`. Variant names are
  internal; no projection depends on them.
- `split_frontmatter` reproduces Python `str.splitlines(keepends=True)` line
  boundaries (including U+0085, U+2028, U+2029 and the C1 separators), not
  just `\n`, so a manuscript carrying an exotic separator splits identically
  on both sides.
- The edition oracle test is env-var driven and returns without asserting
  when neither `MAG_MODEL_ARTICLES` nor `MAG_MODEL_ORACLE` is set, because
  the run directory is untracked and `cargo test` must not depend on it.
  Setting exactly one panics. `cargo test` alone therefore proves the
  fixtures and the codepoint intersection, NOT edition 010; the 010 proof is
  the explicit command above, which the verifier must run.
- `tools/pdf2md.py` and other Python consumers of these three modules stay in
  place per the Phase 5 preamble; nothing was deleted.

## Status

done
