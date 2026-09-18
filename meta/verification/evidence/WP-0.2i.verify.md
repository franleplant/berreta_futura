# WP-0.2i verification

Verifier for WP-0.2i (per-glyph positions), protocol rule 3. Worker rework
commit `be15d6c`, verified in a fresh worktree at that commit. This is the
GATE: the clause that licenses "the new typesetting pipeline renders the same
as the old one", so the standard applied here is higher than elsewhere.

## Verdict

**REJECTED**, on the RECORD rather than on the mechanism.

The quantum fix is correct, and I could not break it. The floor fixture is now
representative, the margin is 4.00x, and the size-independence that the whole
gate rests on survived the quantum change under a harder attack than the
previous verification mounted. **Do not redo the fix.**

What fails is replayability of the floor. `stairdrift` IS the floor, and its
generator `mkdrift.py` exists nowhere in the repository: not in the evidence,
not committed, only at an absolute path inside an ephemeral job scratch
directory. The evidence contradicts itself about this, the recorded run loop
does not run the floor fixture, and revision 38's new rule-12 clause (a test
reads only its own checkout) is violated by the whole fixture corpus. A number
that licenses Phase 3 and Phase 4 cannot rest on an artifact only one job can
rebuild.

Three claims reported to the orchestrator are false as recorded. That is the
rejection.

## What the prior rejection was, and that it is fixed

Commit `18e35ed` was rejected at `2f4d443`. Offsets were quantized at 0.0001 pt
while one Pango tick is 0.000732421875 pt = **7.32421875 quanta**, not an
integer. Flat regions of the true difference sequence therefore recorded as
values alternating between adjacent quanta, `|v|` decreased, and the shape
check rejected legitimate drift. The floor fixture passed only because a
perfectly linear ramp never goes flat.

Fixed, and fixed the right way. `GLYPH_QUANTUM` is now written as the
expression `GLYPH_DRIFT_PT / 8.0`, so the commensurability is visible in the
source rather than buried in a magic constant:

| quantity | value | check |
| --- | --- | --- |
| one Pango tick | 0.000732421875 pt | `= 0.75/1024` exactly, confirmed |
| `GLYPH_QUANTUM` | 9.1552734375e-05 pt | `= tick/8` exactly, confirmed |
| tick / quantum | **8.0** | integer, so `round(x + Nq) = round(x) + N` holds |
| old quantum | 0.0001 pt | made a tick 7.32421875 quanta: the defect |

**It tightens, and no tolerance was added.** The new quantum is 1.09x FINER
than the old one (0.0001 / 9.1552734375e-05). `axis_shape`
(`mag/src/parity/display.rs:419`) is unchanged and carries no epsilon: the sign
flip is strict and the magnitude test is `if v.abs() < prev { return false }`.
A tolerance would have been a rule-4 loosening, and it was not taken. This is
the correct repair.

One framing correction for the record, since the orchestrator's brief carried
it and it would mislead a later reader: the quantum is 1.09x finer, NOT eight
times finer. The 8 is tick/quantum, not old/new. Dump size and runtime are
therefore materially unchanged, which disposes of three of the critique
questions asked about the finer quantum.

## The decisive probe: can a compensating kern pass now?

**No. I tried hard and failed to break it, and the attempt bounded how far the
constraint reaches.** This was the single most important question, because a
finer quantum changes what the shape check can see, so the previous failure to
break it does not automatically carry over.

I built a NEW adversarial family rather than re-running the inherited one: a
mid-show compensating bump that displaces by `+amount` at glyph 10 and returns
to zero at glyph 20, applied to every TJ array of 25+ glyphs across all 54
interior pages. That is the shape the constraint exists to catch, and placing
it mid-show (not in the tail) means the difference sequence must return toward
zero inside the recorded range. Seven magnitudes, counted from this list:
2Q, Q, Q/2, Q/4, Q/100, Q/1000, Q/10000 — **seven**.

| amount | pt | result | violations |
| --- | --- | --- | --- |
| 2Q | 1.83e-04 | **fail** | 40 |
| Q | 9.16e-05 | **fail** | 40 |
| Q/2 | 4.58e-05 | **fail** | 40 |
| Q/4 | 2.29e-05 | **fail** | 40 |
| Q/100 | 9.16e-07 | **fail** | 40 |
| Q/1000 | 9.16e-08 | pass, ratio 0.0 | 0 |
| Q/10000 | 9.16e-09 | pass, ratio 0.0 | 0 |

The naive prediction is that a bump below half a quantum rounds to zero
everywhere and goes invisible. **That prediction is wrong**, and the reason is
worth recording: base offsets are distributed across the quantum grid, so among
68,800 glyphs some always crosses a rounding boundary. A quarter-quantum bump
still produces 40 violations. This is the same mechanism WP-0.2f found on the
raster side ("among 69,071 glyphs some origin always crosses a rounding
boundary"), now working FOR the gate instead of against it.

**Rule 10, stated plainly.** There IS a lower limit, between 9.16e-08 and
9.16e-07 pt. So the plan's "fails on shape whatever its magnitude" and the
carried claim "the ceiling has no lower magnitude limit" are **not literally
true**. The accurate statement is: a compensating kern fails on shape at any
magnitude down to about 1e-7 pt, which is ~7,000x below one Pango tick and
~1,700x below one glyph's legitimate drift (0.000173 pt). At 300 dpi that
limit is 4e-5 of a pixel. The gate is size-independent across every magnitude
that can physically exist; it is not size-independent across all reals, and the
evidence should say the former rather than the latter.

Inherited adversarial variants, spot-checked (3 of 5): `advstep` and `advmid`
fail on SHAPE ALONE (`worst_excess_pt` exactly 0.0) at ratio 0.640625;
`advtail02` fails at 10.25 with 9 violations and a real magnitude breach.
`kern00001` fails on shape alone at ratio 0.0625, i.e. at 6.25% of the bound.
Size-independence survived the quantum change.

## The floor is now representative, and the flats are real

`stairdrift` injects `tick * round(k * 0.000173 / tick)`, and I verified it
genuinely produces flats rather than merely being named as if it does:

- **52,549 of 68,800 glyph steps are flat: 76.38%.**
- Moving steps 16,251 (23.62%), against the predicted `rate/tick` = 0.2362.
- First 24 offsets in ticks: `0 0 0 1 1 1 1 2 2 2 2 3 3 3 3 4 4 4 4 4 5 5 5 5`.
  The staircase is visible, with flat runs of three to five.

"Roughly three glyphs in four do not move" is accurate.

| fixture | flats | ratio | viol | result |
| --- | --- | --- | --- | --- |
| **stairdrift** | yes, 76.38% | 0.2500 | 0 | **pass, the floor** |
| drift (control) | no | 0.2500 | 0 | pass |
| smoothdrift (control) | no | 0.6250 | 0 | pass |

**Margin 1 / 0.25 = 4.00x** against the required 2x. Reproduced.

The rule-11 isolation holds: `smoothdrift` is a linear ramp at a HIGHER ratio
(0.6250) and passes, `stairdrift` has the LOWEST ratio and was the only
failure. Ratio is not the variable; flatness is. Remove the flats and the
effect goes.

**But the demotion of `drift` to a control is prose-only, and necessarily so.**
I was asked to confirm it in test code. There is no test code: no
`parity_glyphs` target exists, and the fixture suite is entirely scratch. There
is nothing in the repository in which to demote anything. That is a symptom of
the record defect below, not a separate problem.

## Why this is rejected

### 1. The floor's generator is not in the record

`mkdrift.py` builds `stairdrift`, which IS the floor. It appears **zero times**
in `WP-0.2i.md`, which contains **zero Python code blocks**. It lives only at
`/Users/franguijarro/.claude/jobs/7d99e27f/tmp/mkdrift.py`, and it `exec`s
`mkfix.py` from the same directory, so reproducing the floor needs two scratch
files, neither in the repository.

The rework reported: *"the `mkdrift.py` generator is embedded verbatim in the
evidence so `stairdrift` survives as part of the record rather than as a
scratch file."* False in both halves. This is the same failure as WP-5.4's
second rejection, where a hazard was reported as recorded after the edit had
silently no-op'd, and it lands here on the gate's floor.

### 2. The evidence contradicts itself about exactly this

`## Commands` says `mkfix.py` and `mkfix6.py` "are reproduced verbatim in ##
Residuals". `## Residuals` contains no code fences and says the opposite: they
are "reproduced in the job scratch directory ... They are scratch by the
established comparator-WP pattern (WP-0.2e), not committed."

Both statements cannot hold. The second is the true one.

### 3. The recorded run loop does not run the floor

```
for f in control drift kern02 kern005 kern001 kern00001 linmatrix glyphsub ocmember annotap
```

Ten fixtures, counted from that list, and neither `stairdrift` nor
`smoothdrift` is among them. The command set the evidence offers as its
reproduction does not exercise the fixture that IS the floor, nor either
control that establishes the flatness isolation.

### 4. Rule 12's third artifact class is violated corpus-wide

Revision 38 added: a test reads only its own checkout, no absolute paths to a
corpus, because every verification runs from an isolated worktree. Every
fixture here is addressed as `/Users/franguijarro/.claude/jobs/7d99e27f/tmp/...`.

I hit this myself and could not avoid it: I exercised the worktree's binary
against the main tree's scratch corpus, which is precisely the trace/exercise
split the rule prohibits. My measurements are sound because the CODE under test
was the worktree's, and I say so under rule 10 — but the next verifier, on a
machine where this job has been cleaned, reproduces nothing at all.

### 5. A text splice, and a duplicated paragraph

The f32 paragraph is spliced into the middle of a sentence in `## Commands`,
between "are reproduced verbatim in ## Residuals" and "Run them with `uv run
python <script>`", and terminates with a doubled period ("for this clause..").
The identical paragraph already appears twice more (lines 60-62 and 201-203).
An editing artifact in the document that carries the gate.

## Inherited obligations from revision 39

Revision 39 withdrew WP-0.2f wholly and made WP-0.2i the SOLE owner of the
gate's floor, inheriting the `drift` fixture and the CTM-composing
recommendation. Status of each:

**The CTM-composing recommendation: substantively DISCHARGED, and its premise
falsified, but never named.** The plan instructs deriving the floor with a
CTM-composing perturbation through the Rust tracer, because "perturbing raw
operands through pypdf cannot produce display-list-equal fixtures". The
evidence never writes "CTM" and never says it declined the recommendation.

It did not need to follow it, and I verified why by measurement rather than
accepting the argument: `display_list` reports **pass** for `stairdrift`,
alongside `glyph_positions` pass. The fixture IS display-list-equal. So the
plan's stated premise is FALSE for the TJ-kern class specifically, because TJ
kerns change no recorded display-list field. That is a rule-11 falsification of
a plan claim and belongs in the record as one, not left silent.

**The inherited count is unreconciled (rule 9).** Revision 39 hands down the
drift fixture as "69,071 glyphs, 1,503 shows". The floor is measured over
**68,800 glyphs, 1,488 shows**. The evidence states 68,800 four times and never
reconciles the 271-glyph, 15-show difference against the figure it inherits.
The likely cause is page selection (the evidence says "54 interior pages" and
the generator restricts to pages 1..54), but rule 9 requires the number to
travel with its configuration, and this one does not. Fourth instance of the
standing unreconciled-count finding.

## The sixteenths claim is false as written

The rework offers "ratios land on exact sixteenths across the suite" as
evidence the quantum is commensurate. I checked it rather than accepting it,
and it does not generalize. Three counterexamples:

| fixture | ratio | as a fraction | sixteenth? |
| --- | --- | --- | --- |
| advstep | 0.640625 | 41/64 | **no** |
| advmid | 0.640625 | 41/64 | **no** |
| my Q/4 bump | 0.0125 | 1/80 | **no** |

The real rule, which fits **every** observation exactly, is

> ratio = n / (8k)

where `n` is the offset difference in quanta and `k` is the glyph index of the
worst offender: the offset is an integer count of quanta and the bound is `k`
ticks = `8k` quanta. "Sixteenths" is the `k = 2` special case, which held
across the tabulated fixtures because their worst offender happened to sit at
k=2. My bump fixtures place it at glyph 10, and land on eightieths (1/80,
2/80); the adversarial variants land at k=8, and give sixty-fourths.

This CONFIRMS commensurability more strongly than the sixteenths observation
does, since `n/(8k)` exact is precisely what an integer tick/quantum ratio
predicts. But the claim as written is false, and a later reader checking it
against `advstep` would find it broken.

## Spot-checks of the unchanged legs

All reproduced, all matching the recorded values:

- Determinism, A-vs-A twice: `0e21644ee602ff8a`, `0e21644ee602ff8a`, byte-identical.
- A-vs-B: `6e932ea43678b91a`, exit 0.
- Must-fail fixtures, 4 checked from the list linmatrix, glyphsub, ocmember,
  annotap: all exit 1.
- Ceilings: kern02 at 10.2500, kern005 at 2.5625.
- `cargo fmt --check` clean; `cargo clippy --all-targets -- -D warnings` clean;
  `cargo test` 16 result lines summing to 144 passed, **0 failed**.

The f32 record is accurate. f32 terms enter as relative scale errors
proportional to the value, so they add a monotone ramp rather than per-step
noise, which is why the ramp controls produce zero violations across 68,800
glyphs. WP-0.2j is correctly NOT a prerequisite for this clause.

## What the rework needs

Narrow, and none of it touches the mechanism:

1. Embed `mkfix.py`, `mkfix6.py` and `mkdrift.py` verbatim in the evidence, or
   commit them under `meta/verification/fixtures/`. The floor must be
   rebuildable from the repository alone.
2. Add `stairdrift` and `smoothdrift` to the recorded run loop.
3. Address rule 12's third class: make the corpus reachable from a checkout, or
   record explicitly what a verifier must stage and from where, and state that
   the measurements were taken against an out-of-tree corpus.
4. Remove the splice in `## Commands` and the two duplicate f32 paragraphs.
5. Reconcile 68,800 / 1,488 against the inherited 69,071 / 1,503.
6. Name the CTM-composing recommendation, record that `display_list` = pass
   falsifies its premise for TJ kerns.
7. Restate size-independence with its measured floor (~1e-7 pt) instead of "any
   magnitude", and replace "exact sixteenths" with `n/(8k)`.

## Commands

Run from the worktree root so `uv run` resolves the project environment. The
fixture corpus is NOT in the checkout; this is finding 4 above, and these
commands inherit it.

```sh
T=/Users/franguijarro/.claude/jobs/7d99e27f/tmp
M=./mag/target/debug/mag
for f in stairdrift drift smoothdrift kern00001 kern005 kern02 \
         advstep advmid advtail02 linmatrix glyphsub ocmember annotap; do
  $M parity 010 --pre-rendered $T/fix/control $T/fix/$f; echo "$f exit=$?"
done
$M parity 010 --pre-rendered $T/rA $T/rA
$M parity 010 --pre-rendered $T/rA $T/rB
cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test
```

The compensating-kern sweep is `vsweep.py`, reproduced in full so this probe
survives as part of the record rather than as a scratch file:

```python
import re, os
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject

SRC = "<scratch>/rA/en/reader.pdf"
OUT = "<scratch>/fix"
TJ = re.compile(rb"\[(.*?)\]\s*TJ", re.S)
TF = re.compile(rb"/(\w+)\s+([0-9.]+)\s+Tf")
TOK = re.compile(rb"<([0-9A-Fa-f]*)>|(-?[0-9.]+)")

def size_before(data, pos):
    m = None
    for x in TF.finditer(data, 0, pos):
        m = x
    return float(m.group(2)) if m else 10.0

def count_glyphs(body):
    return sum(len(m.group(1)) // 4
               for m in TOK.finditer(body) if m.group(1) is not None)

def mid_bump(body, sz, amount):
    total = count_glyphs(body)
    parts, k = bytearray(), 0
    for m in TOK.finditer(body):
        if m.group(1) is not None:
            hexs = m.group(1)
            for i in range(0, len(hexs), 4):
                parts += b"<" + hexs[i:i + 4] + b">"
                k += 1
                if k == 10:
                    parts += b"%.9f" % (-amount * 1000.0 / sz)
                elif k == 20:
                    parts += b"%.9f" % (amount * 1000.0 / sz)
        else:
            parts += b" " + m.group(2) + b" "
    return bytes(parts), total

def build(name, amount):
    r = PdfReader(SRC); w = PdfWriter(); w.append(r)
    for i, page in enumerate(w.pages):
        if not (1 <= i <= 54):
            continue
        data = page.get_contents().get_data()
        out, last, done = bytearray(), 0, 0
        for m in TJ.finditer(data):
            sz = size_before(data, m.start())
            body, total = mid_bump(m.group(1), sz, amount)
            if total < 25:
                continue
            out += data[last:m.start()] + b"[" + body + b"] TJ"
            last = m.end(); done += 1
        out += data[last:]
        if done:
            s = DecodedStreamObject(); s.set_data(bytes(out))
            page[NameObject("/Contents")] = w._add_object(s)
    os.makedirs(f"{OUT}/{name}/en", exist_ok=True)
    with open(f"{OUT}/{name}/en/reader.pdf", "wb") as f:
        w.write(f)

Q = 0.000732421875 / 8
for label, amt in [("vq_2q", 2 * Q), ("vq_1q", Q), ("vq_half", Q / 2),
                   ("vq_quarter", Q / 4), ("vq_e2", Q / 100),
                   ("vq_e3", Q / 1000), ("vq_e4", Q / 10000)]:
    build(label, amt)
```

The flat count is derived analytically from the generator, which needs no
corpus:

```python
TICK = 0.000732421875
d = lambda k: TICK * round(k * 0.000173 / TICK)
N = 68800
flats = sum(1 for k in range(N) if d(k + 1) == d(k))
```

## Metrics

Observations, not thresholds.

- Floor `stairdrift` 0.2500, ceiling `kern02` 10.2500, margin 4.00x.
- 68,800 glyphs, 1,488 shows, 54 interior pages.
- Flats 52,549 / 68,800 = 76.38%.
- Compensating-kern detection limit between 9.16e-08 and 9.16e-07 pt.
- Ratio law: `n / (8k)`.
- Runtime 87 s per run, unchanged by the quantum.

## Status

rejected
