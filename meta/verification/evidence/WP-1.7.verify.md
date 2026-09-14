# WP-1.7 verification

## Scope and downgrade

WP-1.7 is a Phase 1 spike, so per the Phase 1 preamble verification is an
EVIDENCE-CONSISTENCY AUDIT, not a replay: the spike code was uncommitted and
is gone, and the intermediate dumps (`wp17-measures2.json`,
`wp12-weasy-runs.json`, `wp17-weasy-verify.json`) are not in the repository.

Audited harder than a pure measurement, because this spike's output is a
number that enters the engine: WP-2.2a's body column width. Everything
checkable from the evidence's own figures or from the repository was
recomputed rather than read.

- Verified WP: commit `2873f8b`, `meta/verification/evidence/WP-1.7.md`
- Base: `6e8abb8`, plan revision 10 (`6c13738`)

## Owns

`git show --stat 2873f8b`: one file, `meta/verification/evidence/WP-1.7.md`,
444 insertions. No tracked source, no `*.verify.md`, no `baseline.json`. The
working tree carries nothing of the spike's (the one modified path,
`meta/plans/typst-parity-and-rust-migration.md`, belongs to the concurrent
planning agent). Clean.

## Verdict

**ACCEPTED.** The interval derivation is sound, the intersection arithmetic
is exact, both bounds are bracketed by measured failures, and the
recommended constant is confirmed by rendering. Findings below are recorded,
none is rejection-worthy, but findings 2, 3 and 4 must reach WP-2.2a.

## 1. Intersection arithmetic: EXACT, no sign error

Recomputed from the stated absolute bounds:

| measure | lower delta | upper delta | width |
|---|---|---|---|
| 325.0000 | +0.010000 | +0.040000 | 0.030000 |
| 311.0000 | -0.360000 | +0.200000 | 0.560000 |
| 312.1614 | -10.021400 | +11.348600 | 21.370000 |

`max(lower) = +0.010000`, `min(upper) = +0.040000`, so the intersection is
`[+0.010000, +0.040000)`, set entirely by the 325 pt group, exactly as
claimed. The 312.1614 row subtracts correctly in both directions
(312.1614 - 302.140000 = 10.021400; 323.510000 - 312.1614 = 11.348600) and
no row is mis-signed. Intersection midpoint +0.025000; resulting widths
325.025000 / 311.025000 / 312.186400, matching the evidence.

## 2. Upper bound: INFERRED, not measured

The rendered deltas are 0, +0.005, +0.010, +0.025, +0.039, +0.045.
**+0.040000 itself was never rendered.** The exclusivity claim in Residuals
("+0.040000 itself is NOT safe") is therefore derived from the model (at
that width block 137 line 1's next-unit measure equals the column width, so
the unit fits and is pulled up), not observed.

What IS measured:
- safe, 149/149 and 968/968: +0.010, +0.025, +0.039
- fails: +0.005 (below the lower bound, block 135 breaks early) and +0.045
  (above the upper bound, block 137 pulls "cost" up)

So the measured-safe range is `[+0.010, +0.039]` and both edges of the
model's interval are bracketed by real failures. The recommendation +0.025
sits strictly inside both the modelled and the measured range. This is a
labelling precision issue, not a soundness one, but WP-2.2a should treat
+0.039 rather than +0.040 as the highest demonstrated-safe delta.

## 3. Precision WP-2.2a must carry

Checked against the window `[325.010, 325.040)`:

| value | inside |
|---|---|
| 325.0 | no |
| 325.02 | yes |
| 325.025 | yes |
| 325.03 | yes |
| 325.04 | no |
| 325.05 | no |
| 325.1 | no |

The evidence's concrete claims are all correct (325.03 inside; 325.0 and
325.05 outside). Its generalization, "it needs three decimals", is an
overstatement: **two decimals suffice** to land inside the window, since
both 325.02 and 325.03 are admissible. **One decimal does not** (325.0 and
325.1 are both outside). Three decimals are needed only to express the
recommended midpoint 325.025 exactly.

Statement for WP-2.2a: carry the delta as **+0.025 pt** and the widths as
325.025 / 311.025 / 312.1864. If a two-decimal constant is unavoidable,
325.02 or 325.03 both remain inside the window and inside the
measured-safe range; never round to one decimal. Given finding 2 (the upper
edge is inferred), staying at the midpoint rather than drifting up is the
prudent choice.

## 4. Baseline discrepancy against WP-1.2: UNRECONCILED

WP-1.7's own delta-0 run reports **147/149 paragraphs and 962/968 lines**.
WP-1.2 reports **148/149 and 963/968** for what both WPs describe as the
same population (149 `p` blocks, 968 lines, the 6 `span` blocks excluded);
WP-1.2's verifier confirmed its arithmetic (968 - 963 = 5 differing lines,
consistent with block 135's five-line cascade).

So WP-1.7's harness sees one additional divergent block contributing one
additional differing line at the unwidened measure, and the evidence neither
names that block nor explains it: the delta-0 row's outcome column cites
only "block 135 breaks early", which accounts for one miss, not two. The
same extra miss appears at +0.045 (147/149, 963/968).

Why this does not block acceptance:
- the interval itself is derived in step 2 from `measure()` values, entirely
  independently of the render harness;
- at the recommended constant the harness reports 149/149 and 968/968, so
  whatever the second delta-0 miss is, the widening fixes it too, and the
  headline result is stronger than WP-1.2's baseline rather than weaker;
- both bounds remain bracketed by measured failures.

But it is an unexplained instrument disagreement between two spikes, and it
is the third such case in this phase (WP-1.2 vs WP-1.3 differed by 26 lines;
WP-1.1 vs WP-1.6 proved unreconcilable as written). Worth noting that
WP-1.2's evidence records its own instrument improving "from 147/149 to
148/149" once styled runs were preserved, so a harness difference in styled
run handling is the first place to look. WP-2.2a should not treat 147/149 or
148/149 as a settled baseline without re-measuring.

## 5. Per-measure midpoint column invites misreading

The Metrics table's "midpoint" column gives 325.025000, 310.920000 and
312.825000, which are the midpoints of each measure's OWN interval. Only the
first coincides with the recommendation. Applying the per-row midpoints
would set the 311 pt column to delta -0.080000, outside the intersection
`[+0.010, +0.040)` that the same evidence derives. The prose is unambiguous
("one constant serves all three... 325.025000, 311.025000, 312.186400"), so
this is presentation risk rather than error, but WP-2.2a must take the
single delta, not the column.

## 6. Population substituted for the plan's clause

The plan's Verify clause reads "reproduces WeasyPrint's breaks on 899/899
body lines". WP-1.7 scored 149 paragraphs / 968 lines instead, stating that
968 strictly contains both WP-1.6's 899 and the 698-line unstyled subset.
The substitution is toward a STRICTER bar and the evidence declares it
openly, so the clause is satisfied a fortiori IF the containment holds.
Containment is asserted, not demonstrated, and the dumps that would prove it
are gone. Given 899 is WP-1.6's filter over body lines of the same `p`
blocks, it is plausible and I record it as asserted rather than verified.

## 7. Modelling caveat: confirmed in source

The upper-bound model depends on knowing where a line may break, and the
evidence's correction (excluding non-breaking characters from the split,
after a first attempt produced an impossible 293.30 pt bound at a 311 pt
column) rests on the adapter binding a paragraph's last two words. Confirmed
in `src/magazine/weasyprint_adapter.py`: `_NO_BREAK_SPACE = " "` at
line 312, `_bind_paragraph_tails` at 773 called from 725, `_bind_last_two_words`
at 782. The behavior is real.

The evidence further reports that a tighter variant, also breaking after
hyphen, en dash, em dash and slash, selected the same binding candidate at
every measure, so the bound does not depend on that modelling choice. That
robustness check is the right one to have run; its output is not preserved,
so it is audited rather than reproduced.

## 8. Independence of the 325.010000 agreement

The evidence presents WP-1.6's 325.010000 reproducing exactly as
corroboration. Precisely stated, this is a REPRODUCTION rather than an
independent derivation: both WPs obtained it from Typst's `measure()`, and
WP-1.7 reused WP-1.2's `wp12-weasy-runs.json` as input. What makes the value
independently corroborated is WP-1.6's own second instrument, a rustybuzz
advance sum agreeing at 325.0100000000 (32501 font units at upem 1000). The
agreement is still meaningful (it shows the pipeline is reproducible across
two spikes), but it is not two instruments agreeing.

## 9. Input revalidation: done properly

The worker did not trust the surviving WP-1.2 and WP-1.6 dumps, which were
taken under an uncommitted hyphenation switch while WP-1.5 has since landed
a differently scoped `html:lang(en)` one. It re-rendered at `6e8abb8` with
width instrumentation in a throwaway worktree and found **zero** of the 149
`p` blocks differing in line set or measure. This is the correct discipline
and it is the reason the reused dumps are acceptable inputs.

## 10. Harness hygiene, minor

The step-3 listing contains dead code (`if False: continue`) and a silent
filter (`if not all(lines): continue`) that would drop any block containing
an empty line without reporting the exclusion. The reported totals are 149
blocks and 968 lines throughout, so nothing was in fact excluded, but the
filter is unguarded and the block-count print goes to stderr and is not
recorded in the evidence. A later WP reusing this harness should assert the
population size rather than trust it.

## Commands

```sh
git show --stat 2873f8b
python3 -c "
rows=[(325.0000,325.010000,325.040000),(311.0000,310.640000,311.200000),(312.1614,302.140000,323.510000)]
los=[];ups=[]
for m,lo,up in rows:
    dlo=round(lo-m,6); dup=round(up-m,6); los.append(dlo); ups.append(dup)
    print(f'{m:10.4f} delta [{dlo:+.6f}, {dup:+.6f})  width {round(up-lo,6):.6f}')
print('intersection: [%+.6f, %+.6f)'%(max(los),min(ups)))
print('midpoint: %+.6f'%((max(los)+min(ups))/2))
for v in (325.0,325.02,325.025,325.03,325.04,325.05,325.1):
    print(f'  {v:9.3f} inside={325.010 <= v < 325.040}')
"
grep -n "_bind_last_two_words\|_bind_paragraph_tails\|_NO_BREAK_SPACE" src/magazine/weasyprint_adapter.py
grep -n "148/149\|963/968" meta/verification/evidence/WP-1.2.md
sed -n '/^### WP-1.7/,/^### /p' meta/plans/typst-parity-and-rust-migration.md
```

## Status

`accepted`. The number WP-2.2a must carry is **delta +0.025 pt**
(325.025 / 311.025 / 312.1864), with findings 2, 3 and 4 attached: the upper
edge is inferred rather than measured, two decimals suffice but one does
not, and the delta-0 baseline does not reconcile with WP-1.2's.
