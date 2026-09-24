# WP-0.2w evidence

Base bc512e6. Sources: WP-4.0g.verify.md (mutants 5-7), WP-5.1h.md sections
1 and 3, WP-5.1h.verify.md (scalar_label removal survived).

## What changed

1. `parity.rs`: new test
   `the_tier_s_gate_fails_on_each_clause_failing_or_missing_alone` breaks
   each Tier S clause alone (page_count, boxes, text, color, navigation set
   to "fail"; boxes, text, color, navigation set to None) and asserts
   `tier_s_pass` is false, after asserting the unbroken verdict passes.
2. `parity.rs`: `pub(crate) use exact::{authored, num};`. `impose.rs` now
   binds every real through `parity::authored(&doc, &raw)` for the life of
   the source-page read and reads box numbers with `parity::num`; the regex
   raw-byte recovery (`authored_boxes`, `Authored`, `number`) is gone, so a
   reader whose pages sit in an object stream imposes. The test crates that
   include `impose.rs` by `#[path]` gained the re-export in their `parity`
   shim (critic_faults, critic_rules, package) or an exact+streams+shim
   include (impose, preflight). New test
   `a_reader_whose_pages_live_in_an_object_stream_imposes_at_authored_precision`
   (tests/impose.rs): a hand-built PDF with the page dictionary in an ObjStm,
   MediaBox `0 0 419.527559 595.275591`; the sheet's placement matrix must be
   `1.00000002` (exact 595.2756 / 595.275591 = 1.0000000151; the f32 path
   gives 1.00000004).
3. `model/doc.rs`: Python (`publication_document.py:136`, `yaml.safe_load`)
   loads `label: !!null`, `!!null ''`, `!!null foo` and
   `!<tag:yaml.org,2002:null> x` as None (probed with `uv run python`, exit
   0), refuses `!!null [a]` (ConstructorError "expected a scalar node") and
   `[!!null,!!null]` (ParserError). serde_yaml refused every `!!null` whose
   scalar is not a null literal (`de.rs` parse_null). `load_header` parses
   as before; only when that fails and the header contains a null tag, it
   retries with the tag swapped for the local `!magazine-null` and maps
   that tag to Null on a scalar, refusing it on a collection. `~` and
   `null` already loaded as Null. Tests: every spelling loads `label` as
   Null and `content_label` falls back to the mode label exactly as an
   absent key does; the collection and parser-error cases are refused with
   `Invalid YAML frontmatter: `.
4. `tests/web_port_fixtures/wfx/articles/container-label.md` (keyed.md with
   `label: []` frontmatter) and test
   `a_container_label_refuses_the_web_edition_instead_of_printing_brackets`,
   which pins `Frontmatter label must be text, not []`. Rust-only: Python
   prints `()` there, which WP-5.1h classified as wrong in both engines.

## Commands and results

- `cargo test` in `mag/`: exit 0, 32 result lines, 835 passed, 0 failed.
- `cargo fmt --check` exit 0; `cargo clippy --all-targets -- -D warnings`
  exit 0.
- `mag parity 010 --pre-rendered editions/010/render-2026-09-24T01-56-37
  editions/010/render-2026-09-24T01-58-11` with release binaries built at
  bc512e6 (`mag-base`) and at this change (`mag-w`), separate
  MAG_PARITY_OUT_DIR each: both exit 1 (Tier S navigation, as before);
  `cmp` of the two verdict.json exit 0 (**byte-identical**).
- WP-5.2 impose oracles: the committed fixture tests in tests/impose.rs
  pass inside the full run above. Live edition leg:
  Python oracles regenerated from
  `editions/010/render-2026-09-14T01-49-02/en/reader.pdf` with the
  WP-5.2.md recipe (exit 0), then `MAG_IMPOSE_READER=... MAG_IMPOSE_ORACLE_DIR=...
  cargo test --test impose imposition_matches_python_on_the_live_edition`
  with this change: exit 0, 1 passed (1405.79 s; display list, text, sheet
  count and per-sheet raster equal for all, interior, cover).

## Mutants (each restored after; `git diff --stat` confirmed)

- Drop each conjunct of `tier_s_pass` in turn (page_count, boxes, text,
  color, navigation): the new gate test FAILS for each, naming clause
  0..4. Before this WP page_count, color and navigation survived
  (WP-4.0g.verify.md mutants 5-7).
- Base `impose.rs` (bc512e6) with the new object-stream test: FAILS with
  "MediaBox on object (3, 0) carries a real that lopdf parsed as f32 and no
  authored text was recoverable".
- `scalar_label(&document.metadata)?;` removed from `web/semantic.rs`: the
  new web_port test FAILS (the edition writes). WP-5.1h.verify.md recorded
  this removal surviving.
- doc.rs retry disabled: both doc tests FAIL. Collection arm replaced by an
  unreachable pattern: the refusal test FAILS.

## What is and is not proven

- Proven: the Tier S gate refuses each clause failing or missing alone;
  imposition reads object-stream boxes at authored decimal precision on a
  synthetic reader; null-tagged labels load as Null like PyYAML; a list
  label refuses the web edition; the 010 parity verdict did not move.
- Not proven / remaining divergence: `label: !!null [a]` alone still loads
  as a sequence in Rust (serde_yaml ignores a core tag on a collection, so
  the first parse succeeds and the retry never runs) where Python refuses;
  the web path then refuses it via `scalar_label`, the typeset path does
  not (typeset is not owned here). The retry rewrites `!!null` textually,
  so in a header that already fails for a null tag, a quoted string
  containing `!!null` would be altered; zero such headers are known.
  `shared::load_structured` still refuses `!!null` (shared.rs not owned).
  No real edition reader with object streams was imposed (the 010
  reader of the live leg has 0 `/ObjStm` and 56 `/MediaBox`, `grep -a -c`).
