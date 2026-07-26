# Renderer migration — ReportLab to WeasyPrint

The A5 reader is moving from the bespoke ReportLab typesetter in
`src/magazine/render.py` to an HTML/CSS path
(`html_edition.py` → `weasyprint_adapter.py` + `assets/weasyprint-a5.css`).

**WeasyPrint is now the production renderer.** ReportLab is retained as the
rollback and is selected by one key; see [Switching renderers](#switching-renderers).
The new path was proven against it
before cutover by `tools/compare_pipelines.py`, which renders the candidate,
imposes the A4 booklet, and compares both against a frozen baseline build of
edition `002-unreleased` across six gates: geometry, imposition, per-page
content, ink geometry, per-page pixel difference, and colour.

Byte-identical PDFs are not achievable between two producers and are not a
goal. Pixel-identical rasterized pages **are** achievable — measured floor is
0.000000% differing pixels (0 of 1,000,440) for a full page of body copy
rendered through both pipelines and rasterized by the same `pdftoppm`.

## Switching renderers

Which renderer typesets the A5 reader is configuration, not code.

```toml
[render]
engine = "weasyprint"   # default when the key is absent; "reportlab" rolls back
```

An unrecognised value is a `ValidationError` at `Magazine(root)` construction —
before any work starts — naming the values it will accept. There is no silent
fallback. Note that `[render]`'s neighbouring `body_size` and `leading` are dead
keys that nothing reads (see [Dead configuration](#dead-configuration)); `engine`
is the only live one in that table besides `design`.

**Cut over:** `engine = "weasyprint"`, or delete the key.
**Roll back:** `engine = "reportlab"`. Nothing else changes.

For one build without touching configuration — a side-by-side before committing:

```sh
mag build 002-unreleased --engine reportlab
```

The flag overrides the configured engine for that build only and is never
written back.

### Why `design` is not part of the switch

`render_a5` accepts only `"monument"`, `render_a5_weasyprint` only
`"WeasyPrint / A5 fold proof"`, and each *raises* on the other's value. So the
dispatch in `render_engine.py` never forwards a design across the seam: a
renderer carries the design it renders as part of its identity, read from a
constant in its own module. `[render] design` is the ReportLab engine's design
direction and is consulted only when that engine is selected. Switching engines
is therefore one key, not two, in both directions.

The two engines also stay independent: each is imported lazily inside its own
factory, so a ReportLab build never imports `weasyprint_adapter`, and neither
module has gained a reference to the other.

### What changes in the built package

`layout.design_direction` in `edition-manifest.json` identifies the renderer,
because the two engines have disjoint design vocabularies: `A / Quiet Standard`
for ReportLab, `WeasyPrint / A5 fold proof` for WeasyPrint. A WeasyPrint build
additionally records `layout.shaping_scaffolds` — the three measures listed
below that hold its typography down to ReportLab's. That list is in the artifact
rather than only in this document, and deliberately not a console warning: a
build-time warning that fires on every single build and cannot be silenced is
noise, and would be ignored by the second week.

### The reader hashes change, so the render review goes stale

Two producers cannot emit identical bytes, so switching engines changes
`reader.pdf` and `booklet-a4.pdf`. Any recorded render review is hash-bound and
immediately reports `status: "stale"` (`mag review status <edition>`), and
`mag release` will refuse the edition until a reviewer records a new decision
with `mag review record`. This is correct — nobody has looked at the new PDFs —
but it is the first thing that bites on cutover. Verified on `002-unreleased`:
the status flips to `stale` with `machine_result: "pass"`, and the refusal is a
clean `error:` line, not a crash.

Verified on `002-unreleased` at cutover: a full `mag build` completes on
WeasyPrint in both languages, `render_critic` returns `pass`, `preflight`
returns `home_ready_studio_blocked` (its pre-existing state), the 8 figure
placements match, and two consecutive WeasyPrint builds are byte-identical to
each other. `engine = "reportlab"` reproduces the pre-cutover build byte for
byte across all 162 packaged files in both languages.

### Shelf life of the rollback

**The rollback is faithful only while the three shaping scaffolds below are in
place.** They are what make the two renderers interchangeable: with kerning,
ligatures and intra-token breaking suppressed, WeasyPrint reproduces ReportLab's
line breaking exactly, so falling back restores the publication rather than
altering it.

Re-enabling shaping — the first deferred item below, and the reason the
migration happened — ends that. WeasyPrint will then set type that ReportLab
cannot reproduce: 66% of English running words shift, worst case 1.87pt on a
single word, and line breaks move. From that point `engine = "reportlab"` is no
longer a rollback; it is a **visible change to the publication**, reverting it to
unkerned type.

Whoever removes those scaffolds is closing the rollback window. Do it
deliberately, re-baseline, and say so in this document — do not discover it
during an incident.

## The colour gate, and why its exact clause carries it

G6 was added last. It has two clauses: an **exact** per-page comparison of the
chromatic ink each pipeline sets in its content streams, with no tolerance at
all, and a **toleranced** per-channel RGB raster clause.

The exact clause is the one that does the work, and this is the measurement that
shows it. Injecting a channel swap of `VIOLET` and `SIGNAL_ORANGE` — a grossly
wrong hue on every accent, across 32 of the 36 reader pages — was **missed by
every raster gate**: G4's worst ink ratio moved by 0.000013 against a 0.002
tolerance, G5's differing-pixel fraction reached 0.43% against 1%, G5's mean
absolute difference 0.0495 against 2.0, and G6's *own* raster clause 0.2573
against 0.5. The chromatic-ink clause caught it immediately, with **88
failures**.

The accents on this magazine are hairlines, rules and small display type. Their
coverage is too low to move an average past any honest tolerance, so a raster
metric cannot be the thing that catches a hue error here. The raster clause is
kept as the corroborator that also sees hue *inside* an embedded image, where no
colour operator exists to compare.

## Deferred until after cutover

Ordered by what matters most.

### 1. Re-enable shaping and re-baseline

Three scaffolds hold Pango down to what ReportLab does. All are an
**equivalence scaffold, not a design decision**, and all come out together.
Removing them also closes the ReportLab rollback window — see
[Shelf life of the rollback](#shelf-life-of-the-rollback). They are declared in
code as `weasyprint_adapter.SHAPING_SCAFFOLDS` and recorded in every WeasyPrint
build's manifest, so all three lists must be retired together:

1. `font-kerning: none` in `assets/weasyprint-a5.css`.
2. `font-variant-ligatures: none`, beside it.
3. `.reader-token { white-space: nowrap }`, plus the
   `_suppress_intra_token_breaks` tree pass in `weasyprint_adapter.py` that puts
   one such box around every whitespace token. The CSS comment above the rule
   says the two come out together; this list is the other half of that promise.

ReportLab measures text by summing raw glyph advance widths and has never
kerned. Pango/HarfBuzz kerns and applies ligatures by default. The same 10pt
line measures **321.862pt** shaped versus **323.870pt** unshaped — enough for a
word to fit on one line in one pipeline and wrap in the other, which then shifts
every line below it. With shaping off the two agree to **0.008pt** across a full
325pt measure. Shaping accounted for 15.49% of the total pixel difference and
took English line-break agreement from 81.8% to 94.8% (Spanish to 100%).

The third scaffold is line breaking. `lines` (render.py) splits a paragraph with
`str.split`, so the reader can only end a line on whitespace; Pango also breaks
*inside* a token, after a hyphen or a dash — `compile- checked`, `Opus-
planner`, `trade- offs`. `word-break`, `line-break`, `hyphens` and
`overflow-wrap` are all measured no-ops against it, so the only lever is markup.
One nowrap box per token took English line-break agreement from 94.8% to 385/385
lines and 69/69 paragraphs, and left Spanish at the 423/423 it already had.

The cost is real: kerning affects **66% of English running words**, worst case
**1.87pt (~0.19 em)** on a single word — visible on a printed page. Disabling it
is defensible only because it reproduces what the last two printed editions
already look like. It is parity, not a regression.

Reversing all three is: delete two CSS declarations, delete the `.reader-token`
rule, delete `_suppress_intra_token_breaks` and its call in `_lay_out`, and
re-baseline. Dropping the nowrap box also lifts the constraint recorded under
**Long URLs** below — an over-measure token becomes breakable rather than a
`_validate_reader_measures` refusal. The publication then ends up better set
than it has ever been. **The goal is professional typography; these scaffolds
are temporary.**

### 2. Blank-page check accepts near-white ink

`render_critic._inspect_page` derives `blank` from `WHITE_THRESHOLD = 245`, so
the production critic's own "inside front and inside back covers must be
completely blank" error would pass a 246–254 grey tint or a hairline. This is in
shipping code and independent of the migration. `tools/compare_pipelines.py`
already requires a pure-white raster plus zero extracted characters; production
should match.

### 3. Deduplicate the reader-text fold

`reader_text.fold_reader_characters` was extracted so the HTML path could fold
smart quotes at the escape boundary rather than over assembled markup (folding
after escaping corrupts attribute values — an article titled `The "Dark"
Factory` terminated its own `alt` attribute). `render._plain` still carries its
own copy plus a markdown-link regex that has no business running over HTML. A
test currently pins the two implementations together on link-free input.
`render.py` was deliberately not edited during convergence because the frozen
baseline came from it.

### 4. `render_critic` API friction

`RASTER_DPI` is a module constant rather than a parameter, so the harness
rebinds it inside a context manager. `_booklet_spread_checks` takes left/right
page numbers from its argument rather than deriving them from the booklet PDF,
so its mapping cannot serve as evidence — the harness derives placement
positionally instead.

### 5. Latent, will bite on a future edition

- **Band anchor heading measured at the wrong size.** `render.py:871-874`
  measures at `(SERIF_DISPLAY, 17.5)` / `(SANS_SEMIBOLD, 8.7)` then draws at
  18.5 / 8.5. The CSS uses the drawn sizes. A heading whose 18.5pt width falls
  between 333.008pt and ~352pt wraps in CSS but not in ReportLab. Not exercised
  by edition 002.
- **Terminal balance is not reproduced.** The adapter hardcodes
  `frame_bottom = 45.0`, but `render.py` raises it for the last two pages of any
  article carrying an `ArticleBalancePlan`. Inert today — the frozen manifest has
  `article_terminal_balance: {}` — but the tail-ornament rule and the
  `.article-tail` datum are both silently wrong the first time a plan fires.
- **Long URLs.** The edition contains URLs up to 169 characters, which exceed the
  measure at 7.2pt. The per-token `white-space: nowrap` used for dash parity
  needs `overflow-wrap: anywhere` beside it to mimic `render.py`'s per-character
  fallback. Those break points are **unverified**.
- **Nested list markers.** U+25E6 WHITE BULLET exists in neither Source Serif 4
  nor Inter and silently falls back to Times New Roman. Edition 002 has no
  nested lists. Bullets are drawn as boxes rather than set as glyphs
  specifically to avoid this; do not reintroduce a marker character.

### 6. Off-grid type sizes cost 0.29%

Pango quantizes font size to 1/1024 CSS px, so 10pt becomes 9.999756pt
(−24.4 ppm). Only 5 of the design's 18 sizes are exactly representable; 12pt,
22pt and 24pt measure exactly zero pixel difference. This is the entire
irreducible residual and it is a consequence of the type scale, not a tool
limit. **Do not change type sizes to flatter a diff metric** — recorded here
only so the residual is understood.

## Dead configuration

`magazine.toml`'s `[render] body_size = 9.55` and `leading = 12.55` are read by
nothing. The authoritative pair is **10 / 13** in `render.py`. The stylesheet was
originally calibrated against the dead values, which is why its metrics were
wrong. Either wire the config up or delete it.
