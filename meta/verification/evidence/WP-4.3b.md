# WP-4.3b English hyphenation ships (WP-4.3 option 2)

## Base

f258bf2 (art_directed). Fran chose WP-4.3 option 2 on 2026-09-24.

## What changed

1. **Default on.** `Hyphenation::SHIPPED` (`mag/src/typeset/hyphen.rs`) is
   what `from_settings` falls back to when a key is absent: English on,
   WeasyPrint-69 skip on, ladder limit on. `magazine.toml [render]` now says
   `hyphenate_english = true` explicitly. `Hyphenation::PARITY` is unchanged
   except for the new `limit_ladders: false`.
2. **Consecutive hyphens.** The old renderer set no limit. WeasyPrint 69 has
   no `hyphenate-limit-lines` (weasyprint-a5.css comment at the prose rule).
   The adapter only *reported* a prose block that ends more than 2
   consecutive lines on a hyphen (`_HYPHEN_LADDER_LIMIT = 2`,
   `weasyprint_adapter.py:315`, `_report_hyphen_ladders`). Typst 0.15.1 has
   no knob for this either: `text.costs` covers hyphenation, runt, widow and
   orphan, with no term for consecutive lines. The Typst leg now does both
   things:
   - **Enforces** the limit of 2 in the runt binder's settle loop
     (`runt.rs` `laddered`). In each run of more than 2 hyphen-ended lines,
     the first soft-hyphenated line from the third on loses its break. A
     Spanish word has its U+00AD removed. An English word is wrapped in
     `#text(hyphenate: false)[...]`, bounded to its alphanumeric run. The
     edits only remove break chances, so the loop converges. `PASSES` goes
     from 3 to 6, and failing to settle still bails loudly. `bind` now
     dedups edits, because a WeasyPrint-69 skip and a ladder fix can pick
     the same U+00AD.
   - **Warns.** `runt::ladder_warnings` is a port of the adapter's audit. It
     uses the same threshold, the same endings (soft hyphen, `-`, U+2010)
     and the same message shape. It runs on the final document, and its
     lines go into the result `warnings`, which `close_typst` prints to
     stderr. It fires only for a ladder the binder could not fix, such as
     one made only of hard hyphens.
3. **Parity forces the parity configuration.** `RenderArgs` gains
   `#[arg(skip)] parity`, which `mag parity`'s `render_leg` sets. With it,
   `typeset::run_request` uses `Hyphenation::PARITY` and ignores
   magazine.toml. The parity log shows `hyphenation Hyphenation { english:
   false, weasyprint69_skip: true, limit_ladders: false }`.
4. **WeasyPrint rollback: CSS left alone.** The parity oracle leg renders
   through the same `weasyprint-a5.css`. Reverting WP-1.5's `:lang(en)`
   rule would hyphenate English in the oracle. The oracle's text and glyph
   positions would then move away from the parity-config Typst leg, and
   the gate would break. So the rule stays. **The WeasyPrint rollback
   (`--engine weasyprint`) prints English unhyphenated**, and so no longer
   matches the shipped Typst output in English line breaks.

Test added: `a_ladder_is_more_than_two_consecutive_hyphen_ended_lines`
(runt.rs). The hyphen.rs default test is renamed to
`english_hyphenation_ships_by_default_and_a_bad_value_is_refused` and pins
SHIPPED as the default and PARITY as english-off with no ladder limit.

## Commands and results

Worktree `<scratch>/wp43b`, release build in `<scratch>/wp43b-target`.
"before" is the same tree built with `SHIPPED.limit_ladders = false`
(copied to `<scratch>/wp43b-nolimit`, then reverted and rebuilt).

```sh
R="--no-model --run editions/010/run-2026-09-13T01-34-51"
wp43b-nolimit render 010 $R     # exit 0, render-2026-09-24T20-16-57 (before)
mag render 010 $R               # exit 0, render-2026-09-24T20-17-37 (shipped)
mag parity 010                  # exit 0
python3 wp43-breaks.py <before>/en/reader.pdf <after>/en/reader.pdf
python3 wp43b-runs.py  <before>/en/reader.pdf <after>/en/reader.pdf
(cd mag && cargo fmt && cargo clippy --all-targets -- -D warnings)   # 0, 0
(cd mag && cargo test --no-fail-fast)                                # 0: 33 binaries, 968 passed, 0 failed
(cd mag && env -u MAG_ORACLE PATH=nopy-bin cargo test --no-fail-fast) # 0: 33 binaries, 968 passed, 0 failed
                                    # nopy-bin: 1789 links, command -v python3 python uv uvx empty (exit 1)
```

### 010 en, from each render's result.json `layouts[0]` and the PDFs

| measure | before (no limit) | shipped |
|---|---|---|
| total pages | 56 | 56 |
| per article | alignment 6, countering 3, dario 13, deepseek 4, rails 3, storage 4, scenarios 4, third-era 4, self-driving 5 | identical |
| opener fits | 9 of 9 | 9 of 9 |
| critic | pass | pass |
| cap warnings | dario verbatim 13 pages, cap 10 (predates this WP, WP-4.3) | the same single warning |
| `hyphen ladder` warnings (Typst audit) | 9 (6 of 3 lines, 3 of 4) | 0 |
| runs of hyphen-ended lines (mutool text, independent) | 1: 138, 2: 35, 3: 6, 4: 3 | 1: 144, 2: 44, 3+: 0 |
| lines / line-end hyphens (wp43-breaks.py) | 1116 / 227 | 1118 / 221 |
| breaks moved | | 40 gone, 42 new, on 9 pages |

The before render is the positive control for the audit: the same code path
printed 9 ladders there. The mutool count agrees with it (9 runs of 3 or
more). WP-4.3 counted 8, because its count left out hard hyphens. The
adapter's audit counts them, and so does this one.

### Parity gate, `mag parity 010` (staged, newest run), exit 0

Tier S page_count 56 vs 56. Critic, boxes, text, color and navigation all
pass. Tier E glyph positions pass: 59073 glyphs, 0 violations. Tier E
display list: 59304 vs 59304, 0 pages differ. Tier G max dy 0.006 pt.
Ratchet pass at target E: 56 measured, 0 regressions. The typst leg ran
with `english: false`, as its log line shows. The repo's magazine.toml
said `true` at that moment.

## What is and is not proven

PROVEN: English hyphenation is the shipped default, and 010 keeps 56 pages,
identical per-article counts, 9 of 9 openers fitting, critic pass and the
one pre-existing cap warning. The typst leg leaves no ladder of 3 or more
consecutive hyphen-ended lines on 010: before 9, after 0, measured two
independent ways. `mag parity 010` still exits 0 at Tier E, because parity
forces PARITY on the typst leg whatever magazine.toml says.

NOT PROVEN: that the enforcement always settles. It converges on 010 within
6 passes, and a failure to settle bails loudly rather than shipping. The
Spanish ladder fix (U+00AD removal) runs only in the shipped configuration.
No edition ships es on the Typst leg, so it is exercised by the code path
alone, not by a real es render. Whether hyphenated English reads better is
Fran's call, made on WP-4.3's PDFs. The WeasyPrint rollback now sets
English differently from the Typst output (unhyphenated), by choice, to keep
the oracle in the parity configuration.
