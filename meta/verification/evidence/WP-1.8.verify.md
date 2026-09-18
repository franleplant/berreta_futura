# WP-1.8 verification: reconcile the third cross-spike line count

**Verdict: ACCEPTED**

Every number in `## Metrics` was reproduced independently, from a third
worktree, by extracting the `## Commands` blocks programmatically and running
them under `env -i`. Every count cited below was re-derived from its own miss
enumeration rather than read off a total (rule 9). The two corrections WP-1.8
makes to accepted WPs both hold, and they should propagate into the plan:
WP-1.2's "147/149 improving to 148/149" and WP-1.7's delta table are each wrong
in the way WP-1.8 says. **WP-1.7's +0.025000 pt body-measure recommendation
SURVIVES**, and survives for the reason WP-1.8 gives rather than for the reason
WP-1.7's own verifier gave.

Phase 1 spike, so verification is the evidence-consistency audit rule 3
prescribes, plus a full replay of the measurement.

## Setup

```sh
git worktree add /Users/franguijarro/.claude/jobs/7d99e27f/tmp/vwp18 da83e2b
```

Neither the worktree the work was developed in nor the one it was replayed in;
both are gone from `git worktree list`. `mag/src/parity.rs` was not touched and
no comparator was invoked, so the `out_dir` collision hazard was never in play.

Commit shape, checked before replaying:

```sh
git show --stat fc1b954
git show --stat da83e2b
```

`fc1b954` adds 572 lines to `meta/verification/evidence/WP-1.8.md` and nothing
else; `da83e2b` adds 12 lines to the same file and nothing else. No tracked
source file changed, no `*.verify.md`, no `baseline.json`. Owns respected.

The instrumentation is genuinely gone from the shared tree:

```sh
git status --porcelain src/magazine/
grep -n "_dump_prose_lines\|MAG_LINE_DUMP" src/magazine/weasyprint_adapter.py
```

Clean, and the grep exits 1. The recorded revert
(`git show HEAD:src/magazine/weasyprint_adapter.py > ...`) also left the
verification worktree clean after the replay re-applied the instrumentation:
`git status --porcelain` in it returns nothing.

## Rule 12: the commands were extracted, not transcribed

```sh
cat > extract_commands.py <<'PY'
import hashlib, pathlib, re, sys
src = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
lines = src.splitlines(keepends=True)
start = next(i for i, ln in enumerate(lines) if ln.rstrip("\n") == "## Commands")
end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("## "))
section = "".join(lines[start:end])
fence = chr(96) * 3
blocks = re.findall("^" + fence + r"sh\n(.*?)^" + fence + "$", section, re.S | re.M)
out = "".join(blocks)
pathlib.Path(sys.argv[2]).write_text(out, encoding="utf-8")
print("sh blocks", len(blocks), "bytes", len(out.encode()))
print("sha256", hashlib.sha256(out.encode()).hexdigest())
PY
uv run --no-project python extract_commands.py \
  meta/verification/evidence/WP-1.8.md wp18_commands.sh
```

6 `sh` fences, 8681 bytes, sha256
`599b7472343436c48fdaf12aae5e48b6cddb61c82bd55650f99042fd2fa9fed9`. The
concatenation is a coherent script: the later blocks use `$CHECKOUT`, `$WORK`
and `$TYPST` that the first block defines.

Executed with only `HOME`, `PATH` and `TERM` inherited, with a deliberately
hostile `TYPST_ROOT`, from the verification worktree:

```sh
cd /Users/franguijarro/.claude/jobs/7d99e27f/tmp/vwp18 && env -i \
  HOME="$HOME" PATH="$PATH" TERM=dumb \
  MAG_RUN_DIR=/Users/franguijarro/code/magazine/editions/010/run-2026-09-13T01-34-51 \
  WP18_WORK=/Users/franguijarro/.claude/jobs/7d99e27f/tmp/vwp18-work/w \
  TYPST_ROOT=/Users/franguijarro/.claude/jobs/7d99e27f/tmp/vwp18-work/w/typst-install \
  bash wp18_commands.sh
```

Exit 0. `WP18_TYPST_INSTALL` was deliberately NOT set, so the block built its
own typst 0.15.1 from source rather than reusing the worker's prefix. Its first
line printed the mode as rule 2b requires:
`MODE: measuring the live edition 010 corpus at .../run-2026-09-13T01-34-51`.

### The `TYPST_ROOT` guard works, and it is load bearing (rule 11)

With `TYPST_ROOT` exported to the install prefix and the block's `unset` in
place, the whole replay ran green. Removing the supposed cause, that is running
the block's own runner with `TYPST_ROOT` still set:

```sh
cd "$WORK" && env -i HOME="$HOME" PATH="$PATH" TERM=dumb \
  CHECKOUT=... WORK=... TYPST=... TYPST_ROOT="$WORK/typst-install" \
  uv run --no-project python wp18_run.py recorded
```

fails on the first compile with `error: source file must be contained in
project root`, then `harness wp18a-wp12-appendix failed`. Effect appears when
the guard is removed and goes when it is restored. Residual 5 is correct:
`TYPST_ROOT` is the typst CLI's project root, not an install prefix.

## Tool versions, confirmed in the replay environment

typst 0.15.1, pdftotext 25.08.0, python 3.12.11 (`uv run python`), uv 0.8.17.
All match `## Tool versions`.

## Claim 1: the two harnesses are the same program

Extracted myself, not reused from the worker:

```sh
uv run --no-project python -c '...PYBLOCK.findall(WP-1.2.md)[2], (WP-1.7.md)[1]...'
```

| harness | my sha256 | evidence records |
|---|---|---|
| WP-1.2 appendix | `ee02136dd6b7ca780f7b751004917f5ed75b9de60c1b22d78d7e02c1e6fa00ca` | identical |
| WP-1.7 section 3 | `1900b2be7941e0a4485d085ad2117a80b9bba9520a912e8e6aa9b6cc7011595d` | identical |

A unified diff of the two extracted blocks (138 against 139 lines) shows
exactly four differences: the `FONTS` constant, the added
`DELTA = float(sys.argv[1]) ...`, `w` becoming `round(w + DELTA, 6)` in the tag
and page width, and the `wp12d-`/`wp17v-` output tags. At `DELTA = 0`,
`str(round(w, 6)) == str(w)` for all three measures, so at delta 0 they are the
same program modulo output filenames. Both carry the identical
`return [" ".join(s.replace("\xa0", " ").split()) for s in seq]`, checked at the
byte level, so the normalization really is shared rather than a difference
between them.

Input identity, which is the stronger half: my own instrumented render, in my
own worktree, from the `env -i` shell, produced

```
e4ab672cefe221d06d2df1237e7663761a1e7c2f4311cb6d0d6a4f8581a7ac41  wp18-weasy-runs.json
```

byte-identical to the digest WP-1.2 produced, WP-1.7 reused and WP-1.8 records.
The three spikes measured one population.

Population re-derived from the dump rather than accepted: 155 keyed blocks, 149
`p` blocks totalling 968 lines, 6 `span` blocks at 6.8 pt excluded; 124 blocks
(812 lines) at 325.0000 pt, 24 (154 lines) at 311.0000 pt, 1 (2 lines) at
312.1614 pt; 27 styled blocks (270 lines) and 122 unstyled (698 lines).

Measured, at delta +0.000:

| harness | paragraphs | lines | miss set |
|---|---|---|---|
| WP-1.2 appendix | 147/149 | 962/968 | 4, 135 |
| WP-1.7 section 3 | 147/149 | 962/968 | 4, 135 |

Neither produces 148/149. **Claim 1 reproduced.** Each total re-derived from
the enumeration: block 4 contributes one differing line (index 5) and block 135
five (indices 0 to 4), so 149 - 2 = 147 and 968 - 6 = 962.

## Claim 2: the removal test

| treatment | paragraphs | lines | miss set |
|---|---|---|---|
| as recorded | 147/149 | 962/968 | 4, 135 |
| styled-run preservation REMOVED | 147/149 | 960/968 | 39, 135 |
| size-exclusion treatment | 146/147 | 937/942 | 135 |

Paragraph count unmoved, and the removal is not inert: the line count drops by
two and the miss set changes completely. Block 39 diverges at its lines 8, 9
and 10 (11-line block at the 311 pt measure), block 135 at all five, so
968 - 8 = 960. The size-exclusion row changes the POPULATION to 147 blocks and
942 lines, confirming WP-1.8's point that its numbers are not comparable to
either spike's. **Claim 2 reproduced.**

## Claim 3: the 147 before and the 147 after are two different 147s

This is the claim I attacked hardest, and it holds.

| | paragraphs | miss SET |
|---|---|---|
| before the styled-run fix (flat) | 147/149 | **{39, 135}** |
| after the styled-run fix (as recorded) | 147/149 | **{4, 135}** |

The sets are disjoint except for 135. Compared as totals the fix does nothing;
compared as sets it repairs 39 and introduces 4. So WP-1.2's recorded
progression "147/149 to 148/149" cannot be produced by its own recorded harness
under its own recorded normalization, and the 148 is the count after block 4 is
discounted by hand as an artifact.

Two independent supports I found in WP-1.2's own text, which WP-1.8 does not
cite and which make the reconstruction stronger than it claims:

- WP-1.2's `## Verdicts` describes `wp12d-misses.json` as **"the two recorded
  misses"**, while its headline table on the same page reports **"misses: 1"**.
  The recorded instrument produced two; the headline reported one. That is the
  discount, admitted in passing.
- The arithmetic matches exactly: 149 - 1 = 148 and 968 - 5 = 963 are the
  numbers you get by dropping block 4 and keeping block 135's five-line
  cascade, which is precisely what the whitespace-removed normalization
  produces mechanically.
- The mechanism is self-consistent: block 4 is a miss only when the font change
  is present, so it cannot exist in a flat pass, and block 39 diverges only when
  the bold run is flattened, so it cannot exist in a styled pass. Each pass has
  exactly one of them.

**Claim 3 reproduced.** One phrasing nit, not a defect: section 2 says the 148
"came from somewhere else entirely", while sections 3 and 4 correctly identify
where it came from, the same harness with the artifact removed.

## Claim 4: the named cause

One line changed, everything else held fixed, delta +0.000:

| harness | `norm` treatment | paragraphs | lines | miss set |
|---|---|---|---|---|
| WP-1.2 appendix | collapse (as recorded) | 147/149 | 962/968 | 4, 135 |
| WP-1.2 appendix | remove whitespace | 148/149 | 963/968 | 135 |
| WP-1.7 section 3 | collapse (as recorded) | 147/149 | 962/968 | 4, 135 |
| WP-1.7 section 3 | remove whitespace | 148/149 | 963/968 | 135 |

Both harnesses land on 148/149 and 963/968, WP-1.2's headline exactly. The
effect appears when the treatment is applied and returns when it is removed, on
both programs, which is the rule 11 shape. I also re-derived the
whitespace-removed column a second way, without re-running typst, by applying
`"".join(s.split())` to the stored strings in each collapse run's own
`*-misses.json`: it reproduces the same paragraph counts, line counts and miss
sets at every delta. **Claim 4 reproduced, twice.**

## Claim 5: the named block, verified independently of the worker's script

From the dump directly, block 4, `tag=p`, width 433.3333 px = 325.0000 pt, 12
lines. Line index 5 has exactly two runs:

| run | family | weight | size | character range | text |
|---|---|---|---|---|---|
| 0 | Magazine Mono (Geist Mono) | 500 | 10.9333 px = 8.2000 pt | [0:13] | `verification)` |
| 1 | Magazine Serif (Source Serif 4 SmText) | 400 | 13.3333 px = 10.0000 pt | [13:65] | `, which named the CVE it was probing for rather than` |

The run boundary is at character 13 because `verification)` is 13 characters.
The first differing character between the two sides is index 13:
`weasy[13] == ','` against `typst[13] == ' '`, with `weasy[:13] == typst[:13]
== 'verification)'`. The two lines are equal with whitespace removed, and all 12
lines of the block are equal whitespace-insensitively. The font boundary and the
character index are therefore the same position, derived from two independent
artifacts (the WeasyPrint run dump and the poppler extraction).

Reader page located from a fresh `pdftotext -layout` of the replay's own
`reader.pdf`: block 4 line 5 on page **6**, block 135 line 0 on page **47**,
block 137 line 1 on page **48**. **Claim 5 reproduced.**

## Claim 6: discrimination, and claim 7: the residual

Whitespace removal is not a blanket pass. Under it:

- block **135** still fails at +0.000 and +0.005, all five lines displaced,
  measure 325.0000 pt, reader page 47, single family Magazine Serif. This is
  WP-1.2's known 325.01-against-325 pt miss, unchanged;
- block **137** still fails at +0.045, four differing lines (indices 1 to 4),
  measure 325.0000 pt, reader page 48;
- the six deltas partition 3 pass / 3 fail under the removal treatment, so the
  treatment discriminates on a non-trivial partition rather than agreeing with
  everything.

**Claims 6 and 7 reproduced.**

## The adjudication of WP-1.7, both halves separately

### Half one: the delta table IS mixed. Confirmed.

| delta | WP-1.7 records | collapse (its recorded harness) | whitespace removed | miss set, collapse | miss set, removed |
|---|---|---|---|---|---|
| +0.000 | 147/149, 962/968 | **147/149, 962/968** | 148/149, 963/968 | 4, 135 | 135 |
| +0.005 | 147/149, 962/968 | **147/149, 962/968** | 148/149, 963/968 | 4, 135 | 135 |
| +0.010 | 149/149, 968/968 | 148/149, 967/968 | **149/149, 968/968** | 4 | none |
| +0.025 | 149/149, 968/968 | 148/149, 967/968 | **149/149, 968/968** | 4 | none |
| +0.039 | 149/149, 968/968 | 148/149, 967/968 | **149/149, 968/968** | 4 | none |
| +0.045 | 147/149, 963/968 | **147/149, 963/968** | 148/149, 964/968 | 4, 137 | 137 |

Every cell reproduced, and every total re-derived from the miss enumeration
underneath it. The argument is forced rather than merely plausible: **no single
normalization reproduces all six recorded rows.** The three outside the interval
match collapse and not removal; the three inside match removal and not collapse.
So the recorded table cannot have come from one run of the recorded harness.
This is an error in an ACCEPTED WP and it should be recorded as one.

### Half two: the interval and the +0.025000 pt recommendation SURVIVE.

Checked as a separate question, because it could have gone the other way.

- The interval is not derived from the harness at all. WP-1.7 section 2
  computes it from typst `measure()` values (`wp17-measures2.json`, 2606
  measurements), and the harness is only the empirical confirmation. An error
  in the confirmation table cannot move a bound it did not set.
- Under EITHER normalization the empirical transitions sit at the same deltas.
  Block 135, the lower-bound binder, is a miss at +0.000 and +0.005 and absent
  from +0.010 up, under both. Block 137, the upper-bound binder, is a miss at
  +0.045 only, under both. Block 4 is a miss at ALL SIX deltas under collapse
  and at NONE under removal, so it is a constant offset and can move neither
  bound. The artifact being width-independent is itself the check that it is
  not a break effect.
- The measured-safe delta set is therefore `{+0.010, +0.025, +0.039}` under
  both treatments, unchanged. Only the score attached to it changes, from
  149/149 and 968/968 whitespace-insensitively to 148/149 and 967/968 under the
  recorded harness.
- WP-1.7's separate sub-claim, "restricted to the 122 unstyled blocks (698
  lines) at delta +0.025: 698/698 lines identical, zero divergent blocks", is
  untouched. I re-derived 122 unstyled blocks and 698 lines from the dump, and
  block 4 is `styled=True` (its mono run is weight 500), so it never entered
  that subset.

**A third party is corrected that WP-1.8 does not name.** WP-1.7's own verify
file, section 4, gives as its reason for not blocking: "at the recommended
constant the harness reports 149/149 and 968/968, so whatever the second delta-0
miss is, the widening fixes it too". Measured, that is false. Widening never
fixes block 4, at any delta. The conclusion survives on WP-1.8's substitute
argument, the constant offset, not on that one. `WP-1.7.verify.md` section 4
needs the same correction as `WP-1.7.md`.

## What this verification cannot discriminate (rule 10)

- **Whether WP-1.2's actual first-pass `wp12_compare.py` is what the "flat"
  variant reconstructs.** WP-1.8 says this itself under NOT PROVEN, and I
  cannot close it either: that script is not in the evidence. What IS proven,
  and is enough for the finding, is that the recorded harness's progression is
  not the one WP-1.2 recorded, and that the treatment in question cannot move
  the paragraph count in either direction.
- **How WP-1.7's table came to mix normalizations.** A modified harness for
  three rows and a hand correction for three rows are indistinguishable from
  the artifacts. What is established is the reproducibility failure, which is
  the part that matters.
- **Whether the inserted space is poppler's or typst's.** Unresolved, correctly
  flagged NOT PROVEN by WP-1.8 and owned by WP-2.3. My verification adds
  nothing here; I did not open the content stream either.
- **Whether whitespace removal could mask a genuine break divergence.** I
  showed it does not mask the two real ones present in this corpus, and no
  moved token can be pure whitespace, so the masking mode is hard to construct.
  I did not build a fixture that would exhibit it, so this rests on an argument
  plus a non-trivial 3/3 partition, not on a negative fixture.
- **Nothing outside blocks 4, 39, 135 and 137 was inspected line by line.** The
  other 145 blocks are agreements, and an agreement is the weaker kind of
  evidence; they are counted, not read.

## An erratum found independently, in WP-1.2 rather than WP-1.8

WP-1.2 records "The 6 excluded blocks (**34 lines**) are `span`-tagged blocks at
6.8pt". Enumerated from the dump, the six span blocks (keys 15, 16, 102, 103,
123, 124, all at 9.0667 px = 6.8 pt) carry **8 lines** between them, not 34.
WP-1.8 does not repeat the figure, so this is not a defect in the work under
test; it is a fourth count stated beside an enumeration that its enumeration
does not produce, in the same evidence file as the other two, and it belongs in
the record. It changes no compared population: the compared set is 149 blocks
and 968 lines either way.

## Should the corrections propagate into the plan?

**Yes, both.** The amendment revision 45 is holding is now independently
verified:

1. **WP-1.2.** Its headline 148/149 and 963/968 is the artifact-corrected count,
   not what its recorded harness reports (147/149, 962/968). Its narrative
   "Result improved from 147/149 to 148/149" for the styled-run fix is wrong:
   the fix exchanges block 39 for block 4 and leaves the total at 147. Both
   numbers are correct about different things and neither is quotable without
   saying which, exactly as WP-1.8's residual 1 puts it. The plan's line 1686,
   line 1979 (Known divergence table) and line 3127 (WP-1.2 RESULT) all quote
   148/149; they stay correct provided the whitespace-insensitive configuration
   travels with them (rule 9).
2. **WP-1.7.** Its delta table mixes normalizations and its Verify-clause
   sentence holds only whitespace-insensitively (967/968 under its own recorded
   harness). **Its interval and its +0.025000 pt recommendation are unaffected**,
   so nothing that feeds Phase 3 or WP-2.2a changes. `WP-1.7.verify.md`
   section 4 needs correcting too, since its stated reason for not blocking is
   falsified even though its conclusion is not.

Neither correction is live on the branch as code: WP-1.8 committed no source
file, and no consumer is blocked.

## Owns and landing

This verifier owns `meta/verification/evidence/WP-1.8.verify.md` and wrote
nothing else. `baseline.json` untouched (no comparator run). The WP's own diff,
checked above, is its evidence file and nothing else.
