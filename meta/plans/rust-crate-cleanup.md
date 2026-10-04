# Rust crate cleanup

Status: **in execution**, 2026-10-04. Orchestrated: one implementer per
batch, an independent verifier, local commit per verified batch, push to
main after the final edition 012 render. Written from a three-reviewer
read of `mag/` (CLI and pipeline; model, critic and trace; typeset, render
and cover) at base commit `534661c`. Line numbers below are from that commit
and will drift; find the code by the names given, not by the number.

## Why

The crate is disciplined in the small (errors carry context, model output is
gated mechanically, PDFs are reproducible, user text is escaped into Typst in
one checked place). The structural problems come from a Python port that
stopped halfway: the old process boundary, the CPython emulation, the
WeasyPrint emulation, and a PDF reader that recovers layout Typst already
holds in memory all still run in production, and the data model never
became typed. This plan finishes the port and fixes the safety issues the
review found.

## Decisions already made (do not re-open)

- WeasyPrint parity is **not** a goal. Delete everything that exists for it.
- CPython / PyYAML emulation is **not** a goal. Delete it.
- The oracle snapshot tests go. A small set of invariant tests replaces them
  (WP-2.3).
- Every suggestion from the review is accepted; this plan carries all of
  them. Two items keep a measured decision inside the WP (WP-4.4, WP-4.9)
  and one keeps a question for Fran (WP-4.0).

## Ground rules for the executing agent

- Work on `main`. The worktree is shared with other live sessions: check the
  index first, commit with `git commit --only -- <paths>`, never reset,
  stash, or rewrite anything you did not write.
- One WP is one coherent commit (or a few). The pre-commit hook must pass:
  `cargo fmt --check`, `cargo clippy --all-targets -D warnings`, ruff on
  `tools/`, `cargo test --test nocomments`. Run the full `cargo test` in
  `mag/` before each commit.
- Clippy denies a curated list of pedantic lints in `mag/Cargo.toml`
  (AGENTS.md: add pedantic lints by name, fix findings); new code passes
  them.
- House style: no comments, fewest readable lines, low complexity, no
  U+2014 in code, prompts, or copy.
- Fail loud. If a WP hits something this plan did not foresee, stop and
  report it; do not work around it silently.
- Output-changing WPs (marked **[visual]**) end with a before/after render
  handed to Fran. Green tests are not the acceptance check for layout; Fran's
  eyes on the PDF are.
- Subagents are disposable: fresh agent per WP with a self-contained brief,
  at most about 3 concurrent.

## Phase 0: baseline

**WP-0.1 Reference renders. DONE 2026-10-04.** Baseline binary (pre-cleanup,
`9c07153`) rendered 012 en (no Spanish translation exists for 012): 76
pages, critic pass, 38 s wall clock, kept outside the repo by the
orchestrator. Original text: Render the newest complete edition (012, en
and es, plus 013 if it renders) and `mag site --out` into scratch. Keep the
PDFs, page counts, the page each article starts on, and wall-clock render
time. These are the comparison point for every [visual] WP and for WP-4.2.

## Phase 1: safety and correctness (no intended output change)

**WP-1.1 Art brief ids and shell quoting.** `art.rs` `extract_briefs`
accepts any non-empty `brief.id` from the model; `candidate_command`
(~386) puts it into the filename and substitutes `{out}` unquoted into an
`sh -c` string (`DEFAULT_GEN_CMD` ~1793 has `--out {out}`). `generate.sh`
(~417) has the same hole. Fix: require ids to match
`^[a-z0-9]+(-[a-z0-9]+)*$` and be unique within a round (a model reply that
fails goes back through the existing retry-with-feedback path); pass prompt,
out, ref, and size to the generator as environment variables or argv rather
than splicing them into shell text. Test: an id with `;`, `$(`, space, or
`../` is rejected; duplicate ids are rejected.

**WP-1.2 Publish dry run and committed-only site inputs.** `publish.rs`
(~45-64) writes `publish.yaml` on `--dry-run` with `url` set to the rclone
remote path. `site/mod.rs` reads `publish.yaml` (~238) and `edition.yaml`
(~193) from the working tree. Fix: dry run writes nothing (print what it
would write); site reads both files through `git show HEAD:<path>` so an
uncommitted edit can never ship, matching CLAUDE.md.

**WP-1.3 Model caller retries and timeouts.** `caller.rs` (~240-255) feeds
transport failures (timeout, spawn error, 429) back to the model as format
rejections and retries with no backoff; a timeout retries at full length.
`wait_with_timeout` (~356, ~475) kills only the direct child, and joining
the pipe readers can then hang on grandchildren. Fix: separate transport
errors from parse errors; retry transport errors with backoff and the
original prompt; do not retry timeouts; spawn with `process_group(0)` and
kill the group on timeout. Replace the hand-rolled `Semaphore` (~144) with
`thread::scope` plus a bounded work queue if that reads shorter.

**WP-1.4 Capture validates first and writes atomically.** `--article` is
checked only inside `plan_cmd::add_source`, after the paid transcription and
after `record.yaml`, `release-state.yaml`, and `sources.md` are written
(`capture.rs` ~1019); a failure leaves the source queued but planless, and a
re-run stops with "already exists" (~958). Fix: resolve the edition and the
`--article` row before `transcribe`; add one `write_atomic(path, bytes)`
helper (temp file in the same directory, then rename) and use it for every
YAML and Markdown write in capture, plan, produce, art, and publish.
Re-parse `release-state.yaml` after its text edit, as `plan_cmd` already
does for plan edits.

**WP-1.5 Produce front matter.** `produce.rs` `front_matter` (~871-903)
reads `edition.yaml`, waits minutes on a model call, then writes back the
stale copy. Fix: re-read after the call and substitute only TODO lines that
are still there. The hand-rolled quoter `yq` (~457) mistypes `true`,
`null`, `~`, `1984`, leading `- ` or `?`, and newlines: emit scalars with the
YAML library (or always single-quote).

**WP-1.6 Run directory collisions.** `run-{now_stamp()}` with
`create_dir_all` (`produce.rs` ~684) lets two runs started in the same second
share a directory and log. Use `fs::create_dir` and treat `AlreadyExists` as
an error (or suffix it). Same for `art.rs` round dirs (~2026).

**WP-1.7 Translation preserves code by content.** `translate.rs` (~122)
compares only the number of fence markers. Extract fenced blocks from both
texts and require byte equality; drop the `english_sha256` echo check (~102),
which proves only that the model copied a string.

**WP-1.8 Render fails loud.** `template.rs` (~114-125) prints only "did not
converge" warnings and drops the rest. Print all Typst warnings and fail on
unknown font family and missing glyph. `legible.rs` (~94, ~130) stops
enlarging figures for the rest of the edition when tesseract is missing,
after some figures already changed from the cache: check for tesseract up
front and fail, unless an explicit `--no-legibility` flag is passed.

**WP-1.9 Path and PDF hardening.** Reject `..` and absolute components in
staging (`render.rs` ~236, `typeset/mod.rs` ~27-36); the traversal refusal in
`content.rs` runs only after the copy. Add a cycle guard (visited set or
depth cap) to every `/Parent` walk (`pdf_text.rs` ~119, `impose.rs` ~122,
`preflight.rs` ~125); `pdf_text` runs on user-supplied PDFs at capture.

**WP-1.10 Em dashes out of Rust strings.** Remove U+2014 from prompt and
copy strings: `produce.rs` `INLINE_PREAMBLE` (~11, sent with every writer,
art, and front-matter call), ~776, ~794; `art.rs` ~142, ~306, ~324, ~393
(the em dash before "variation {n}" on every image prompt); `translate.rs` ~75, ~108, ~124;
`caller.rs` ~279; `plan_cmd.rs` ~404. Add a test that greps `src/` for
U+2014 outside captured-text fixtures.

**WP-1.11 Small items.**
- `capture.rs` `curl_text` (~55) decodes every page as UTF-8: honour the
  declared charset.
- `print_cmd.rs`: add a Chrome timeout; percent-encode the `file://` URL
  (~211).
- `caller.rs` (~536): codex calls count as $0; record unknown cost as
  unknown, not zero.
- `tests/site.rs` runs `mag site` against the live repo and writes
  `.magazine/site/`: point it at a temp output dir.

**WP-1.12 Capture gate checks recall and order.** Found during WP-2.3:
`capture.rs` `fidelity_gate` only checks that the transcription's words
appear on the page (2% miss budget), so a transcription that drops or
reorders paragraphs passes, against "substantive text, verbatim, in source
order". Record where each matched window lands in the folded page text,
require those positions to increase, and fail when the longest run of page
words no window covers inside the first-to-last match span exceeds a
calibrated limit (fenced code, headings, table cells count as covered).
Calibrate on the committed library captures whose raw HTML is still in
`.magazine/capture/`; test that a dropped paragraph and a swapped pair are
rejected.

## Phase 2: delete and restructure

**WP-2.1 Library crate.** Add `src/lib.rs` with the modules and a thin
`src/main.rs`. Tests `use mag::...`; delete every `#[path = "../src/..."]`
include (22 of 25 test files; `shared.rs` currently compiles 14 times) and
the hand-built `mod critic { pub use super::metrics; }` shims. Remove the six
module-wide `#[allow(dead_code)]` in `main.rs` and the import-only seam tests
(`main.rs` `trace_seam_is_reachable`, `critic.rs`
`parity_seam_is_reachable_from_critic`, `typeset/mod.rs` ~173,
`tests/trace_seam.rs`). `pdf_text` moves out from under `capture.rs`'s
`#[path]` to a normal module.

**WP-2.2 Dead code.** Measured with
`RUSTFLAGS="--force-warn dead_code" cargo check --bin mag`: about 420 lines.
Delete `model/records.rs` ~10-234 (Python `urlsplit` / `quote_plus` /
`parse_qsl` port, `canonicalize_url`, the second `source_id`, `NewRecord`,
`SourceRecord::create` / `to_json` / `key_order`) and the tests that assert
that dead `source_id`; `model/doc.rs` `visible_blocks`, `flatten`,
`inline_visible`; `critic/text.rs` `trace_text`; `critic/rules.rs`
`decisions`; `critic/metrics.rs` `PreparedPrintImage.image` and
`unresolved`; `cover/outline.rs` `width`; the `#[allow(unused_imports)]` in
`trace.rs`. Done when `cargo clippy` is clean with no dead-code allow left.

**WP-2.3 Tests: oracles out, invariants in.** Delete the `*_expected.json`
and `*_expected.txt` oracle dumps, their fixture dirs where nothing else uses
them, the tests that compare against them, and `tests/pinned_inputs.sha256`.
Keep or write focused tests for the promises the project actually makes:
- fenced code is byte-exact through render and through translation;
- extract markers that are ambiguous, or a manuscript that already carries
  the run, are refused;
- article text cannot inject Typst markup (`escape_markup`,
  `string_literal`, `project()` re-parse);
- the capture fidelity gate rejects a transcription that drops or rewords
  prose and accepts an exact one;
- `capture::source_id` is stable for a few pinned URLs and titles (it names
  library directories);
- art brief ids and shell quoting (WP-1.1);
- run-dir and edition-id resolution (WP-1.6, WP-3.3);
- the no-comments and no-em-dash checks.
Fix CLAUDE.md: it documents `MAG_BLESS=1`, which no code reads. Either drop
the sentence or, if any snapshot survives, implement one bless switch and
document that.

**WP-2.4 Delete the WeasyPrint shim. [visual]** `text_shim.rs`
(`WEASYPRINT_69 = true`, glyph-advance rewriting ~293-337 that changes widths
after Typst broke the lines), `template.rs` ~162-432 (`weasyprint_links`,
`weasyprint_chips`, `weasyprint_paint_order`, `weasyprint_annotations`),
`runt.rs` `weasyprint_hyphenates` / `suppressed` (~314, ~444), `hyphen.rs`
`PARITY` / `weasyprint69_skip`, and the flush-right / justify repair in
`shifted()` that exists to compensate. Around 700+ lines. Typst's own
output, links, and annotations stand as they are. Before/after render to
Fran.

**WP-2.5 Delete the CPython emulation. [visual]** `model/shared.rs`:
`py_casefold` / `py_upper` and their ~15 KB Unicode tables, `py_str`
(null -> "None"), `py_repr`, `truthy`, `py_strip` / `PyStrip`, the PyYAML
`!!null` workaround in `load_yaml` (~115-158). Roughly 100 call sites in
`manifest.rs` plus `content.rs` and others. Use Rust string methods; a
non-string where a string is expected is a load error; `to_int`
(`manifest.rs` ~2138) errors on a bad value instead of returning 0 or 1.
Known visible bug this fixes: an empty `subtitle:` prints "None" in the PDF
and nothing on the site.

**WP-2.6 Dependencies.**
- Drop `typst-library` (used only through `typst`'s re-exports).
- `serde_yaml` 0.9 is archived: move to `serde_norway` or `serde_yaml_ng`
  (pick the one that is maintained and API-compatible at execution time).
- Codec overlap: `png`, `zune-jpeg`, `zune-core`, `image-webp`, `gif` sit
  beside `image` (png, jpeg, webp). Remove each one whose use `image` covers;
  keep a crate only where it does something `image` cannot, and say which in
  the commit message.
- Collapse duplicate lockfile versions where a bump allows (`gif`
  0.13/0.14, `sha2` 0.10/0.11, `base64` 0.22/0.23).
- `render.rs` `toml_value` (~193-217) hand-parses `magazine.toml` and breaks
  on inline comments: use the `toml` crate already in the tree.
- Record the reason for the exact pins (`typst`, `resvg`, `usvg`,
  `tiny-skia`) in `docs/ARCHITECTURE.md`; re-evaluate whether they are still
  needed once the oracle snapshots are gone.

**WP-2.7 Duplicate helpers and regexes.**
- One HTML escaper (`art.rs` ~524, `site/html.rs` ~20, `print_cmd.rs` ~473).
- One `read` helper (`plan_cmd`, `produce`, `translate`, `art`).
- One `prompts_path`; drop the unreachable `CARGO_MANIFEST_DIR` fallback in
  `produce.rs` ~29.
- One parallel-jobs helper on `thread::scope` (`produce.rs` ~745,
  `translate.rs` ~180).
- Every `Regex::new(...).unwrap()` in a function body becomes a
  `LazyLock<Regex>` (37 in the pipeline modules, one inside a loop at
  `capture.rs` ~368; `cover/raster.rs` ~7, ~17).
- Replace `partial_cmp(...).expect("finite baselines")` with `total_cmp`
  (`runt.rs` ~179, ~261, ~428).
- `template.rs` ~70 `pages().len() - 2` underflows: `checked_sub` with an
  error. `estimate.rs` ~66 `self.0[face]` panics on an unknown face: return
  an error.

**WP-2.8 CLI shape.** Give every subcommand a `#[derive(clap::Args)]`
struct, as `Render`, `Site`, and `Publish` already have, and replace the
`run_text` / `run_visual` split (both ending in `unreachable!()`) with one
flat `match` that hands each struct to its module.

## Phase 3: typed data model

**WP-3.1 Enums.** `#[derive(ValueEnum, Deserialize, Serialize)]` with
`rename_all = "snake_case"` for: content mode (`plan_cmd.rs`
`CONTENT_MODES` ~177, `produce.rs` ~17, ~397), print layout
(`print_cmd.rs` ~75, ~102), render operation (`render.rs` ~469, ~550,
`site/mod.rs` ~212, `layout.rs` ~566), art brief purpose (about ten string
compares in `art.rs` plus `size_for`), figure layout / tone / fit, extract
style (`records.rs` ~622-637 const arrays; matched as strings in
`legible.rs`, `site/html.rs`, `content.rs`, `tone.rs`). Matches become
exhaustive.

**WP-3.2 One typed loader.** `model/` has no serde derive: `manifest.rs`
walks `serde_yaml::Value`, checks a field, then re-reads it with
`.expect("the title is present")` (~839, ~856, ~1037, ~1053, ~1223, ~1416,
~1563). `Edition` keeps `raw: Value` and `cover: Mapping`, and 17 call sites
outside `model` dig into `raw` (`content.rs` ~259, ~686, ~844, `layout.rs`
~358, `site/html.rs` ~567, `typeset/cover.rs` ~323, ...). `edition.yaml` is
re-parsed raw in `render.rs` ~506, `site/mod.rs` ~193, `produce.rs` ~637,
`sourcecodes.rs` ~254, `art.rs` ~707; `record.yaml` in `plan_cmd.rs` ~166,
`sourcecodes.rs` ~277, `render.rs` ~892. Fix: derived structs with
`deny_unknown_fields` for edition, article, manuscript, figure, extract,
art, cover, and source record; a `validate()` pass for cross-field rules
that keeps the existing collect-all-errors `ValidationError(Vec<String>)`;
every module reads through it and `raw` is deleted. Text edits that must
preserve comments (`plan_cmd` `append_rows`, `join_article`,
`append_missing_articles`, produce's TODO substitution) stay textual, then
re-parse through the typed loader to confirm. `deny_unknown_fields` will
surface stale keys in editions 001-013: fix the data or the struct, and list
what changed in the commit.

**WP-3.3 One edition id.** Three resolvers disagree: `plan_cmd`
(`matching_edition_dirs` / `plan_path_for` ~9-26, ~238-245, and
`queued_source_ids` by `starts_with`) silently takes the first prefix match
(`01` picks `010`); `capture::queue_in_release_state` (~612) requires an
exact match; `art::resolve_edition_dir` (~24) and
`render::resolve_edition_dir` (~159) are near copies that refuse ambiguity.
Fix: an `EditionId` newtype with one resolver that rejects ambiguity, used
everywhere.

**WP-3.4 In-process render request.** `render.rs` ~636 serialises a typed
`Request` to JSON and `typeset/mod.rs` ~45-113 parses it back into
`serde_json::Value` and reads camelCase keys (`primaryLanguage`,
`sourcePath`, `targetPath`). `layout`, `report`, and `release` pass the
layout around as `Value` (`release.rs` ~25-60 converts it back). Fix: pass
`&Request` and typed layout structs; write `request.json` only as an
artifact if still wanted.

**WP-3.5 Languages from data.** `render.rs` `stage_translation` (~841-871)
knows only `translations/es` and returns `["en","es"]` or `["en"]`, while
`primary_language` comes from `edition.yaml`. Derive the language list from
the translations present plus the declared primary language.

**WP-3.6 Remaining shapes.** `critic/rules.rs` builds rows as `Value` maps
and reads them back with `.expect("an object")` (~163, ~1088-1092, ~1791):
derive `Serialize`. Remove the three `#[allow(clippy::too_many_arguments)]`
(`manifest.rs` ~1016 `closing_plate` with four `&mut` accumulators and
~1714; `preflight.rs` ~395; `cover/outline.rs` ~195) with small structs.

## Phase 4: let Typst do the work

**WP-4.0 RESOLVED 2026-10-04: port, do not delete.** The critic is a
blocking gate (`package/release.rs` bails when the result is `fail`) that
enforces project rules (article page cap, page count a multiple of four,
blank inside covers, voids, contents pages), and the same path writes the
A4 booklet (imposition), the studio package, and `package.zip`. Keep all of
that; WP-4.1 ports how it reads the layout. Original question: Does anyone read
`render-critic.json`, the contact sheets, and the preflight report that
`package_release` writes? If not: delete the critic, preflight, contact
sheet, and `trace/` path outright and skip WP-4.1's port. If yes: WP-4.1.

**WP-4.1 Critic and preflight from the laid-out document.** Today
`typeset/release.rs` `publish` writes `reader.pdf`, and `package_release`
reopens it and parses content streams with `trace/streams.rs` (about 2,400
lines: its own matrices, fonts, ToUnicode CMaps, Flate / ASCII85 / PNG
predictor decoding) to rebuild text and image positions. The render already
holds `typst_layout::PagedDocument` with every frame, `TextItem`, image, and
position; `runt.rs`, `flow.rs`, and `layout.rs` already read it. Port the
critic rules and preflight to read frames, and delete `trace/streams.rs`,
`trace/exact.rs`, `trace/elements.rs`. Keep only file-level checks that need
the final spliced PDF (fonts embedded, embedded image resolution) as a small
lopdf pass. `pdf_text.rs` stays for capture of user PDFs: give it a single
resource-inheritance rule (merge the chain, error on a missing font instead
of returning an empty dict at ~118) and use lopdf's stream decoding.
`impose.rs` keeps its own needs but shares that resource helper.

**WP-4.2 Reuse the Typst World.** Each pass builds a new `Sources`
(`world.rs` ~44-75), re-reading and re-parsing 4.2 MB of fonts and rebuilding
`Library::default()` and `FontBook`; `World::file` (~96-108) re-reads every
raster from disk each time; a language takes up to about 9 compiles
(`composed` 1-2, `bound` up to 6, `paginate` 1). `estimate.rs` ~41 parses the
fonts again. comemo is never evicted. Fix: load fonts, book, and library
once and swap only the sources; cache file bytes by `FileId`; call
`comemo::evict` after each pass. Report render time against the WP-0.1
baseline.

**WP-4.3 One geometry module.** `layout.rs` `declared_pt` (~62) already
reads `template.typ`, and `flow.rs` / `legible.rs` use it, but values are
re-hardcoded in `runt.rs` ~15-21 (`MEASURE = 325.0`, `4.00395`, `-32.5`),
`estimate.rs` ~14-29 (`348`, `325`, `333.0079`, `595.2756`, `10.0046`),
`legible.rs` ~15 (148 mm), `layout.rs` ~365-371 (page caps 7 / 10,
duplicating `ARTICLE-PAGE-CAP` / `VERBATIM-PAGE-CAP` in the template), and
`typeset/cover.rs` ~714 (A5 MediaBox). Fix: `typeset/geometry.rs` loads them
all from the template once (`LazyLock`) and every module reads from it.

**WP-4.4 Text measurement. [visual if behaviour changes]** `estimate.rs`
measures widths with `ttf-parser` and no kerning, beside Typst's real
measurement. After WP-4.2, time a measurement compile. If it is cheap enough
for the call sites, measure through Typst and delete `estimate.rs`; if not,
keep the estimator, take its constants from WP-4.3, and add kerning. Record
the timing that decided it in the commit message.

**WP-4.5 Layout decisions as data. [visual]** `content.rs` emits Typst with
`format!` and exact layout, and four modules patch that text afterwards:
`runt.rs` `bind` / `bound` (~461-512, byte offsets, `a - PRELUDE.len()` can
underflow), `flow.rs` `block_start` (~236-301, hunts lines starting with
`#doc-`, `#doc-heading(` and inserts `#colbreak()`), `template.rs` ~69-79
(`replacen` that silently does nothing when its anchor is missing),
`layout.rs` `emitted_figures` (~327-354, re-parses its own output). Fix:
keep keeps, floats, breaks, binds, and plate positions as typed data keyed
by block id; either regenerate the markup from the model each pass with the
decisions applied, or have the template read a generated `decisions.typ`
dictionary. Delete the text patching. Output should be identical to the
post-Phase-2 render; anything that moves goes to Fran.

**WP-4.6 Cover as Typst pages. [visual]** The cover is SVG rasterised with
resvg at 300 dpi (`cover/raster.rs`), text written into a hand-built PDF
content stream limited to WinAnsi (`cover/pdf.rs` ~77-89), then spliced into
the interior with lopdf (`typeset/cover.rs` ~483-530). Set the front and
back covers as Typst pages in the same document: cover art as an image, the
masthead from the committed brand SVGs, the existing cover layout modes
(`framed`, `footer_caption`, `honored_plate`), inside covers blank. Delete
the content-stream writer, the splice, and whatever of `cover/` becomes
unused. Check all three cover modes against several arts before handing to
Fran. Render also writes the typeset front cover as `<lang>/cover.png`,
which `mag epub` consumes: keep producing it.

**WP-4.7 Image headers through `image`.** `typeset/media.rs` ~28-107 and
`package/preflight.rs` ~78-115 hand-parse PNG / JPEG / EXIF headers, and
`media.rs` reads the whole file on every `pixels()` call. Use `image`'s
`ImageReader::into_dimensions` and `ImageDecoder::orientation`. `world.rs`
~15 accepts only png / jpg and gives a confusing NotFound otherwise: accept
what `image` decodes or fail with a message naming the format.

**WP-4.8 Render makes no model call.** `render.rs` ~341-417 calls a model to
re-anchor figures unless `--no-model` is passed, against "rendering only
consumes". Move the anchoring to the step that writes `edition.yaml`
(produce or a dedicated check that reports unresolved anchors) and make
render refuse an unresolved anchor with a message naming the command that
fixes it. Remove `--no-model`.

**WP-4.9 Highlighter. [visual]** `highlight/` interprets a 688 KB
`tables.json` exported from Pygments lexers at runtime with `fancy_regex`,
and `Call.kind` is a string (`engine.rs` ~356). With Pygments parity gone,
try `syntect` (or `tree-sitter-highlight`) against the code blocks in the
committed editions. Switch if the print and site styling map cleanly onto
its scopes and the result reads at least as well; otherwise keep the engine,
make `Call.kind` an enum, and record why. Either way `fancy-regex` goes if
nothing else uses it.

**WP-4.10 Retire release-state.yaml; capture --refresh.** Added
2026-10-04 at Fran's request. `library/release-state.yaml` duplicates
`plan.yaml` (capture writes both), its `status` is `collecting` for every
edition including shipped ones, and only plan_cmd and capture read it. Its
one live fact is `intake_edition_id`. Delete the file; the default capture
edition becomes a `magazine.toml` key (or `--edition`); `mag plan` and
capture read membership from `plan.yaml`. Add `mag capture --refresh <id>`
that re-transcribes an existing source in place (article.md, media,
synopsis, sources.md entry) without touching any plan.

## Docs

- CLAUDE.md: the `MAG_BLESS` sentence (WP-2.3); describe render as
  "Typst layout, critic reads the laid-out document" once WP-4.1 lands; drop
  `--no-model` once WP-4.8 lands.
- `docs/ARCHITECTURE.md`: the module map after Phase 2 and Phase 4, the
  exact-pin rationale (WP-2.6).
- Save a memory when the plan closes, replacing this file's status line with
  the closing commit.

## Done when

- No `#[allow(dead_code)]`, `#[allow(unused_imports)]`, or
  `#[allow(clippy::too_many_arguments)]` in `src/`.
- No `#[path = ` in `tests/`.
- `grep -ri 'weasyprint\|py_str\|py_casefold\|python' mag/src` returns
  nothing meaningful.
- `serde_yaml::Value` / `serde_json::Value` appear only where the data is
  truly untyped (model replies before parsing), not in edition, record, or
  layout handling.
- `trace/streams.rs` is gone (or WP-4.0 removed the whole path).
- Render time per language is reported against the WP-0.1 baseline.
- Fran has approved the last [visual] render.
