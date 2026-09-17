# WP-0.2i verification

Verifier for WP-0.2i (per-glyph positions), protocol rule 3, critique folded in.
Worker commit `18e35ed`. Verified in a fresh worktree at that commit.

## Verdict

**REJECTED**, on one defect, which is in the implementation of the shape
constraint rather than in the design of the gate.

The shape constraint rejects the mechanism the bound is derived from. A drift
fixture built as the honest staircase Pango actually produces fails with 40
shape violations at ratio 0.1785, no magnitude breach anywhere. Legitimate
drift is therefore a false fail, and the real Typst-versus-WeasyPrint
comparison would hit it on every page.

Everything else in the WP reproduced, including the result that matters most:
the ceiling is genuinely size-independent.

## The defect

`axis_shape` (display.rs:396) requires the per-axis difference sequence to be
one-signed and **exactly** monotone non-decreasing in magnitude, over values
that have been quantised to 0.0001 pt by `qo`.

Real drift has flat regions. WeasyPrint advances by an integer count of
1/1024 px, so the true difference between the legs steps by one tick and is
**flat in between** — WP-1.6 measured 0.000173 pt per glyph, which is 0.236 of
a tick, so a tick lands about every 4.2 glyphs and the other 3.2 are flat.

One tick is 0.000732421875 pt, which is **7.324 quanta of 0.0001 pt, not an
integer**. So a flat region of the true difference is recorded as a value that
alternates between two adjacent quanta, `|v|` decreases at those points, and
`axis_shape` returns false. Demonstrated arithmetically, independent of the
tracer:

```
flat true difference 0.025000000 pt  ->  recorded quanta [-250]        (exact multiple, no jitter)
flat true difference 0.002197266 pt  ->  recorded quanta [-22, -21]    (3 ticks, jitters)
```

### Rule 11 isolation: remove the flats and the effect goes

Three fixtures, same corpus, same code path, differing only in whether the
difference sequence ever goes flat:

| fixture | per-glyph step | flat regions | worst ratio | result |
|---|---|---|---|---|
| `drift` (the WP's floor) | 0.000173 pt every glyph | no | 0.2731 | pass, 0 violations |
| `smoothdrift` (mine) | 0.0005 pt every glyph | no | 0.5461 | pass, 0 violations |
| `stairdrift` (mine) | 0.000732 pt every 4.2 glyphs | **yes** | 0.1785 | **fail, 40 shape violations** |

The failing fixture has the **smallest** magnitude of the three, and fails with
`worst_excess_pt` exactly 0.000000, so nothing about magnitude is involved. Two
no-flat fixtures at different rates both pass. The cause is isolated to the
presence of flat regions.

`stairdrift` is the honest model: cumulative shift `floor(k * 0.2362) * tick`,
built across all 1,488 shows of the interior, reproducing WP-1.6's measured
rate through WP-1.6's measured mechanism. The WP's own floor fixture is a
perfectly linear ramp, which never goes flat, and that is the only reason it
passes: its per-glyph step is 1.73 quanta, always enough to swamp the
one-quantum jitter.

### Two fixes, one of which does not loosen anything

- Make one tick an integer number of quanta (for example `GLYPH_QUANTUM =
  tick/8 = 9.1552734375e-5`). Flat regions then land on exact multiples and
  cannot jitter. This is an implementation choice and loosens nothing, so it is
  available to the WP without a plan revision.
- Allow the monotonicity test one quantum of slack. This is a **loosening** of
  the shape rule as revision 15 states it, so under rule 4 it would be a plan
  matter, not the WP's call.

I recommend the first. The second also weakens the constraint that gives the
ceiling its size-independence, which is the WP's best property.

## The f32 question, checked rather than assumed

The coordinator supplied a computed prior from plan revision 25: an f32 ulp is
3.87e-5 pt at 325 pt, which is 5.3% of the magnitude bound at k=1 but roughly
**22% of one expected step** against the shape constraint, with the honest
warning that this is the opposite of the reassuring answer.

**Measured answer: f32 is not the mechanism here, and it is shape-preserving.**

- **Accumulation is f64 from f32 inputs.** `num()` (streams.rs:225) matches
  `Object::Real(r)` and returns `f64::from(*r)`; `tx`, `starts` and `qo` are all
  f64. So each authored value carries a one-time parse quantisation and nothing
  compounds in the accumulator.
- **The error is a scale error, so it preserves monotonicity.** The f32-parsed
  quantities entering an offset are the font size (`Tf`), the `Tm`/`cm`
  components forming `base`, and the TJ adjustments. Size and matrix errors
  enter as a *relative* factor multiplying `v`, so they add a smooth ramp
  proportional to position rather than per-step noise. A monotone error added to
  a monotone sequence stays monotone. That is why the prior's 22% figure
  overestimates: it compares an ulp at 325 pt against one 0.000173 pt step, but
  the error at 325 pt is not a per-step perturbation.
- **Empirically disproved as a shape risk.** If per-step f32 noise were 22% of a
  step, `drift` and `smoothdrift` could not produce **zero** violations across
  68,800 glyphs in 1,488 shows; random 22% perturbations would break exact
  monotonicity somewhere. Both produce zero.
- **Against magnitude it is negligible at every k**, not only at large k: at
  k=1 the accumulated error is one advance's ulp (~9.5e-7 pt at an 8 pt advance)
  against a 0.000732 pt bound, about 0.13%; at k=70 the dominant `base` scale
  error is ~3.9e-5 pt against a 0.0512 pt bound, about 0.08%.

So WP-0.2j (the shared exact-number path) is **not** a prerequisite for this
clause. It remains worth doing for WP-5.2's reasons, and the bound's derivation
does not need to account for parser precision.

## Reproduced from the evidence

Floor, ceiling, margin, and all five must-fail fixtures, rebuilt from `mkfix.py`
and `mkfix6.py`:

| fixture | claimed | observed |
|---|---|---|
| `drift` (floor) | pass, ratio 0.2731 | pass, ratio 0.2731, 0 violations |
| `kern02` | fail, 10.2400 | fail, 10.2400, 5 violations |
| `kern005` | fail, 2.5941 | fail, 2.5941, 5 violations |
| `kern001` | fail on shape alone | fail, ratio 0.5461, excess 0.000000, 1 violation |
| `linmatrix` | fail, 2.8672, 9 violations | fail, 2.8672, 9 violations |
| `glyphsub` | caught by `gids` alone | confirmed, see below |
| `ocmember` | fail-loud stop | `operator BDC: optional content membership unsupported` |
| `annotap` | fail-loud stop | `annotation Link carries an appearance stream` |

**The ceiling is size-independent, and this is the WP's strongest result.**
`kern001` fails with `worst_excess_pt` exactly 0.000000 and ratio 0.5461, well
under 1.0, so its single violation is the shape message with no magnitude
breach. I pushed further than the evidence: a compensating kern at 0.0001 pt,
and three trailing-compensated variants of my own designed to keep the sequence
monotone (`advtail02`, `advtail_small`, `advtail_late`, the last placed at glyph
40 of a 73-glyph show where the bound is loosest), plus a mid-suffix variant
(`advmid`). **I could not construct a compensating kern that passes.** Every one
failed, and the small ones failed on shape with zero magnitude excess.

**`gids`-alone isolation confirmed**, which is what proves the glyph-identity
blind spot is actually closed:

```
tier S text:            pass (0 pages differ)
tier E glyph positions: pass (68800 glyphs, worst ratio 0.0000, 0 violations)
tier E display list:    fail (12 pages differ)
```

**Determinism**, byte-identical across consecutive runs and matching the
evidence exactly: A-vs-A `0e21644ee602ff8a78fc6ac20289c8032c5ba5c4905f8327668a436784b189e0`
twice, A-vs-B `6e932ea43678b91add20a13847e633555e2a3a8b19ef159e86fc0cc2b6015836` twice.

## Critique points

- **Bound reset point: correct.** `k` is the index within the element
  (display.rs:440), and one element is one show, so `k` resets per show. The
  plan records each laid-out line as its own show, and WP-1.6's drift
  accumulates within a line, so the reset matches the mechanism.
- **Offsets are device space: confirmed.** `base = Tm · CTM` and `offs =
  [qo(v*base[0]), qo(v*base[1])]` (streams.rs:404, 417). The translation
  cancels because offsets are measured from the show origin, and the linear part
  is applied, which is exactly what makes the linear-matrix amplification
  observable. `tx` is already post-`Tf`, so the size is not applied twice.
- **Zero difference sequence: handled.** `axis_shape` on all zeros keeps
  `sign = 0` and `prev = 0`, and `0 >= 0` holds, so it returns true. `worst_ratio`
  guards `bound > 0.0`, so glyph 0 never divides by zero.
- **Simple-font sentinel: adequately disclosed, and WP-0.2h's reasoning is
  sound.** Unresolved codes map to `UNRESOLVED_GID` and compare equal on both
  legs. WP-0.2h (`0bf3977`) deliberately left it open because the Inter subset
  could be closed by the outline-hash route but non-embedded Helvetica cannot —
  there is no embedded program to hash, and for a standard-14 face glyph
  identity is defined by the encoding — so closing it by halves would be worse
  than leaving it named. I agree. Under rule 10 it is non-discriminating
  evidence and must say so: the WP's Residuals do label it, and I recommend the
  `parity.yaml` clause carry the same label, since rule 10 binds evidence
  wherever it is offered.
- **Cross-WP edit: legitimate and minimal.** The diff adds exactly one entry,
  `glyph_positions`, to `fault_suite.clause_vocabulary`. WP-0.2d's
  `seeded_faults_are_detected` passes (21.5 s) with its expected-detections
  matrix unchanged, which is the handoff that guard exists to force.
- **Owns: clean.** `18e35ed` touches only `mag/src/parity.rs`,
  `mag/src/parity/display.rs`, `mag/src/parity/streams.rs`, `parity.yaml` and
  its own evidence. No Cargo change, no verify file, no `baseline.json`.
- **Baseline: green.** `cargo fmt --check`, `cargo clippy --all-targets -D
  warnings` and the full `cargo test` all pass in the worktree.
- **Evidence erratum**, minor: line 26 says the fixture scripts are "reproduced
  verbatim in ## Residuals"; Residuals says they are in the job scratch
  directory, which is where they are. The scripts do rebuild from pypdf and
  fontTools as described.

## What the WP must do to clear this

Change the offset quantum so one tick is an integer number of quanta, or bring
a plan revision for a tolerance. Then re-run the floor with a **staircase**
fixture rather than a linear ramp, since the linear ramp cannot exercise the
failure. `stair.py` is in the job scratch directory and reproduces it.

## Status

rejected
