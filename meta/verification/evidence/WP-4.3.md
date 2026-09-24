# WP-4.3 post-flip hyphenation change

## Base

8f30473 (art_directed). Scope as briefed: land a switch, keep the default at
the parity configuration, measure, hand the choice to Fran. The WeasyPrint
stylesheet's `:lang(en)` switch (WP-1.5) is not reverted: that belongs to the
option Fran picks, not to this WP's landing.

## What changed

Two `magazine.toml [render]` keys, read by the Typst leg only
(`mag/src/typeset/hyphen.rs` `Hyphenation::from_settings`). Absent keys give
`Hyphenation::PARITY`. Any value other than `true`/`false` is refused, and the
error names the key.

| key | default (parity) | when flipped |
|---|---|---|
| `hyphenate_english` | `false` | English prose runs are wrapped in `#text(hyphenate: true)[...]`. This is Typst's own hyphenation: hypher's English patterns, bounds 2/3, and the Knuth-Plass hyphen penalty. It applies only where the stylesheet hyphenates Spanish: body paragraphs, the standfirst remainder, list items, blockquotes, extract quote lines and captions, and key ideas. Headings, standfirsts, rosters, captions, furniture and code stay unhyphenated. The runt bind then treats a hyphenated English line as it treats a Spanish one. |
| `weasyprint69_hyphen_skip` | `true` | `runt.rs` stops removing the soft hyphens that WeasyPrint 69's `split_first_line` defect never tries (WP-3.10). Typst then keeps every Pyphen break in Spanish. |

The flags are threaded as a `Hyphenation` value through `content::compose`,
`template::paginate` and `runt::bound`. The render log prints the value in
effect, for example `typst source tree (en, hyphenation Hyphenation { english:
true, weasyprint69_skip: true })`. One line changes outside Owns:
`render.rs` `toml_value` becomes `pub(crate)` so typeset reads the same
parser. magazine.toml itself is not edited, since another agent owns the
engine key. Both keys are documented here only.

Soft hyphens were not used for English. A U+00AD break reaches Typst's line
breaker as `Breakpoint::Normal` and carries no hyphen penalty
(typst-layout 0.15.1 `linebreak.rs:660`, `line.rs:141`). "English on" would
then mean more hyphens than Typst itself sets.

Tests added: `the_parity_configuration_is_the_default_and_a_bad_value_is_refused`
(hyphen.rs); the 906 composition test also composes en with the switch on and
checks that body prose is wrapped, a heading is not, and that no U+00AD or
wrapper appears by default.

## Commands and results

Worktree at `<scratch>/wp43`, `editions/010/run-2026-09-13T01-34-51`
copied in, release build. Each "flipped" run inserted the keys under
`[render]` in the worktree's magazine.toml and restored the original after.

```sh
M=mag/target/release/mag; R=--run editions/010/run-2026-09-13T01-34-51
$M render 010 --engine typst --no-model $R    # parity: exit 0, render-2026-09-24T14-47-18
# + hyphenate_english = true
$M render 010 --engine typst --no-model $R    # native en: exit 0, render-2026-09-24T14-48-06
# fixture 906 copied into editions/906 + library/sources, moved out after
$M render 906 --engine typst --no-model       # parity: exit 0, render-2026-09-24T14-50-43
# + hyphenate_english = true, weasyprint69_hyphen_skip = false
$M render 906 --engine typst --no-model       # flipped: exit 0, render-2026-09-24T14-50-57
python3 breaks.py <parity>/reader.pdf <flipped>/reader.pdf   # below
# magazine.toml restored, fixture moved out
$M parity 010 $R                              # default config: exit 0
(cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test)   # all exit 0
```

`breaks.py` (scratch) reads `mutool draw -F txt` lines. It drops folio
(all-digit) and running-head (all-caps) lines and strips a line-final U+2010
or U+00AD, counting those as hyphens. It records each break as the offset
into the non-whitespace text stream, and asserts that both streams are equal
(59298 characters for 010) before comparing break sets. mutool is used because
pdftotext silently re-joins line-end hyphens.

### 010 en: native hyphenation vs parity

Page and fit figures are read from each render's `result.json` `layouts[0]`.

| measure | parity | native en |
|---|---|---|
| total pages | 56 | 56 |
| per article | alignment 6, countering 3, dario 13, deepseek 4, rails 3, storage 4, scenarios 4, third-era 4, self-driving 5 | identical |
| opener fits | 9 of 9 true | 9 of 9 true |
| editorial pages | 0 | 0 |
| critic | pass | pass |
| text lines | 1127 | 1116 (-11) |
| line-end hyphens | 0 | 227 (20% of lines) |
| breaks | 1127 | 566 parity breaks gone, 555 new, on 36 pages |
| hyphen ladders | none | 140 single, 30 of 2, 5 of 3, 3 of 4 consecutive lines |

Caps: the flip adds no cap violation. One violation exists in both renders
and predates this WP. `dario-amodei-we-must-pace-the-frontier` is `verbatim`
at 13 pages against the ten-page cap. It is the known warned-past-cap article
of 010, and the flip neither causes it nor fixes it. Every `article` piece is
at most 6 pages against 7, and `the-third-era` (verbatim) is at 4.

Once one line in a paragraph re-breaks, the paragraph reflows to its end. So
"566 gone" counts every moved line end, not only the lines that carry a new
hyphen. `weasyprint69_hyphen_skip` has no effect on English: native breaks
carry no U+00AD for the rule to remove.

### 906 (fixture): es and en

| measure | es parity | es, WeasyPrint-69 skip off | en parity | en native |
|---|---|---|---|---|
| total pages | 16 | 16 | 16 | 16 |
| per article | figure 3, hyphenation 3 | identical | figure 3, hyphenation 2 | identical |
| lines | 69 | 69 | 65 | 64 |
| line-end hyphens | 11 | 12 | 0 | 11 |
| breaks moved | | 1 gone, 1 new, 1 page | | 15 gone, 14 new, 3 pages |

The single es break is the known WP-3.10 case. It now reads
"dividirse legíti‐" where the oracle has "dividirse / legítimamente".

## Options for Fran

1. **Keep parity** (the default, nothing to do). English stays unhyphenated,
   as it has been since WP-1.5 in both engines. Spanish keeps Pyphen with
   WeasyPrint 69's skip. The Typst leg stays byte-comparable to WeasyPrint.
2. **English hyphenation on** (`hyphenate_english = true`). On 010: 56 pages
   either way, per-article counts identical, all openers fit, no new cap
   violation. 227 hyphens across 1116 lines, 11 fewer lines, line ends moved
   on 36 of 56 pages. Typst has no limit on consecutive hyphenated lines, and
   010 gets three 4-line ladders. Parity against WeasyPrint then fails by
   design, unless the stylesheet's `:lang(en)` switch is reverted to match.
   Even then Pyphen's en_US patterns are not hypher's, so the two engines
   would still break differently.
3. **Also drop the WeasyPrint-69 skip** (`weasyprint69_hyphen_skip = false`,
   Spanish only). On 906 es it changes 1 break of 69 and adds 1 hyphen. Pages
   are unchanged. The skip only reproduces a WeasyPrint defect. Dropping it
   breaks es parity with the bridge in exactly those lines.

Options 2 and 3 are independent and can be combined.

## What is and is not proven

PROVEN: the default renders the parity configuration. `mag parity 010 --run
...` exits 0 at Tier E with the switch compiled in (56 vs 56 pages, glyph
positions 59073 with 0 violations, display list 59304 vs 59304, ratchet 56
measured with 0 regressions). The flipped renders exit 0, and their page,
per-article, opener-fit and break figures are the ones above, all taken from
those runs.

NOT PROVEN: whether option 2 reads better. That takes Fran reading the
native-en PDF, kept at
`/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp43-010-native-en.pdf` (parity
twin `wp43-010-parity-en.pdf`, script `wp43-breaks.py`, same dir), or
re-rendered with the commands above. The es measurement covers
the fixture only: no real edition ships an es translation on the Typst leg,
so a Spanish page-count change from option 3 on a long edition is not
excluded. The WeasyPrint leg was not rendered with English hyphenation, so
option 2's cross-engine gap is not quantified.

Status: done (Fran chose option 2, 2026-09-24; shipped by WP-4.3b)
