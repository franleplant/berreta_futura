# WP-0.2m colour-space operators in the display-list reader

## Base and ownership

- Base `art_directed` `d5e3629`, detached worktree. Rebased onto `c58864d`
  (WP-0.2l, which changed `parity.rs` and the staged-input digest) before
  landing; there `cargo test` gave 25 binaries, 312 passed, 0 failed, and
  `mag parity 010` on the typst leg re-ran with the same exit (1) and the
  same per-tier figures as below, staged inputs now `d92eca1d...` (57 edition
  inputs, 43 renderer files). The floor table was measured at `d5e3629` and
  not re-run after the rebase. Owns
  `mag/src/parity/streams.rs` and its tests; the tests' two ICC fixtures are
  new files under `mag/tests/parity_icc/`. `mag/src/parity.rs`, `display.rs`
  and `parity.yaml` were read and not written. No crate added.

## What changed

1. **`cs`/`CS`/`sc`/`SC`/`scn`/`SCN`.** The graphics state now carries a
   fill space and a stroke space (initially DeviceGray, per the PDF spec).
   `cs`/`CS` select a space and reset its colour to the space's initial
   black; `sc`/`scn` read the operands in the current space. Every colour
   operator, `rg`/`g`/`k` included, now goes through one `paint(space, args)`
   that refuses a wrong component count (before, `rg` with two operands
   panicked on an index).
2. **Spaces accepted, and nothing else.** `/DeviceGray`, `/DeviceRGB` and
   `/DeviceCMYK` by name, with the same normalisation as `g`, `rg` and `k`.
   A resource space must be `[/ICCBased stream]`, and the profile is accepted
   only if its decoded bytes hash to one of two profiles:
   - sRGB v4, sha256 `c56e1685...8353`: family `rgb`, values unchanged.
   - sGrey v4, sha256 `00c0f94e...2a9d`: family `rgb`, value `v` recorded as
     `(v, v, v)`.
   Any other profile fails loud (`ICCBased profile sha256 <digest> is not the
   sRGB or sGrey v4 profile, so its values are not comparable as sRGB`), as
   do Lab, Pattern, Indexed, Separation and a `/N` that disagrees with the
   profile. This is the line the brief drew between "not comparable" and
   "divergent": an ICC space whose values are not sRGB is never equated.
3. **Why these two profiles are sRGB, computed rather than assumed.** Both
   are krilla 0.8.2's embedded profiles (`krilla-0.8.2/icc/`, CC0, from
   saucecontrol/Compact-ICC-Profiles); the 010 typst leg's `/c0` hashes to
   sRGB v4 byte for byte. Their tags, read from the files: sRGB v4 has the
   sRGB primaries (rXYZ 0.43604 0.22244 0.0139 and so on, D50-adapted) and the
   sRGB parametric curve (type 3, gamma 2.40004, a 0.947861, b 0.052139, c
   0.077393, d 0.040451) on all three channels. sGrey v4 has the same curve on
   kTRC and the same D50 white. The luminance row of the sRGB matrix sums to
   0.22244 + 0.71693 + 0.06062 = 1.0, so sRGB `(v, v, v)` and sGrey `v` both
   land on white-point chromaticity at `Y = TRC(v)`: the same colour. That is
   why sGrey is recorded in family `rgb` and not `gray`: WeasyPrint writes the
   same white as `1 1 1 rg`, and the typst leg writes it as `/c1 cs 1 scn`
   (typst-pdf converts an achromatic colour to its luma space).
4. **Font resolution by PostScript name.** Needed for the verify clause: once
   `cs` passed, the reader stopped at `operator Tf: loading font f0: font
   Inter-Medium has no vendored face in font_name_map`. `font_name_map` is
   keyed by the WeasyPrint alias (`Magazine-Sans-Medium`); its own `method`
   note says `face` "is ... the name the typst leg embeds from the same
   file". `face_entry` now finds an entry by alias, or failing that by its
   `face` value; both legs then resolve to the same face name and the same
   vendored file. A name that is neither still fails loud.

## Commands

From the worktree root. `RUN=editions/010/run-2026-09-13T01-34-51`.
`mag-base` is the binary built from `d5e3629` with this diff stashed,
`mag-new` the binary with it (before change 4; the final binary re-ran the
three floor rows marked `final`).

```sh
(cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test)
./mag/target/debug/mag render 010 --engine typst --no-model --langs en --run "$RUN"
# operator census over every page and form XObject of the typst leg (pypdf ContentStream)
# floor: editions/010/render-2026-09-14T01-49-02 copied from the main tree, fixtures rebuilt from it
MAG_PARITY_RENDER_A=editions/010/render-2026-09-14T01-49-02 uv run python mag/tests/parity_glyph_fixtures/mkfixtures.py
MAG_PARITY_OUT_DIR=output/parity-wp02m/<bin>-<row> $B/<bin> parity 010 --pre-rendered <a> <b>
# typst leg
MAG_PARITY_OUT_DIR=$PWD/output/parity-wp02m/typst ./mag/target/debug/mag parity 010 --run "$RUN"
```

The complete floor script is `/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp02m-floor.sh`
(scratch).

## Metrics

### The operators Typst's 010 PDF uses

Typst leg sha256 `02417ef38b39...`, the same bytes WP-2.2c recorded, three
renders here. Census over all 56 pages: `q Q cm` 1629 each, `cs scn` 1629
each, `BT ET Tr Tf Tm` 1477 each, `TJ` 1473, `Tj` 4, `m` 152, `l` 384, `c` 96,
`h` 128, `f` 143, `CS SCN w M B` 9 each. The colour operators split as
`/c0 cs` + 3-operand `scn` 1620, `/c1 cs` + 1-operand `scn` 9, `/c0 CS` +
3-operand `SCN` 9. `/c0` = `[/ICCBased 264]`, N 3; `/c1` = `[/ICCBased 265]`,
N 1. No `sc`, `SC`, `g`, `rg`, `k`, `d`, `gs`, `Do`, `BDC` or shading op
appears. `sc`/`SC` are implemented anyway because they are the same operator
over a non-pattern space and cost no extra line.

### Unit tests (9 new, all in `streams.rs`)

| test | what it pins |
| --- | --- |
| `an_srgb_icc_fill_equals_the_same_rg_fill` | `/c0 cs v scn` and `sc` equal `v rg`, family `rgb`, with the real sRGB v4 bytes and the page-3 values |
| `an_srgb_icc_stroke_equals_the_same_rg_stroke` | `CS`/`SCN`/`SC` equal `RG` |
| `an_sgrey_icc_value_equals_the_rgb_triple_it_denotes` | `/c1 cs 1 scn` equals `1 1 1 rg`; also at 0.25 |
| `device_spaces_selected_by_cs_equal_their_shorthand_operators` | DeviceRGB/Gray/CMYK via `cs` equal `rg`/`g`/`k` |
| `cs_resets_the_colour_to_the_space_s_initial_black` | `1 0 0 rg /c0 cs` paints black |
| `a_genuinely_different_colour_still_compares_unequal` | 0.001 off on one sRGB channel, sGrey 0.499 vs 0.5 grey, a stroke off by 0.1, and DeviceGray vs rgb (family): all unequal |
| `an_unrecognised_icc_profile_fails_loud_rather_than_equating` | sRGB v4 with one bit flipped is refused by digest |
| `unsupported_spaces_and_wrong_arity_fail_loud` | Lab, Pattern, one operand in a 3-component space, two-operand `rg` |
| `a_face_resolves_by_its_alias_or_by_its_postscript_name_and_nothing_else` | change 4, with a negative |

Discrimination: the base tracer bails on `cs` (the WP-2.2c error), so every `cs` test could
not pass against it; the tests were not run against the base, that is by
construction. The fail-loud tests assert on message text, so a silent
acceptance fails them; the unequal-colour test is the negative for every
equality test.

`cargo fmt --check` clean, `cargo clippy --all-targets -D warnings` clean,
`cargo test` **25 binaries, 310 passed, 0 failed** (265 at WP-2.2c's
landing; the 45 added are these 9 tests counted five times, because
`streams.rs` is compiled into the `mag` binary and into four integration
test crates by `#[path]`).

### The WeasyPrint floor is unchanged

WP-0.2i's two floor trees are not both on disk: `render-2026-09-14T01-47-59`
is gone from the main tree, and its recorded digests (`468eac3c...` A-vs-A,
`df9909ee...` stairdrift) were taken at `20adcfb`, and verdict digests move
with the commit (WP-0.2i's own finding). So the floor was measured as a
before/after on one base: the same inputs through `mag-base` and `mag-new`,
with leg A = `render-2026-09-14T01-49-02` and the fixture corpus rebuilt from
it by the committed generator (its self-check printed `stairdrift flat steps
52549/68800 = 76.3794%`, WP-0.2i's figure exactly).

| row | mag-base exit / digest | mag-new exit / digest | final exit / digest |
| --- | --- | --- | --- |
| A-vs-A | 0 / `72edc4f14eceb5da` | 0 / `72edc4f14eceb5da` | 0 / `72edc4f14eceb5da` |
| control | 0 / `9984ec00bb9dd48b` | 0 / `9984ec00bb9dd48b` | |
| stairdrift (the floor) | 0 / `5ef7026af486eb7d` | 0 / `5ef7026af486eb7d` | 0 / `5ef7026af486eb7d` |
| kern001 (must fail) | 1 / `905b88686a65de00` | 1 / `905b88686a65de00` | |
| glyphsub (must fail) | 1 / `2112d9a172e35002` | 1 / `2112d9a172e35002` | 1 / `2112d9a172e35002` |

stairdrift glyph clause on both binaries: pass, 68,800 glyphs, 1,488 shows,
worst ratio 0.2500, 0 violations, WP-0.2i's floor. Byte-identical verdicts
before and after, including two must-fail rows, so the change moved nothing
the WeasyPrint self-comparison records.

### `mag parity 010` on the typst leg

**Exit 1, verdict written** (`output/parity-wp02m/typst/verdict.json`, sha256
`0e647797ef67...`; staged inputs `e48eb5c6...`, as WP-2.2c). Every tier ran:

```
tier S page_count: pass (56 vs 56)
tier S boxes: pass (162 boxes, 54 rotations compared; 0 box, 0 rotation mismatches)
tier S text: fail (30 pages differ)
tier G: max dx 328.844 pt, max dy 367.872 pt, beyond G1 118, beyond G2 201, structure mismatches 141
tier S color: fail (1733 entries compared, 47 pages differ)
tier S navigation: fail (85 annotations of which 85 links, 0 outlines, 0 title, 0 lang compared; 22 mismatches)
tier E glyph positions: fail (3295 glyphs, 62 shows, worst excess 88.974701 pt, worst ratio 8285.8750, 40 violations)
tier E display list: fail (54 pages differ)
tier V: dims pass (mismatches 0), V1 fail, V2 fail, worst page fraction 0.624220, max channel delta 255
tier E raster: not_evaluated (WP-0.2d raster_bound derivation)
```

First failures per clause: text pages 4-9, 11-17, 31-33, 36, 40-44, 46-53;
navigation starts `page 3: annotations 27 vs 0` (the contents page carries
no links on the typst leg), then 2 vs 0 on each opener; display list
`page 2: page boxes differ` and the same on every page (see below).

**The colour clause, looked at directly.** Distinct (fill/stroke, colour)
pairs over the interior, both legs quantised as the reader does: typst 10,
WeasyPrint 11, 6 in common. The white, the paper inks and SIGNAL-ORANGE
match exactly after normalisation. The four that differ are the template's
percentage colours:

| colour | WeasyPrint `rg` | typst `scn` |
| --- | --- | --- |
| INK `rgb(5.5%, 7.5%, 8.5%)` | 0.055 0.075 0.085 | 0.054902 0.074510 0.086275 (14/255, 19/255, 22/255) |
| VIOLET `rgb(25%, 10%, 43%)` | 0.25 0.10 0.43 | 0.250980 0.101961 0.431373 |
| SLATE `rgb(31%, 35%, 37%)` | 0.31 0.35 0.37 | 0.309804 0.349020 0.368627 |
| COOL-GRAY `rgb(88%, 89%, 90%)` | 0.88 0.89 0.90 | 0.878431 0.890196 0.901961 |

WeasyPrint only: PALE-VIOLET `0.955 0.945 0.975`, which the typst leg never
paints. The cause of the four is in the engine, not the reader:
`typst-pdf-0.15.1/src/paint.rs:146` converts every solid colour with
`to_vec4_u8()` before writing it, so typst cannot emit 5.5%. Each difference
is under half an 8-bit step (largest 0.001569 = 0.40/255). The reader records
them as different, which is correct under the clause as written (1e-6
quantum, "numerically equal"); whether a sub-1/255 difference is a divergence
is a clause decision, not this WP's, and nothing here loosens it.

## Defects and findings for the orchestrator

1. **Display list fails every page on a box it should not compare.**
   `display.rs:224-238` records `TrimBox` only when the page states one.
   WeasyPrint writes `/TrimBox` and `/BleedBox` equal to the MediaBox; typst
   writes neither, so the effective box is identical and Tier S `boxes`
   passes, but `compare_page` returns `page boxes differ` at `display.rs:367`
   before looking at a single element, on all 54 pages. This masks every
   real display-list difference. Comparator territory (`display.rs`, not
   owned here): absent TrimBox should default to CropBox, which defaults to
   MediaBox.
2. **Colour quantisation in typst-pdf** (table above): four template colours
   can never be numerically equal at 1e-6. Needs a clause decision (compare
   at 1/255, or accept as engine-inherent) before Phase 3 can pass colour.
3. PALE-VIOLET missing on the typst leg, and the contents page has no link
   annotations: port gaps for Phase 3, recorded only.
4. The two WP-0.2i floor trees should be restaged or re-derived:
   `render-2026-09-14T01-47-59` no longer exists in the main tree.

## What is and is not proven

**Proven.**
- The reader accepts every colour operator and space the 010 typst leg uses,
  and `mag parity 010` now scores every tier on it (exit 1 on real clause
  failures, verdict written), where it exited 1 in the tracer before.
- The same colour compares equal across the two spellings: sRGB ICC vs `rg`,
  sGrey ICC vs an equal-component `rg`, device spaces by `cs` vs their
  shorthand, tested with the real profile bytes; and a different colour
  compares unequal, including one differing by 0.001 on one channel.
- A profile that is not one of the two sRGB-family profiles is refused, not
  equated (one-bit-flip test).
- The WeasyPrint self-comparison, the stairdrift floor and two must-fail
  fixtures give byte-identical verdicts before and after.

**Not proven.**
- The WP-0.2i digests themselves were not reproduced: their leg-A tree is
  gone and they belong to `20adcfb`. The before/after comparison on one base
  is what stands in for them.
- Colorimetric identity is argued from the profile tags, not from a colour
  engine run. It is sRGB v4 vs DeviceRGB-as-sRGB; a viewer that renders
  DeviceRGB unmanaged would still show the same pixels for the same numbers.
- Profiles other than krilla's v4 pair (its v2 "magic" profiles, used for
  other PDF standards) fail loud rather than being recognised. Typst emits
  them under PDF/A-2 and similar standards, which 010 does not use.
- `DeviceGray` stays in family `gray` as the plan specifies, so a future
  oracle `g` against a typst sGrey would read as a family difference. 010's
  oracle emits no `g` (census of `render-2026-09-14T01-49-02`: `rg` 564, `RG` 3, no other colour operator), so this is
  latent.
