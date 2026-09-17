# WP-0.2h verification

Verdict: **ACCEPTED**.

Worker commit `0bf3977`, pre-land HEAD `10d705d`. Verified in a fresh
worktree at `0bf3977`.

## Owns

`git diff --name-only 10d705d 0bf3977` lists exactly four paths:
`mag/src/parity/streams.rs`, `mag/src/parity/display.rs`,
`mag/tests/parity_text_seam.rs`, `meta/verification/evidence/WP-0.2h.md`.
No verify file, no `baseline.json`, no `parity.yaml`, no Cargo files. Rule
1a's only-gained check is correctly not applicable: no crate was added.

## The clause: digests unchanged

The clause this WP had to meet, since the covers sit outside the compared
domain and a decode addition must not perturb the interior. All three
reproduce exactly, from the two matched pre-`5504e5a` render trees:

| run | digest | matches WP-0.2i |
|---|---|---|
| A-vs-A run 1 | `0e21644ee602ff8a78fc6ac20289c8032c5ba5c4905f8327668a436784b189e0` | yes |
| A-vs-A run 2 | same, byte-identical | yes |
| A-vs-B | `6e932ea43678b91add20a13847e633555e2a3a8b19ef159e86fc0cc2b6015836` | yes |

Each exits 0. Adding `tr` to every Text element does not move the digest
because `verdict.json` records clause outcomes rather than the display list,
and every interior show is mode 0 on both legs.

Baseline in the worktree: `cargo fmt --check` clean, `cargo clippy
--all-targets -- -D warnings` clean, **113 tests pass across 12 binaries**,
0 failed. WP-0.2d's fault suite passes and its expected-detections matrix is
untouched (`parity.yaml` is not in the diff at all).

## The third fail-loud reason, and the identity check

Confirmed. The identity-versus-remapping distinction is implemented
correctly, and correctly for more than DeviceGray:

    let channels = match cs { "DeviceRGB" => 3, "DeviceGray" => 1, other => bail!(...) };
    let identity: Vec<f64> = (0..channels).flat_map(|_| [0.0, 1.0]).collect();
    ensure!(values? == identity, "...not the identity for {cs}, which would remap samples");

The identity is built **per channel from the colour space**, so DeviceGray
compares against `[0,1]` and DeviceRGB against `[0,1,0,1,0,1]`, by full
equality including length. The failure mode the brief asked about is
therefore absent: a DeviceRGB image carrying an inverting `[1,0,1,0,1,0]`,
or a truncated `[0,1]`, differs from the six-element identity and bails.

Two orderings make this sound rather than lucky. `bpc == 8` is asserted
before the check, so the bit-depth-dependent default (`[0, 2^n - 1]`) cannot
arise; and any colour space whose spec default is not `[0,1]` per channel
(Indexed, Lab, ICCBased with other ranges) bails at the colour-space match
first, before reaching the Decode comparison.

Recorded under rule 10: **the DeviceRGB path of this check is correct by
construction but is not exercised by any fixture.** Edition 010's only
Decode array is the cover SMask's DeviceGray `[0,1]`. The claim above rests
on reading, not on a test.

## The seam

Both halves reproduced on `booklet-a4.pdf` (28 sheets):

| entry point | result |
|---|---|
| `display::extract` (1-28) | ERR `annotations page 3: resolving named destination: missing required dictionary key "Names"` |
| `display::trace_elements` (1-28) | OK, 28 pages, 2252 elements |

## The honesty point: the plan's claim was not previously observable

Confirmed, structurally rather than by rebuilding the parent. `pdffonts -f 1
-l 2 booklet-a4.pdf` reports two non-embedded `Helvetica` (Type 1, WinAnsi,
`emb no`, `uni no`) on the first sheets, which is exactly the "lacks
ToUnicode" stop. Imposition places the covers on sheet 1, so before this WP
any trace from page 1 died on the Helvetica error on sheet 1, long before
page 3's annotation resolution. Both entry points failed identically.

So the plan recorded a distinction (`extract` dies where `trace_page` reads)
that nobody had observed, and which only became true once the covers decoded.
The worker was right to say so rather than presenting a confirmation.

## The covers trace

Exactly as claimed:

| page | elements | shows | characters | render modes |
|---|---|---|---|---|
| 1 | 8 | 5 | 166 | {3} |
| 56 | 12 | 10 | 371 | {3} |

Page 56's 371 against WP-5.3d's pypdf 380 is correctly recorded as a
**difference**, and the 9-character gap is accounted for by mechanism rather
than by decode error: WP-5.3d measured pypdf injecting synthetic spaces into
letter-spaced runs, making its count a superset. Every show on both faces is
mode 3, corroborating WP-5.4's finding that all cover text is the invisible
selectable layer.

## Stream order, measured

Confirmed on both faces, and the empty text object verified in the raw
stream rather than inferred:

| page | `/F1` | `3 Tr` | `/F2` |
|---|---|---|---|
| 1 | 19 | 240 | 280 |
| 56 | 19 | 201 | 235 |

Page 1's stream opens `1 0 0 1 0 0 cm  BT /F1 12 Tf 14.4 TL ET` — `/F1` is
set inside an **empty** `BT...ET` and never shows a glyph. So the Helvetica
decode is needed only to get past the `Tf`, as WP-5.4 predicted without
running the tracer.

## Judgment: leaving the simple-font sentinel open

**Agreed, and for a stronger reason than the one given.** Simple fonts are
confined to pages 1 and 56, confirmed independently (`pdffonts` per page: 2
on page 1, 2 on page 56, 0 on pages 2, 3, 28 and 55), so the sentinel is
outside the compared domain and closing it changes no verdict today.

The worker's "not by halves" argument is sound: the Inter-Regular subset can
be closed by WP-0.2i's outline-hash route, but non-embedded Helvetica cannot,
because there is no embedded font program whose outlines could be hashed —
for a standard-14 face glyph identity is defined by the *encoding*, which
this WP now records as the decoded string. The two halves need different
mechanisms and only one is available.

The decisive argument is rule 10 itself: closing the Inter half now would add
a comparison that **no fixture in the compared domain can exercise**, which
is the non-discriminating clause the rule exists to forbid. Better to close
both at WP-5.4g, when the covers enter the domain and there is something for
the clause to discriminate.

On labelling: the evidence does not use the phrase "non-discriminating", but
it states the substance accurately — the sentinel is open, outside the
domain, and has no consumer — and it makes no agreement claim that rule 10
would catch. Not a defect. A future reader would be helped by the explicit
label.

## Judgment: moving the standard-14 AFM failure to show time

**Precisely right, and load-bearing rather than cosmetic.** I checked whether
`/F1` carries `/Widths`, because if it did the whole path would be moot:

    page 1  /F1: BaseFont=/Helvetica  widths=False  enc=/WinAnsiEncoding
    page 56 /F1: BaseFont=/Helvetica  widths=False  enc=/WinAnsiEncoding

It genuinely has none. So the AFM path is reachable in principle and is
unreachable only because `/F1` never shows a glyph. Had the failure stayed at
load time, **the covers would not trace at all** and this WP's target would
be unmet.

It is not the trap the brief asked about, for three reasons. The deferred
failure is still loud and never guesses a width, so it cannot produce a
silently wrong glyph position in a geometric gate. Its message names the
condition exactly (`shows text but carries no Widths; standard-14 AFM metrics
are not implemented`), so it is diagnosable where it fires. And it fires at
the operation that actually needs the missing data, which is where a reader
looks.

One obligation for WP-5.4g, which should travel with the sentinel handoff the
worker already assigned there: when the covers enter the compared domain,
confirm that **neither leg shows standard-14 text**, because that is the
moment this deferred stop could fire. Today's WeasyPrint/reportlab leg is
safe (`/F1` set, never shown) and a Typst leg embeds its faces rather than
relying on standard-14, so the risk is a future cover design that draws text
in reportlab's default font.

## Residuals confirmed

`/Differences` and `MacRomanEncoding` are unimplemented and fail loud naming
the encoding, rather than mis-decoding. Symbol and ZapfDingbats are correctly
excluded from the standard-14 list, since they use built-in encodings.

## Erratum, not a defect

The evidence's `## Metrics` says "107 tests pass across 11 binaries". The
measured figure at this commit is **113 across 12**. The evidence's count was
accurate when written and went stale when WP-5.1e landed further tests
underneath; the claim it supports (the suite is green, the fault suite passes,
its matrix is unchanged) holds.
