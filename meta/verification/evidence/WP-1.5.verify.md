# WP-1.5 verification

## Verdict

**ACCEPTED.**

Full replay, not an audit: WP-1.5 changes tracked source, so every claim was
re-measured from fresh renders in a clean worktree.

## Subject

| item | value |
|---|---|
| WP commit | `5504e5a` |
| Owns | `src/magazine/assets/weasyprint-a5.css`, `meta/verification/parity.yaml`, own evidence |
| verifier worktree | detached at `5504e5a`, removed at end |

## Owns check

`5504e5a` touches exactly three paths, all within Owns: the stylesheet,
`parity.yaml`, and `meta/verification/evidence/WP-1.5.md`. No `*.verify.md`,
no `baseline.json`, no comparator code, no Rust.

The stylesheet diff is **33 insertions, 0 deletions**. The original prose
rule is therefore untouched byte for byte, and the revert path the WP claims
(WP-4.3 deletes one contiguous block) is exactly what the diff supports.

## The selector-list correspondence

This is the load-bearing claim: a selector present in the prose rule but
missing from the `:lang(en)` block would leave that element hyphenating in
English, and a selector present only in the new block would switch off
hyphenation the design never granted.

Both lists were extracted mechanically (comments stripped, rule bodies
matched on their declaration) and diffed:

| check | result |
|---|---|
| prose rule selectors | 9 |
| `html:lang(en)` rule selectors | 9 |
| every en selector carries the `html:lang(en) ` prefix | yes |
| en selectors, prefix removed, vs prose list, positionally | 9 of 9 MATCH |
| set difference prose minus en | empty |
| set difference en minus prose | empty |

**One for one, no omissions, no extras.**

Specificity is sound in the same direction: prefixing `html:lang(en)` adds an
element plus a pseudo-class to every compound, so the new rule strictly
outranks the prose rule on precisely the same elements, and it appears later
in the file as well. It sets `hyphens: manual`, so it can only switch
hyphenation off, never on.

`hyphenate-limit-chars` is deliberately not repeated in the new block and does
not need to be: it has no effect under `hyphens: manual`.

The scoping mechanism exists as claimed: `html_edition.py:94` emits
`<html lang="{edition.locale}" ...>`, the only `lang=` site in the file.

## Replay

Four renders from one worktree at `5504e5a`, isolating the stylesheet as the
only variable. The "before" leg restores the parent's stylesheet with
`git show 7026d45:src/magazine/assets/weasyprint-a5.css`; the "after" leg and
both determinism renders use the committed one.

| leg | out dir |
|---|---|
| after (hyphens off), en+es | `render-2026-09-14T17-27-15` |
| before (hyphens on), en+es | `render-2026-09-14T17-29-15` |
| determinism 1 (post-switch, en) | `render-2026-09-14T17-31-08` |
| determinism 2 (post-switch, en) | `render-2026-09-14T17-32-09` |

### The switch, English

| quantity | claimed | measured | |
|---|---|---|---|
| reader pages before / after | 56 / 56 | 56 / 56 | OK |
| `layout.article_pages` before vs after | identical | **identical** | OK |
| cap violations introduced | 0 | **0** | OK |
| pre-existing violation | dario-amodei 13 vs cap 10, both legs | present both legs | OK |
| hyphen-ended lines | 142 to 16, delta 126 | 142 to 16, **delta exactly 126** | OK |
| max consecutive hyphen-ended lines, after | 2 | **2** | OK |
| max consecutive hyphen-ended lines, before | 3 | **4** | see Findings |

Page counts are read with `pdfinfo`, never from engine JSON, as the ladder
requires. The 126 delta matches WP-1.3's independently measured soft-hyphen
count exactly, which is a genuine cross-instrument agreement rather than a
restatement: WP-1.3 counted soft hyphens from the adapter, this counts
hyphen-terminated lines from `pdftotext`.

### Spanish, the point of the scope

Reproduced with my own scratch translation, built by the evidence's own
staging script from the run's finals, rendered `--langs en,es` on both sides
of the switch:

| quantity | claimed | measured | |
|---|---|---|---|
| es `pdftotext -raw` before vs after | byte-identical | **byte-identical** (`cmp`) | OK |
| es pages before / after | 56 / 56 | 56 / 56 | OK |
| es hyphen-ended lines before / after | 162 / 162 | 162 / 162 | OK |
| es max consecutive hyphen-ended | 4 both | 4 both | OK |

Spanish still hyphenates and still ladders after the switch, and English does
not. The `:lang(en)` scope does exactly what it claims. English
`pdftotext` output does differ across the switch, confirming the switch is
not inert.

### Determinism, WP-0.1's check on the post-switch state

| check | result |
|---|---|
| `pdftotext -raw`, all four PDFs (reader, booklet-a4, booklet-a4-cover, booklet-a4-interior) | IDENTICAL |
| `pdfinfo -box`, all four PDFs | IDENTICAL |
| `request.json` | BYTE-EQUAL |
| `edition-manifest.json` | BYTE-EQUAL |
| differing JSON leaves, whole tree | **exactly 6** |

The six are `preflight.json`'s four scratch-stage paths
(`.cover_art.path`, `.figures[0..2].path`) and `render-critic.json`'s two
PDF-byte hashes (`.visual_review.{booklet,reader}_sha256`) - precisely
WP-0.1's whitelist, nothing more. I confirmed the four path leaves satisfy
the conditional strip rule rather than being waved through: both values on
each leaf contain `/mag-engine-render-stage-`, which is what
`normalization.strip_pdf_keys` requires.

## Findings

1. **Minor, evidence only.** The Metrics table's "before" figure for max
   consecutive hyphen-ended lines reads 3; I measure **4** on the same
   quantity from a fresh pre-switch render (es measures 4 both legs, so 4 is
   not an artifact of my counter). This looks like a conflation with
   WP-1.3's separate finding of *three ladders* at reader pages 19, 24 and
   38. It affects one cell of one table. The value that is actually recorded
   in `parity.yaml` and that carries the claim,
   `max_consecutive_hyphen_ended_lines: 2 after`, is exact.
2. **Obligation recorded, not discharged.** `parity.yaml` now carries
   `typst_leg: WP-2.2a disables hyphenation for the same language`. That is
   a promise against a WP that has not been cut. It is correctly a decision
   record rather than a measurement, but WP-2.2a's brief must carry it or
   the two engines will be compared under different hyphenation settings.
3. **Render fixtures are now stale**, as the WP itself reports. The trees
   `render-2026-09-14T01-47-59` and `...T01-49-02`, used as oracle
   references by earlier comparator WPs, carry hyphenated English and
   predate `5504e5a`. Any WP replaying a stored verdict digest against a
   fresh render must re-render both legs. `mag parity` is unaffected since
   it renders both legs itself.

## Commands

Selector diff: comments stripped with a regex, both rule bodies located by
their declaration (`hyphens: auto` for the prose rule, `hyphens: manual`
plus an `html:lang(en)` selector for the new one), selectors split on commas
and compared positionally and as sets.

Renders, all from a worktree at `5504e5a` with
`editions/010/run-2026-09-13T01-34-51` copied in and the evidence's own
scratch-es staging script:

```sh
./mag/target/debug/mag render 010 --no-model --run editions/010/run-2026-09-13T01-34-51 --langs en,es
git show 7026d45:src/magazine/assets/weasyprint-a5.css > src/magazine/assets/weasyprint-a5.css
./mag/target/debug/mag render 010 --no-model --run editions/010/run-2026-09-13T01-34-51 --langs en,es
git show 5504e5a:src/magazine/assets/weasyprint-a5.css > src/magazine/assets/weasyprint-a5.css
./mag/target/debug/mag render 010 --no-model --langs en --run editions/010/run-2026-09-13T01-34-51
./mag/target/debug/mag render 010 --no-model --langs en --run editions/010/run-2026-09-13T01-34-51
```

Measurements: `pdfinfo` for page counts, `pdftotext -raw` then `grep -c -- '-$'`
for hyphen-ended lines, a five-line Python max-run counter for ladders,
`cmp` for the Spanish byte comparison, `article_pages` and
`article_page_caps` compared from `edition-manifest.json`, and a recursive
JSON leaf diff over the whole render tree for the determinism check.

## Tool versions

poppler 25.08.0 (`pdfinfo`, `pdftotext`), python 3.12.11, weasyprint 69.0,
rustc 1.96.0. Unchanged from WP-0.1's record; this WP adds no tool.

## Status

`accepted`
