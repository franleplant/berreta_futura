# WP-5.4g + WP-5.3g comparator switches

## Base

`art_directed` `f981635`, detached worktree `.../tmp/wp54g`, its own `mag/target`.
Tracked run `editions/010/run-2026-09-13T01-34-51`, `--langs en` (the comparator's default).

## What changed

- **WP-5.4g, domain 1..n** (`mag/src/parity.rs`): `build_verdict` compares reader.pdf pages
  1..n (counts must be equal and at least 1), so every Tier S, G, V and E clause now covers
  the cover faces. The page sets stay on the interior (2..n-1), as `parity.yaml page_sets`
  defines them. `baseline.json` gains rows 1 and 56 at tier `none` with no clauses (WP-0.2k's
  seed rule; raising them from the proposal is a verifier's), and its `schema_note` says so.
  `parity.yaml font_name_map.cover_faces_note` records what the faces embed on each leg.
- **WP-5.3g, critic clause** (`mag/src/parity/critic.rs`, new): Tier S `critic` is
  evaluated from both legs' `en/render-critic.json` and joins the gate (`tier_s_pass`) and the
  per-page clause list. Two parts, both required for `pass`:
  1. Report leaves: every leaf of the two reports is compared exactly except the
     `tiers.s.critic.excluded_leaves` groups in `parity.yaml` (raster-derived measurements,
     the two pypdf-vs-tracer text counts, the two PDF hashes), each with its argument. Result,
     summary, every issue (code, page, severity, message), every check flag and per-page
     decision stay compared. A report present on one leg only fails; absent on both is
     `not_evaluated` (the lopdf fault fixtures carry none).
  2. Text check: the Rust critic's text source (`critic::rules::read_leg`) run on BOTH legs'
     reader, booklet, interior and cover PDFs, every page; `body_text_lines`,
     `standalone_punctuation_lines` and text emptiness must be equal. `text_characters` is
     reported, not gated (argument below and in `parity.yaml`).
- **Critic fix** (`mag/src/critic/text.rs`): whitespace-only shows are skipped, no separator
  is added next to a show edge that is already whitespace, each line is trimmed, and the shows
  merged into one line are ordered by x instead of by baseline. `standalone_punctuation_lines`
  became `pub(crate)` for the text check.

## The cause of WP-5.6's critic discrepancy

WP-5.6 (`evidence/WP-5.6.md`, "For the orchestrator") compared the two legs' reports and saw
1-2.6% more `text_characters` on 46 typst pages and `body_text_lines` differing on 7. Two
separate causes:

1. **The two reports come from different critics.** The bridge (oracle leg) runs Python's
   `package_release`, whose critic reads text through pypdf; the typst leg runs the Rust critic
   (tracer text). On reader page 3 the Rust critic reads 662 characters from BOTH PDFs, while
   the oracle report's 653 is pypdf's. That is WP-5.3d's path B (the tracer does not reproduce
   pypdf's merged headlines and synthetic spaces), so those two counts are excluded from the
   report comparison and the Rust fields are compared Rust against Rust instead.
2. **The Rust critic read the two PDFs differently.** Tracing both legs with the unchanged
   critic, the page texts differed on 45 of 56 reader pages, 25 of 28 booklet sides and 25 of
   26 interior sides. Typst writes glyphs WeasyPrint does not: a space at the end of every
   justified line, and a U+00A0 show of zero advance on each side of inline code (the padding);
   the critic kept them as text. On booklet sides, a left-page line and a right-page line
   within 1 pt of the same baseline were joined in baseline order, so whichever page sat 0.3 pt
   higher came first with a negative gap and no space ("ontoPractical" on the oracle, "onto
   Practical" on typst, only because of typst's trailing space). The fix removes all three.
   After it, all compared fields agree on all 111 pages; the texts still differ on 5 reader
   pages (and the same paragraphs on 5 booklet and 5 interior sides), by one space each.

The residue is `text_characters` only: typst sets five two-word last lines ("us wisely.",
"weight theft.", "Composer 1.5.", "find patterns.", "product teams.") as two shows with no space
glyph, the space being a positioning gap. The critic adds a space only past 0.25 em beyond an
extrapolated run width, and the Source Serif word space is 0.235 em (measured in the oracle's
"us wisely." show: space advance 25668 quanta = 2.35 pt at 10 pt), so it welds "uswisely." on
the typst leg. This is a critic limitation, not a writer fault. Closing it needs each run's pen
end and a lower threshold, and `Element::Text` carries no pen end. Adding one means changing the
constructor in `mag/tests/critic_text.rs` (WP-5.3c's), and the critic test shims re-export only
`trace_elements`, so a side channel is not reachable either. `text_characters` feeds no issue
site (grep of `rules.rs`: the text-derived sites read `blank`, `ink_free`,
`standalone_punctuation_lines` and `body_text_lines`), so it is reported and not gated.

## Commands and results

```sh
cargo fmt --check                                     # 0
cargo clippy --all-targets -- -D warnings             # 0
cargo test                                            # 0; 32 result lines, 935 passed, 0 failed
MAG_PARITY_OUT_DIR=<s1> mag parity 010 --run editions/010/run-2026-09-13T01-34-51   # 0
MAG_PARITY_OUT_DIR=<s2> mag parity 010 --run editions/010/run-2026-09-13T01-34-51   # 0
```

Both staged runs from empty out dirs (no oracle cache, both legs rendered fresh):
staged fresh `bc49b2aa...`; ratchet pass (target E, 54 committed entries checked, 56 recorded,
56 measured, 0 regressions); S page_count 56 vs 56, boxes pass (168 boxes, 56 rotations),
text pass (56 pages), color pass (59252 entries), navigation pass (85 links, 51 outlines, 1
title, 1 lang); **critic pass: results pass vs pass, 4 issues, 1999 report leaves compared,
1022 excluded, 0 differ; Rust text fields on 111 pages, 0 differ; text_characters 15 pages
differ (reported)**; G 56 pages, max dy 0.006 pt; E glyph positions pass (59073 glyphs, 1529
shows, 0 violations); E display list pass (59304 vs 59304); V 56 pages, worst fraction 0.000336.
Before this WP the same run measured 54 pages, 58623 glyphs and 58850 elements
(`evidence/WP-0.2y.md`), so pages 1 and 56 add 450 glyphs and 454 elements, and on both they
are raster-identical (Tier V fraction 0.0, max channel delta 0) with zero G displacement.
The two verdicts are identical after removing `a_reader_sha256` (WeasyPrint dates it), the
render-dir stamps and the out-dir path (normalized sha256 `5f57fe151c941799...`); both
`baseline-proposed.json` are equal and propose pages 1 and 56 at E with all six evaluated
clauses, and add `critic` to every page. `b_reader_sha256` is `6c03dda9...` on both, the value
WP-0.2y recorded, so the critic change does not touch the typst reader.

Controls, pre-rendered against the staged oracle leg:

| control | result |
|---|---|
| typst leg of WP-5.6's predecessor (`render-2026-09-24T04-37-08`, placeholder outer pages) | exit 1; text and color fail on exactly [1, 56]; V pages 1 and 56 at 0.965 and 0.666 |
| typst report with `issues[0].page` moved 17 -> 18 | exit 1, critic fail, `.issues[0].page: 17 vs 18` |
| typst reader.pdf swapped for the placeholder-cover one | exit 1, critic fail: text fields differ on reader p1, p5, p38, p56 |
| typst report with an excluded leaf changed (`pages[4].ink_ratio` +0.01, `text_characters` +5) | exit 0, critic pass (negative control for the exclusion list) |
| the two new `critic::text` tests against HEAD's `text.rs` | both fail; both pass with the fix |

Unit tests added: `parity::critic::tests` (an excluded leaf skips every index and every array
element beneath it; a decision leaf and a one-sided leaf differ; a prefix is not a match) and
`critic::text::writer_independent` (invisible space glyphs add no text; one line reads left to
right whatever its baselines' order).

## Verify clause not met: `--adhoc 008`

```sh
uv run python tools/sourcecodes.py 008                                        # 0 (worktree only)
mag parity --adhoc 008 --run editions/008/run-2026-08-30T13-59-32             # 1
```

The typst leg fails: `cannot read png header .../staged/library/sources/how-warp-builds-self-
improving-agents-on-claude-9e96ce55/media/001.jpg: Invalid PNG signature.` The failure is in
`package/preflight.rs` `figure_row` -> `critic::metrics::prepare_print_image` ->
`decode_rgb`, which decodes PNG only, and 008's figure is a JPEG. **It is pre-existing**: the
same command with this WP's changes stashed (HEAD `f981635`) exits 1 with the same message.
WP-5.6 made the typst leg run preflight natively; WP-0.2y's ad hoc 008 run (exit 0) predates its rebase onto WP-5.6, after which only 010 was re-run. Outside
this WP's Owns line, not fixed here. In that run the comparator falls back to oracle against
oracle and every Tier S clause, the critic included, passes.

## What is and is not proven

PROVEN (010, en): the comparator compares reader.pdf end to end (56 pages) and pages 1 and 56
hold every clause and tier E on both staged runs, with a positive control that fails exactly
those pages when the covers differ. The critic clause is evaluated and passing, discriminates
a moved issue and a changed PDF text, and ignores only the leaves `parity.yaml` names. With the
fix, the Rust critic's gated text fields agree on both legs' four PDFs on all 111 pages.
Verdicts are identical across two clean runs. Floor rows in `parity.yaml` are unchanged, and
the 54 interior baseline rows are unchanged.

NOT PROVEN / open:
- `--adhoc 008` exit 0 (pre-existing typst-leg preflight failure on JPEG figures; above).
- `text_characters` agreement: it still differs by one on the five two-word last lines. The fix
  needs a pen-end field on `Element::Text`, which reaches `mag/tests/critic_text.rs`.
- Equality is not correctness for the report comparison: the Python critic judges the oracle
  PDF and the Rust critic the typst PDF, so an issue both critics miss passes. The critic fault
  suite (WP-5.3c) covers what they catch.
- `tests/critic_text.rs reconstructs_edition_010_text` (opt-in, `MAG_CRITIC_READER_PDF`)
  fails on today's oracle reader, total body lines 1126 against the pinned 1117, with this
  WP's changes and without them, so the pin is stale and this WP did not cause it.
- `tests/parity_ratchet.rs` exercises the committed baseline's first page key, which becomes
  "1" at tier `none`, so its tier-lowering branch skips until a verifier raises pages 1 and 56.
