# WP-2.1 content pipeline: staged inputs to Typst source tree

## Base

- Branch `art_directed`, the recorded command block was run to completion against `c1253d8`; the commit is replayed unchanged onto `f7ca38e` (plan revision 46), whose two intervening commits touch only the plan and `WP-0.2g.verify.md`, neither of which this WP reads or depends on.
- Owns: `mag/src/typeset/content.rs`, `mag/tests/typeset_*`.
- One edit outside that list, unavoidable and registration-only:
  `mag/src/typeset/mod.rs` gains `#[allow(dead_code)] pub(crate) mod content;`
  plus an in-crate consumer test. A module that no `mod` statement declares is
  not compiled, so the WP cannot be landed without it. The `allow(dead_code)`
  matches the convention `mag/src/web.rs` already uses for a ported module with
  no CLI caller yet, and WP-2.2a removes it when the template calls the
  pipeline. No Cargo file changed: `typst-syntax`, `unicode-normalization`,
  `serde_json` and `serde_yaml` were already dependencies.

## Commands

Run from the root of the checkout under test. The only input from outside the
checkout is the render request, which names an untracked run directory; it is
supplied by the operator rather than written into this block, so nothing here
hard-codes a path into any particular tree.

```sh
STAGE=$(mktemp -d)
REQUEST=${MAG_TYPESET_REQUEST:?point this at a render request.json whose run directory is staged}

# Fixture oracles. Regenerating them must reproduce the committed files byte for
# byte; diffing regenerated copies discriminates whether or not they are tracked.
for e in 900 901; do
  uv run python mag/tests/typeset_oracle.py project \
    --root mag/tests/typeset_fixtures/corpus --edition $e \
    --publication-name "Fixture Press" --out "$STAGE/regenerated-$e.json"
  diff -u "mag/tests/typeset_fixtures/expected-$e.json" "$STAGE/regenerated-$e.json"
done

# The hermetic suite: fixtures, refusal matrix, straddles, escaping round trip.
(cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test)

# The live edition. Staged from THIS checkout by overriding artifactRoot, so the
# inputs come from the worktree under test and not from whatever tree wrote the
# request. The run directory editions/010/run-2026-09-13T01-34-51 is untracked,
# which is why this leg is env-gated rather than hermetic.
uv run python mag/tests/typeset_oracle.py stage \
  --request "$REQUEST" --into "$STAGE/live" --artifact-root .
uv run python mag/tests/typeset_oracle.py project \
  --root "$STAGE/live" --edition 010 --publication-name "Berreta Futura" \
  --out "$STAGE/oracle-010.json"
(cd mag && MAG_TYPESET_ROOT="$STAGE/live" MAG_TYPESET_ORACLE="$STAGE/oracle-010.json" \
  MAG_TYPESET_PUBLICATION="Berreta Futura" \
  cargo test --bin mag the_live_edition -- --nocapture)

# Rule 10 discrimination: the live clause must fail when the oracle moves.
uv run python - "$STAGE" <<'PY'
import json, sys
from pathlib import Path
stage = Path(sys.argv[1])
oracle = json.loads((stage / "oracle-010.json").read_text())
edited = dict(oracle)
edited["text"] = oracle["text"].replace("The Speed Limit", "The Speed Limits", 1)
(stage / "oracle-tampered.json").write_text(json.dumps(edited))
cut = dict(oracle)
cut["text"] = oracle["text"][:-40]
(stage / "oracle-truncated.json").write_text(json.dumps(cut))
PY
for case in tampered truncated; do
  (cd mag && MAG_TYPESET_ROOT="$STAGE/live" MAG_TYPESET_ORACLE="$STAGE/oracle-$case.json" \
    MAG_TYPESET_PUBLICATION="Berreta Futura" \
    cargo test --bin mag the_live_edition) && echo "UNEXPECTED PASS $case"
done

# Corpus facts quoted under Metrics, re-derived here rather than cited.
uv run python - "$STAGE" <<'PY'
import glob, json, re, sys
from pathlib import Path
stage = Path(sys.argv[1])
oracle = json.loads((stage / "oracle-010.json").read_text())
print("010 reader text characters:", len(oracle["text"]))
print("010 reader text bytes:", len(oracle["text"].encode("utf-8")))
print("010 verbatim runs:", len(oracle["verbatim"]))
manifest = (stage / "live/editions/010/edition.yaml").read_text(encoding="utf-8")
print("010 articles:", manifest.count("\n- id: "))
print("010 extracts rows:", manifest.count("extracts:"))
fences = sum(
    len(re.findall(r"^```", Path(p).read_text(encoding="utf-8"), re.M))
    for p in glob.glob(str(stage / "live/editions/010/articles/*.md"))
)
print("010 fence lines:", fences)
PY
```

## Tool versions

- rustc 1.96.0 (ac68faa20 2026-05-25), `typst-syntax` pinned `=0.15.1`,
  `pulldown-cmark` 0.13 with `default-features = false`,
  `unicode-normalization` 0.1.
- CPython 3.12.11 through `uv run python`. Two Pythons exist on this machine
  with different Unicode versions, so every command above uses `uv run python`
  and none uses a bare `python3`.
- markdown-it-py 4.2.0, Pygments 2.21.0 (the oracle leg's markdown and code
  highlighting).

## Metrics

Measured, not cited. Every number below is produced by the last command block.

| quantity | value |
| --- | --- |
| 010 reader text, characters | 68,758 |
| 010 reader text, bytes | 69,097 |
| 010 articles | 9 |
| 010 extracts rows | 0 |
| 010 fenced-code fence lines | 0 |
| 010 verbatim runs in the projection | 0 |
| fixture 900 reader text, characters | 1,751 |
| fixture 900 verbatim runs | 2 |
| fixture 901 reader text, characters | 456 |
| in-crate tests passing | 89 |

010 carries no extracts and no fenced code, which is why the two committed
fixture editions exist: without them every extract and code path in this WP
would be dead on the only live corpus.

## Verdicts

**The target clause.** `mag/src/typeset/content.rs` turns a staged root into an
in-memory Typst source tree, and the tree's plain-text projection is byte-equal
to the WeasyPrint leg's pre-layout reader text for all of edition 010. The
oracle is `html_edition.render_html_edition`, the pure function the WeasyPrint
leg hands to layout; its text nodes are the reader-visible text before any
layout exists. Both sides are normalized by the Tier S rule (NFC, rejoin
line-end hyphens, strip soft hyphens, collapse whitespace runs).

**The projection is read out of the emitted Typst, not out of a parallel
in-memory walk.** `project()` parses each emitted file with `typst_syntax::parse`,
refuses on any parse error, and collects text from markup context only, so a
string passed as a named argument is data and a content block is reader text.
The walker **fails loud** on any markup leaf kind it does not account for; that
guard fired twice during development (on `#import`, and on an unescaped Typst
heading) and both are now covered by
`the_projection_refuses_markup_it_cannot_account_for`.

**Refusal matrix**, each exercised end to end through `pipeline()`, which is the
point: the refusals belong to `mag/src/model/` (WP-5.1b/c, accepted) and this WP
proves its pipeline surfaces rather than swallows them.

| case | classification | fixture |
| --- | --- | --- |
| ambiguous begin marker | threshold-discriminating (found 2) | `an_ambiguous_begin_marker_is_refused` |
| begin marker not found | threshold-discriminating (found 0) | `a_begin_marker_that_is_absent_is_refused` |
| ambiguous end marker | threshold-discriminating (found 2) | `an_ambiguous_end_marker_is_refused` |
| run already verbatim in the manuscript | message-only | `a_run_already_in_the_manuscript_is_refused` |
| unknown source id | message-only (set membership) | `an_extract_naming_a_source_the_article_does_not_carry_is_refused` |
| figure path escaping the source dir | message-only | `a_figure_path_escaping_the_source_directory_is_refused` |
| extracts maximum 2 | threshold-discriminating, straddled | `the_extract_maximum_straddles_two_and_three` |
| contents title limit 62 | threshold-discriminating, straddled | `the_contents_title_limit_straddles_sixty_two_and_sixty_three` |
| roster clamp 54 | threshold-discriminating, straddled | `the_roster_clamp_straddles_fifty_four_and_fifty_five` |
| roster shape 3 names / 6 words | threshold-discriminating, straddled | `the_roster_test_straddles_its_name_and_word_counts` |

The marker-count cases straddle naturally: 0 refuses, 1 is accepted by the
fixture itself, 2 refuses. The three numeric limits each run a fitting case and
a refusing case one unit apart. Every `mutated()` case asserts that the text it
is about to replace is still present, so a fixture edit that silently stopped a
case from biting fails rather than passes.

**Rule 10 discrimination.** The live clause was run against two perturbed
oracles, one word-level (`The Speed Limit` to `The Speed Limits`) and one
truncation (last 40 characters removed). Both fail. The clause also asserts the
oracle carries more than 10,000 characters before comparing, so an empty or
stub oracle cannot satisfy it.

**Rule 2b announcement.** `the_live_edition_projection_matches_the_oracle`
prints `skipped, env not set: ...` when unset and
`compared the live edition: 69097 characters of reader text, 0 verbatim runs`
when set, and panics if the three variables are set inconsistently. A reader of
a bare `cargo test` can tell which happened without reading the source.

**Rule 12.** No test reads an absolute path. The fixtures resolve through
`CARGO_MANIFEST_DIR`, the fonts through `CARGO_MANIFEST_DIR/..`, and the live
corpus arrives only through the announcing env gate. The staging command passes
`--artifact-root .` so the staged inputs are copied out of this checkout rather
than out of the tree that happened to write `request.json`. No `#[path]` include
is used anywhere in this WP: the tests are in-crate unit tests that import
`crate::model::*` the ordinary way, and `mag/src/typeset/mod.rs` carries a
consumer test that imports `crate::typeset::content` as a sibling module would.

## Residuals

1. **`normalize_reader_text` duplicates `mag/src/parity/text.rs::normalize`.**
   Same semantics, different name to clear the crate-wide duplicate audit. I
   could not import the accepted copy: `mag/src/parity.rs` declares `mod text;`
   privately, `mag/src/parity*` is not in this WP's Owns, and WP-0.2g has live
   uncommitted work in those files. Per the duplicated-helper rule each copy is
   pinned to its own oracle rather than to its sibling: mine to
   `typeset_oracle.py`'s `normalize` over the HTML, the parity copy to the PDF
   text path. A later WP that owns `mag/src/parity*` should lift one copy into a
   shared module.
2. **WP-5.5a will collide on the UI strings.** That WP ports
   `render_html_edition` to `mag/src/web/`, which means a second `ui`,
   `clamp_roster`, `is_name_roster` and `content_label`. The duplicate audit
   (`mag/tests/rust_helpers.rs`) will force the reconciliation. WP-5.5a should
   import from `crate::typeset::content` rather than redefine, or both should
   move to `mag/src/model/`.
3. **Caption and credit are glued in the projection**, and so are the contents
   entry's label, title and author, and the article label's primary and
   secondary spans. That is faithful: in the oracle HTML they are adjacent
   inline `<span>`s inside one block, and only CSS separates them visually. The
   emitter reproduces the gluing deliberately by emitting those runs as adjacent
   calls with no markup whitespace between them. **WP-2.2 must not change this**
   without changing the oracle comparison with it.
4. **Code-run comparison trims trailing newlines on both sides.** The oracle's
   fenced-code path runs Pygments and then `.rstrip("\n")` when a lexer resolves,
   but not when it does not, so the trailing-newline count depends on whether
   Pygments happens to ship a lexer for the info string. Trailing newlines are
   not printable content, so both sides are compared after
   `trim_end_matches('\n')`. This is the one place the comparison is not
   byte-for-byte, and it is stated rather than hidden.
5. **Escaping is total, not minimal.** Every ASCII punctuation character in
   reader text is backslash-escaped, because Typst's lexer treats a backslash
   followed by any non-whitespace character as a literal escape. That makes the
   emitted source noisy to read and removes any need to reason about which
   characters are markup-significant in which position. `--` would otherwise
   become an en dash and change the text.

## What is and is not proven

**Proven.** For edition 010 and two committed fixture editions, the emitted
Typst source tree's reader text equals the WeasyPrint leg's pre-layout reader
text exactly, under the Tier S normalization; the emitted source parses as valid
Typst; extract runs are contiguous byte-exact runs of the captured
`article.md`; the ten refusals above reach the caller.

**Not proven, and owned elsewhere.**

- **Nothing about layout.** This is a pre-layout comparison. Page count, folios,
  running heads, TOC page numbers, figure placement and same-page equality are
  WP-2.2 and WP-3.4. Tier S's per-page text clause is a different check against
  a rendered PDF and is not touched here.
- **The tree does not compile.** `main.typ` opens with
  `#import "/template.typ": *` and calls functions no one has defined yet.
  Parsing succeeds, which is all the projection needs; `typst::compile` will not
  until WP-2.2a writes `template.typ`. This is the seam, not a defect, but it
  means no one has yet demonstrated that these calls can be given a definition
  that renders.
- **Soft-hyphen injection is absent by decision**, not omission: WP-1.5 chose
  option (b), so the "if WP-1.5 chose (a)" clause of the brief is dead.
- **The es locale is untested.** `ui()` carries the Spanish table because the
  Python function does, but the compared domain is 010 en only and no fixture
  exercises Spanish. The first WP to need it must pin it to the Python oracle.
- **Pygments tokenisation is not reproduced.** The oracle wraps highlighted code
  in `<span>`s that carry no text of their own, so the projection is unaffected,
  but the print CSS colours those classes and Tier S compares text-run fill
  colours. That comparison is WP-2.2/WP-3.3's, and this WP records only that the
  language tag reaches the tree as `doc-code(lang: ...)`.

## What WP-2.2 needs from this

- The tree is `Vec<File>` with `main.typ` first, then one file per piece, in
  document order; `main.typ` carries `#include "/<path>"` for each.
- **The contract the projection enforces: reader-visible text is passed as
  markup content, structural data as code-mode strings.** Put a caption in a
  string argument and it silently leaves the reader text; put an id in a content
  block and it silently joins it. The fail-loud walker catches unknown markup
  but cannot catch this, so it is a discipline, not a guard.
- Function names the template must define: `edition-header`, `publication-name`,
  `issue-line`, `edition-title`, `edition-subtitle`, `edition-date`, `contents`,
  `contents-kicker`, `contents-label`, `contents-entry`, `entry-label`,
  `entry-title`, `entry-author`, `piece`, `content-label`, `label-primary`,
  `label-secondary`, `label-separator`, `label-date`, `piece-title`, `byline`,
  `byline-prefix`, `byline-name`, `author-note`, `provenance`, `source-link`,
  `figure-block`, `figure-caption`, `figure-credit`, `extract`, `quote-line`,
  `extract-caption`, `key-ideas`, `key-ideas-label`, `key-idea`, `end-mark`,
  `tail-art`, `closing-plate`, `doc-heading`, `doc-paragraph`, `doc-code`,
  `doc-quote`, `doc-list`, `doc-item`, `doc-rule`, `inline-code`, `doc-link`.
  `emph` and `strong` are Typst's own.
- `doc-paragraph` carries `standfirst` and `roster` flags, `doc-list` carries
  `references`, `piece` carries `opener: "illustrated_paper_spots_v1" | "plain"`,
  and the illustrated path emits the standfirst inside the opener header while
  the plain path emits a `provenance` line instead of a header source link.
  These reproduce `_render_illustrated_article` and `_article_header_lines`.

## Status

Accepted for review. The target clause is met on the full live corpus and on the
two fixture editions that cover what 010 cannot reach.
