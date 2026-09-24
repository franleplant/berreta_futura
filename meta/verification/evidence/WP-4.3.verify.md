# WP-4.3 verify

Verdict: **ACCEPTED** (the option choice stays awaiting-fran).

Tip `41ea889`, worktree `<scratch>/v6`, release build, `editions/010/run-2026-09-13T01-34-51`.

## Replay

| Command | Exit | Result |
|---|---|---|
| `mag render 010` (committed config, neither key present) | 0 | log prints `Hyphenation { english: false, weasyprint69_skip: true }` = PARITY |
| `mag parity 010 --run editions/010/run-2026-09-13T01-34-51` | 0 | `ratchet: pass (target E, 56 committed entries checked, 56 recorded, 56 measured, 0 regressions)`; page_count 56 vs 56; critic pass; E glyph positions 59073 glyphs, 0 violations; E display list 59304 vs 59304; V worst 0.000336. Same numbers as WP-4.3.md |
| magazine.toml + `hyphenate_english = true` under `[render]`, `mag render 010 --no-model` | 0 | log `Hyphenation { english: true, ... }`, 56 pages, critic pass. Config restored, `git status` clean |

## Own count of breaks (`mutool draw -F txt`, my own script)

| | parity render | english on |
|---|---|---|
| non-empty text lines (incl. furniture) | 1365 | 1354 (-11, as WP-4.3.md) |
| lines ending in U+2010 | 0 | 227 (as WP-4.3.md) |
| lines ending in any hyphen after a letter | 14 (all compound hyphens: `Claude-`, `change-`, `well-`) | 237 |

The first differing paragraph is on the Rails article ("promising full dis‐ /
closure"). Every 25th new break, read by eye: `dis‐closure`, `recon‐naissance`,
`elic‐its`, `democ‐ratic`, `train‐ing`, `comput‐ers`, `gov‐ernments`,
`crite‐ria`, `con‐text`, `Rock‐set`: all legal English breaks. The switch
really changes 010's line breaking.

## Injected defect

`Hyphenation::native` made to ignore the language (`self.english &&
!language(locale).is_empty()`, i.e. Spanish would get native hyphenation too).
`cargo test --bin mag`: 264 passed, 1 failed
(`the_parity_configuration_is_the_default_and_a_bad_value_is_refused`,
hyphen.rs:196). Restored.

## Not proven

Which option reads better (Fran). The weasyprint69 skip was not re-measured here
(WP-4.3.md covers it on 906 only).
