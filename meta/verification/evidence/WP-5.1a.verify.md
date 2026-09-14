# WP-5.1a document model port, verification

## Verdict

REJECTED.

Every stated verify clause reproduces green, and the port is faithful across
eleven of the twelve Markdown constructs probed. One construct diverges: a
space-padded link adjacent to non-space text produces different reader text
in Rust than in Python. The defect is in `inline_visible`, is masked by
edition 010's content and by the committed fixtures, and would surface later
as a Tier E text failure or, after WP-6.1 deletes the Python module, as a
silent change to what the magazine prints.

Everything else verified green, so the re-run is cheap: one function, one
fixture, one regenerated expectation.

## Base

WP commit `cc39664`, diff base `227dfb2`, verified in a fresh worktree at
`cc39664`. Evidence file `meta/verification/evidence/WP-5.1a.md`.

## Owns check

`git diff --name-only 227dfb2..cc39664` lists fifteen paths, all within Owns:
`mag/src/model.rs`, `mag/src/model/doc.rs`, `mag/src/main.rs`,
`mag/tests/model_doc.rs`, `mag/tests/model_doc_expected.json`,
`mag/tests/model_doc_settable.txt`, seven files under
`mag/tests/model_doc_fixtures/`, `mag/Cargo.toml`, `mag/Cargo.lock`, and the
evidence file. No `*.verify.md`, no `baseline.json`, no comparator territory
(`mag/src/parity*`, `parity.yaml`), no `mag/src/typeset/**`, no
`mag/src/render.rs`.

The brief named `mag/src/model/mod.rs`; the WP landed `mag/src/model.rs`,
which is the same module file in the other permitted spelling. Not a
violation.

The `mag/src/main.rs` hunk is exactly the module registration:

```
+#[allow(dead_code)]
+mod model;
```

## Commands

Replayed from the worktree with the untracked run directory copied in
(`cp -R .../editions/010/run-2026-09-13T01-34-51 editions/010/`). Full script
retained at `/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp51a-replay.sh`,
construct sweep at `.../wp51a-sweep.sh`.

- `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings`,
  `cargo test` in `mag/`
- the evidence's edition-010 Python oracle, verbatim
- `MAG_MODEL_ARTICLES=... MAG_MODEL_ORACLE=... cargo test --test model_doc
  edition_manuscripts`
- the fixture-expectation regeneration diff, verbatim
- the settable-codepoint regeneration diff, verbatim
- the negative check, with a different word altered than the evidence used
- two guard probes: exactly one env var set, and plain `cargo test`
- a twelve-construct sweep, each construct as its own single-article corpus
  so failures isolate

## Replay results

All claimed results reproduce.

| check | claimed | observed |
|---|---|---|
| `cargo fmt --check` | green | green |
| `clippy --all-targets -D warnings` | green | green |
| `cargo test` | green | green, 6 tests, parity_faults 19.47 s |
| oracle sha256 | `e17ca71c…07cda50` | `e17ca71c…07cda50`, identical |
| oracle dump bytes | 208052 | 208052 |
| manuscript Markdown bytes | 69176 | 69176 |
| manuscripts | 9 | 9 |
| visible blocks | 199 | 199 |
| block-signature entries | 183 | 183 |
| edition 010 Rust vs Python | equal | equal, exit 0 |
| fixture expectation regenerates | byte-for-byte | byte-for-byte, diff empty |
| settable codepoints | 503, byte-for-byte | 503, diff empty |
| negative check | fails | fails, exit 101 |

Two guard behaviours confirmed as the evidence documents them: setting
exactly one of `MAG_MODEL_ARTICLES` / `MAG_MODEL_ORACLE` panics, and plain
`cargo test` passes the edition test vacuously by early return, so it proves
the fixtures and the codepoint intersection and NOT edition 010.

One metric is mislabelled rather than wrong. The evidence's "65300 projected
characters" is the sum of visible-block text lengths; the educated and folded
projections are 65490 characters each. The dump digest matches exactly, so
nothing about the comparison is affected.

## The defect

`_inline_visible` in `src/magazine/document_structure.py` collapses
whitespace INSIDE each nested container and then concatenates the results:
a nested `Emphasis`, `Strong` or `Link` contributes an already-stripped,
already-collapsed string to `parts`, and only then is `"".join(parts)`
re-split.

`inline_visible` in `mag/src/model/doc.rs` flattens every nested container
raw into one buffer and collapses once at the end. The two agree whenever a
container's visible text has no leading or trailing whitespace, which is why
010 and the fixtures pass.

They disagree when a space-padded container sits against non-space text on
both sides. Probe input:

```
Alpha[ beta ](https://example.com)gamma.
```

- Python: `Alphabetagamma.`
- Rust: `Alpha beta gamma.`

Reproduced through the WP's own comparison harness, which fails with exactly
this pair. `[ beta ]` is legal CommonMark link text and the padding is
preserved by both parsers; the divergence is entirely in the projection.

Construct sweep, each as its own corpus:

| construct | result |
|---|---|
| padded_link | **DIVERGE** |
| padded_link_in_strong | agree |
| nested_link_emphasis | agree |
| tight_list | agree |
| loose_list_code | agree |
| ordered_start | agree |
| quote_with_list | agree |
| hardbreak | agree |
| indented_code | agree |
| emphasis_softbreak | agree |
| code_inline_pad | agree |
| rule_and_headings | agree |

The two padded cases that agree do so because the padded container is
already surrounded by spaces, so both routes collapse to the same string.
The divergence needs the padded container adjacent to non-space text.

## What must change

1. `inline_visible` / `push_visible` in `mag/src/model/doc.rs`: match the
   Python shape. `Emphasis`, `Strong` and `Link` must each contribute their
   OWN collapsed visible string as a unit; `Text` and `Code` contribute raw
   values; `LineBreak` contributes a single space; the concatenation is
   collapsed once at the end.
2. Add a fixture covering a space-padded link adjacent to non-space text
   (`Alpha[ beta ](url)gamma.` suffices), and padded `Emphasis`/`Strong`
   variants in the same position, then regenerate
   `mag/tests/model_doc_expected.json` from the Python oracle.
3. Re-run the edition-010 oracle (must stay equal) and the fixture and
   settable diffs.

If the author judges the Python behaviour to be a bug that must not be
replicated, the Phase 5 preamble and rule 6 make that a fail-loud finding:
record it, set `Status: blocked`, and do not diverge silently.

## Critique, non-blocking

- **The oracle constrains only the projections.** Link destinations, link
  titles, fenced-code info strings and frontmatter metadata VALUES are never
  compared by any of the five projected fields; `metadata_keys` compares keys
  alone. This is exactly the plan's stated clause, so it is not a defect, but
  WP-2.1 and WP-5.1c must not treat those fields as proven. The evidence
  notes this for `info` only; the same caveat applies to destination, title
  and metadata values. It is also why this defect slipped: coverage inside
  the projection depends entirely on which constructs the fixtures carry.
- **Link title**: `(!title.is_empty()).then(...)` maps an explicitly empty
  title to `None`, where Python keeps `""`. Unconstrained by the oracle.
- **cmap intersection**: fontTools `getBestCmap` keeps a codepoint that maps
  to glyph id 0; `face_codepoints` filters those out. Identical for the
  twelve vendored faces (503 both sides, byte-equal), latent only if a future
  face maps a codepoint to `.notdef`. The `CMAP_PREFERENCES` table matches
  fontTools' default preference order exactly.
- **Character-class edges**: Python `str.isalpha`/`isalnum` and Rust
  `char::is_alphabetic`/`is_alphanumeric` differ on Other_Alphabetic marks,
  so a quote adjacent to such a mark could educate differently. Not reachable
  in English or Spanish copy.
- **Correctly ported, confirmed line by line**: the glyph fallbacks (U+2011
  and U+2212 to hyphen, U+00AD dropped), `splitlines(keepends=True)`
  boundaries including U+0085/U+2028/U+2029 and the C1 separators, Python's
  `str.isspace` covering U+001C-U+001F where Rust's `is_whitespace` does not,
  the `\u{a0}` fold and the `isascii` early return, the quote-education
  branches including the index-0 empty-previous case, `block_signature`
  descriptors including the `@start` suffix only for ordered lists starting
  off 1, and symmetric fail-loud on unsupported block and inline tokens (raw
  HTML errors on both sides).
- **`#[allow(dead_code)]`** sits on the module registration, the narrowest
  scope available while `mag` has no library target. The evidence already
  assigns its removal to WP-2.1 / WP-5.1c.

## Status

rejected
