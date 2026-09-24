# WP-5.1h part 1: container labels, strict content decode, shared web helpers

## Base

Worktree cut from `art_directed` at `cc1ae09`. Owns (per the dispatch brief):
`mag/src/impose.rs`, `mag/src/pdf_text.rs`, `mag/src/model/shared.rs`,
`mag/src/web/**` and their tests. `typeset/**` and `parity*` untouched
(`git diff --stat` lists only owned paths plus the new test file and this
evidence).

## 1. The reported `label: []` and `!!null` divergences

### Reproduced on both sides

Python, through the real frontmatter path (`parse_publication_document`),
`uv run python probe.py`, exit 0:

| frontmatter | Python type | `str(value)` |
|---|---|---|
| `label: []` | tuple | `'()'` |
| `label: {}` | mappingproxy | `'{}'` |
| `label: [a, 1]` | tuple | `"('a', 1)"` |
| `label: {a: 1}` | mappingproxy | `"{'a': 1}"` |
| `label: [a]` | tuple | `"('a',)"` |
| `label: !!null` | NoneType | `'None'` (so the guard falls back to `ARTICLE`) |
| `label: !!null ''` | NoneType | `'None'` (same) |

Rust, `serde_yaml::from_str` then `shared::content_label` (throwaway test
binary, `cargo test --test zz_probe -- --nocapture`, exit 0, file removed
before commit):

| frontmatter | parsed | `content_label` |
|---|---|---|
| `label: []` | `Sequence []` | `"[]"` |
| `label: {}` | `Mapping {}` | `"{}"` |
| `label: [a, 1]` | Sequence | `"['a', 1]"` |
| `label: [a]` | Sequence | `"['a']"` |
| `label: !!null` | ERR `invalid value: string "", expected null at line 1 column 8` | n/a |
| `label: !!null ''` | ERR, same message | n/a |

**The `()` claim holds, and the mechanism is confirmed**: PyYAML loads a
list, and `publication_document.py:158` `_freeze` turns every frontmatter
sequence into a tuple, whose `str` is `()`. The plan's hypothesis was right.

### Classified

- **Container label: both engines wrong.** Neither `()` nor `[]` is a section
  label; each prints container syntax on a reader page. Matching Python would
  be equality, not correctness. The correct behaviour for a label that is a
  list or mapping is to refuse the manuscript. Reachability: the corpus
  carries 0 container labels (548 `label:` keys, 18 parsed values, all text,
  per WP-5.1f.verify.md "Metrics"), so this is latent, not live.
- **`!!null` spellings: Rust refuses where Python accepts.** The refusal comes
  from `serde_yaml` in `model/doc.rs::split_frontmatter` (and would equally
  come from `shared::load_structured`). It is a loud failure, not wrong
  output, on a spelling no manuscript uses. Not fixed here: the frontmatter
  parse site is `model/doc.rs`, outside this WP's Owns, and making
  `serde_yaml` accept the tagged null needs a pre-parse rewrite whose risk
  exceeds a zero-occurrence input. Recorded for the orchestrator.

### Fixed (web half)

`shared::scalar_label(metadata) -> Result<()>` refuses a `label` that is a
sequence or mapping with `Frontmatter label must be text, not <repr>`. The
web renderer's `read_document` calls it on every manuscript it parses, so
the web edition now fails loud instead of printing `[]`.
`content_label` keeps its `String` signature because `typeset/content.rs:442`
calls it and typeset is not this WP's; **the typeset path still prints `[]`
until part 2 calls `scalar_label` at its own parse site
(`typeset/content.rs:889`)**. This is a disclosed interim divergence between
the two Rust engines, on an input the corpus does not contain.

Test: `tests/model_shared_helpers.rs::a_container_label_is_refused_rather_than_printed_as_brackets`
pins the refusal for `[]`, `{}`, `[a, 1]`, `{a: 1}` and acceptance of text,
null, number, empty string and an absent key.

## 2. Strict content decode in `pdf_text.rs` and `impose.rs`

Both called lopdf's lenient `Content::decode`, which stops at the first
token it cannot parse and returns the operations before it as success
(mechanism per WP-0.2j.verify.md finding 1 and WP-0.2u.md item 3).

Reproduced before the fix, red tests written first:

- `pdf_text`: `HELLO @ BT ... (Lost line) Tj ET` transcribed as
  `"Hello world\n"`, silently dropping `Lost line`
  (`cargo test --test pdf_text stray`, 1 failed: "expected a loud failure
  ... got text \"Hello world\\n\"").
- `impose`: a 4-page reader whose pages share the resource name `/F1` with
  different fonts (so the second placed page goes through `rename_names`)
  and carry `@` before a painted rectangle imposed with `Ok`
  (`cargo test --test impose stray`, 1 failed at `expect_err`).

Fix: `Content::decode_strict` with context
`... holds a token lopdf cannot parse` at both sites. After:

- `pdf_text::a_stray_token_fails_loud_instead_of_truncating_the_page`:
  positive control (the same two text objects without junk read
  `"Hello world\n\nLost line\n"`), then `@` and `]` each fail loud.
- `impose::a_stray_token_in_a_renamed_page_fails_loud_instead_of_truncating`:
  positive control imposes, the renamed `/F1-0` is present and all 4
  rectangles survive; `@` and `]` each fail loud.

Scope note: `impose` only decodes a page that needs a resource rename; a page
with no rename is copied byte for byte, so a stray token there is passed
through unchanged rather than truncated. That is faithful, not lossy.

## 3. Shared exact-decimal path for `impose.rs`: NOT done, reported

`parity/exact.rs::authored` is the right tool (it binds reals in both
normal and object-stream objects), but it is unreachable without a parity
edit: `parity.rs` declares `mod exact;` privately, and `exact.rs` calls
`super::streams::decode_stream`, while `streams.rs` imports
`super::exact`. A `#[path]` include from `impose.rs` would therefore have to
compile both `exact.rs` (334 lines) and `streams.rs` (1,786 lines, with its
own `mod tests`) a second time under `impose`, duplicating the thread-local
`EXACT` map and every streams test. The clean route is one line in
`parity.rs`, e.g. `pub(crate) use exact::{authored, num};`, which is a
parity edit, so per the brief it is reported rather than taken. `impose.rs`
keeps its raw-byte regex recovery, which already fails loud (bails) on a
real it cannot recover, including every box inside an object stream.

## 4. Web helpers moved into `model/shared.rs`

Moved from `web/semantic.rs` into `shared.rs`, Python-exact forms, now
public for typeset to adopt in part 2:

- `anchor_key` (was `py_anchor_key`): `py_casefold(py_strip(..))`.
- `is_reference_heading` (was `py_is_reference_heading`).
- `article_opener_format(raw: &Value)` (was `py_article_opener_format(&Edition)`;
  takes the raw manifest value so `shared.rs` stays free of `manifest.rs`,
  which the 15 test binaries that `#[path]`-include `shared.rs` alone need).
- `raw_or` (Python `str(value or fallback)`), which `article_opener_format`
  depends on; `web/edition.rs` now imports it from shared.

**`inline_text` NOT moved, reported.** It walks `model::doc::Inline`.
`doc.rs` already imports `shared`, and 15 test binaries include `shared.rs`
by `#[path]` without `doc.rs`, so `shared.rs` cannot name `Inline` without
breaking those binaries. Its natural home is `model/doc.rs` beside `Inline`,
outside this WP's Owns. Web keeps its `plain_text`, identical to
`typeset/content.rs:837` `inline_text`.

Tests (`tests/model_shared_helpers.rs`) pin correct values, not Python
agreement: `anchor_key` strips U+001C..U+001F (Python `str.strip`) and
full-casefolds `Straße` to `strasse`; `is_reference_heading` accepts
`REFERENCIAS` padded with U+001E and rejects `Further references`;
`article_opener_format` is `""` for null, empty, a non-mapping `format` and
an absent key (the typeset copy gives `"None"` for null, WP-5.5a.md), and
strips the declared value; `raw_or` falls back on all seven Python falsy
spellings.

## Commands

All in `mag/`, `CARGO_TARGET_DIR` set to the worktree's own target:

```
cargo test --test pdf_text stray      # before fix: 1 failed (truncation reproduced)
cargo test --test impose stray        # before fix: 1 failed (Ok on a stray token)
cargo fmt --check                     # exit 0
cargo clippy --all-targets -- -D warnings   # exit 0
cargo test                            # exit 0: 737 passed, 0 failed, 0 ignored, 32 binaries
```

Oracle binaries inside that run: `tests/impose.rs` 5 passed (includes
`imposition_matches_the_python_oracle`, which asserts >= 9 display-list
comparisons, and the poppler raster/text oracle, which asserts the pinned
poppler 25.08.0 rather than skipping); `tests/web_port.rs` 15 passed;
`tests/pdf_text.rs` 16 passed (every committed fixture transcribes under
strict decode).

`tests/rust_helpers.rs` (the duplicate-helper lint) failed once after the
move, as it should: `anchor_key` and `is_reference_heading` now exist in
both `model/shared.rs` and `typeset/content.rs`. Four `ALLOWED` rows record
why (the typeset copies use `str::trim` and go away in part 2); part 2 must
delete those rows when it deletes the copies.

## What is and is not proven

- Proven: both reported divergences reproduce on both engines with the
  outputs above; the `_freeze` mechanism is the cause of `()`.
- Proven: lenient decode silently truncated in both `pdf_text` and `impose`
  (red tests), and strict decode fails loud with positive controls green.
  The committed pdf_text fixtures and the WP-5.2 impose oracles all decode
  strictly (they still pass), so no real input relied on leniency.
- Proven: the web now refuses a container label (unit-tested at
  `scalar_label`, wired in `read_document`). Not proven by an end-to-end web
  render with such a label; the wiring is one `?` line.
- Not done: typeset still prints `[]` (part 2); `!!null` refusal left as is
  (doc.rs, unowned); exact-decimal reuse in impose needs a parity edit;
  `inline_text` needs doc.rs.
