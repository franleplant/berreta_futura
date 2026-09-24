# WP-5.12 `mag parity --lang` and source-relative translated figure paths

Base: `art_directed` `d320995`, detached worktree `.../tmp/wp512`, own `mag/target`.
Source of the gap: `meta/verification/evidence/WP-3.10.md`, "For the orchestrator"
items 1 (manifest path) and 3 (parity `--lang`).

**Status: met.** `mag parity --pre-rendered` and `--adhoc` compare a named
language; 906 es exits 0 on both with no symlink aliases. The es
edition-manifest.json figure path is `media/diagram.png` on the typst leg. 010
staged parity is unchanged (exit 0, target E, 0 regressions).

## What changed

- `mag/src/main.rs`: `mag parity --lang <code>`, default `en`.
- `mag/src/parity.rs`: `Options.lang`. `render_leg` passes `langs: "en"` for en
  and `"en,<code>"` otherwise (both engines render every language in request
  order, so the primary is always rendered too). The reader PDF, the
  edition-manifest.json behind page sets, the critic inputs and the cached-oracle
  check all read `<leg>/<code>/`. The out dir gets a `-<code>` suffix
  (`output/parity/906-es`, `906-adhoc-es`); en keeps its old paths. A staged
  (baseline) run with `--lang` other than en is refused: the baseline and ratchet
  cover English only.
- `mag/src/parity/critic.rs`: `compare` now takes the language dirs, so
  `render-critic.json` and the four PDFs are read from the compared language.
- `mag/src/model/manifest.rs`: `figure_raw` (used only by `translation_raw`)
  writes the figure path relative to `library/sources/<source_id>/`, as the base
  edition's raw row carries it. It used to write the resolved absolute path.
  Class C: both engines were wrong. The bridge still writes the absolute
  staging path of a deleted temp dir until WP-6.1 fixes `_translation_raw`.

## Commands and results

```sh
M=mag/target/release/mag
# fixture: cp -R mag/tests/typeset_fixtures/corpus/editions/906 editions/, fixture-source-a..d into library/sources; moved out after
$M render 906 --engine weasyprint --no-model     # exit 0, W = render-2026-09-24T12-49-02 (en + es)
$M render 906 --engine typst --no-model          # exit 0, T = render-2026-09-24T12-49-21 (en + es)
$M parity 906 --pre-rendered W T --lang es       # exit 0
$M parity 906 --pre-rendered W T                 # exit 0 (en)
$M parity --adhoc 906 --lang es                  # exit 0
$M parity 010 --run editions/010/run-2026-09-13T01-34-51   # staged, uv on PATH: exit 0
(cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test)
#   fmt 0, clippy no warnings (hook re-checks at commit), test exit 0: 32 result lines, 951 passed, 0 failed
```

- 906 es `--pre-rendered`: page_count 16/16, critic pass (643 leaves, 0 differ),
  E glyph positions 3513 glyphs 0 violations, display list 3557 vs 3557. The
  verdict's `a_reader_sha256` `f17dc893...` equals `shasum` of `W/es/reader.pdf`.
  Positive control that es, not en, was read: the en run on the same pair gives
  3144 glyphs, 3188 elements, 679 critic leaves. Both sets match the WP-3.10
  numbers (es 3513/3557/643, en 3144/3188).
- 906 es `--adhoc`: mode `render`, gate `tier_s`. Every tier S clause passes
  (boxes, text 16 pages, colour, navigation 10 links, 8 outlines, title, lang,
  critic), and so does E (3513 glyphs, 0 violations; 3557/3557). The page sets
  are built from `es/edition-manifest.json`. The typst leg's es reader sha
  `a5594d73...` is byte-identical to T's.
- 010 staged: inputs fresh `bc49b2aa...`, ratchet pass (target E, 56 measured, 0
  regressions), critic pass, display list 59304 vs 59304, glyphs 59073, 0
  violations. Same numbers as WP-3.10.

### Figure path in es edition-manifest.json (`edition.articles[].figures[].path`)

| leg | en | es |
|---|---|---|
| bridge (W) | `media/diagram.png` | `/private/var/folders/.../mag-engine-render-stage-xai52e8m/library/sources/fixture-source-a/media/diagram.png` (still wrong, Python) |
| typst (T, this binary) | `media/diagram.png` | `media/diagram.png` |

The comparator does not compare this field, so leaving it out is the correct
treatment. It reads edition-manifest.json only for page sets: `layout.toc`,
`layout.article_pages`, `layout.figures[].page` and `layout.tail_arts`
(`parity.rs` `manifest_pages`/`placement_pages`/`page_sets`; grep for
`edition-manifest` in `parity.rs` and `parity/` finds only that read). Proof it
does not gate: 906 es exits 0 while the two legs differ in this field.

## Tests added

- `tests/model_manifest.rs`
  `a_translated_figure_path_stays_source_relative_as_in_the_base_edition`: 906 es
  raw figure paths are `["media/diagram.png"]` and equal to en's, while the
  in-memory `Figure.path` stays absolute for rendering. Negative control: with
  `manifest.rs` reverted to HEAD, the test fails with the absolute
  `.../corpus/library/sources/fixture-source-a/media/diagram.png`. No Python
  oracle case covers a translated figure (the only translation case,
  `translation_loads_cleanly`, has none), so the oracle suite is unaffected.
- `parity.rs`
  `a_non_english_comparison_renders_both_languages_and_never_touches_the_english_baseline`:
  `leg_langs` gives `en` and `en,es`, and a staged `--lang es` run is refused.
  `an_adhoc_run_writes_beside_the_baseline_run_never_over_it` now also pins
  `906-adhoc-es` and `906-es`.

## What is and is not proven

PROVEN: `--lang es` makes `--pre-rendered` and `--adhoc` read the es outputs
(sha and count controls above). 906 es passes both without aliases. en and 010
staged are unchanged. The Rust translation manifest writes the source-relative
figure path, and a test pins it.

NOT PROVEN:
- `--lang` with a staged baseline run: refused by design. There is no es baseline.
- The Python bridge still writes an absolute temp path (WP-6.1).
- Only 906 carries a translation. No real Spanish edition exists (WP-3.10).
