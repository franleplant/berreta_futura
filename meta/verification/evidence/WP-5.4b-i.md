# WP-5.4b-i headline refusal fixture straddles its size boundary

## Base

Dispatched at `a537a24`, plan revision 39. MEASURED at `ba9c3ea`, plan revision
45, which is the commit every count in `## Metrics` carries. LANDED on
`f00e4c7`, plan revision 46, which arrived while this WP was verifying and
touches neither `mag/src/cover/` nor `mag/tests/cover_*`; `cover_modes` is
re-run green there and the suite total moves with WP-2.1's fixtures, which is
why the counts below name `ba9c3ea` rather than the landing commit.
The base moved eight commits during this WP, so the same perturbation reports
153 passing at `ba9c3ea` and 151 at the dispatch commit; the FLIPS are identical
at both, which is the part that is being claimed.
Follow-up to WP-5.4b (accepted, verify `03532ad`),
which fixed its own deck fixture and whose verifier then found the same weakness
in the headline refusal it had INHERITED. Revision 39 records the generalization
this WP is the first instance of: the straddle rule binds on inheritance, not
only on authoring.

Owns: `mag/tests/cover_*` and this file. `mag/src/cover/svg.rs` is NOT owned and
ends byte-identical to `36df6e8`; every perturbation below was applied to a
pristine copy taken from that commit and reverted in place, with the revert
asserted by content equality after each run.

## The defect

`headline_layout` in `mag/src/cover/svg.rs` guards TWO numbers: a line limit
(`lines.len() <= 3`) and a size floor (`size < 20.0`, walked down from 29.0 in
steps of 0.5 against a headline width of 302.0 pt). The inherited fixture was

```
Antidisestablishmentarianismxx Pneumonoultramicroscopic Floccinaucinihilipilification Supercalifragilisticexpialidocious
```

which needs size 10.5 to reach three lines. It therefore refuses under any floor
above 10.5, which is why WP-5.4b's verifier could drop the floor to 15.0, a 25%
loosening, and watch all eleven tests still pass.

Measured against the inherited fixture set, of the four ONE-STEP perturbations
the guard admits, exactly one flipped a test. Enumerated and counted from the
enumeration (four rows, one FAIL):

| one-step perturbation | inherited fixtures, `cargo test --test cover_modes` |
|---|---|
| size floor 20.0 -> 19.5 | 11 passed, 0 failed |
| size floor 20.0 -> 20.5 | 11 passed, 0 failed |
| line limit `<= 3` -> `<= 4` | 10 passed, 1 failed (`a_headline_that_cannot_fit_is_refused`) |
| line limit `<= 3` -> `<= 2` | 11 passed, 0 failed |

So the line limit DID have the same weakness in milder form, and it is the form
the brief predicted. It discriminated LOOSENING at one step and not TIGHTENING,
because there was no fitting headline fixture at all: the only headline the
suite laid out successfully is edition 010's own `The Speed Limit`, which wraps
to two lines (`THE SPEED` / `LIMIT`) at the opening size of 29.0 and so survives
a limit of 2 untouched. A refusal fixture alone can only ever pin one side.

## The pair

Both strings share an 83-character stem and differ in ONE GLYPH, the first
letter of the final word:

- fits: `Antidisestablishmentarianism Floccinaucinihilipilification Pneumonoultramicroscopic Is`
- refuses: `Antidisestablishmentarianism Floccinaucinihilipilification Pneumonoultramicroscopic As`

They read oddly. They are calibrated to the boundary, not chosen for realism:
the requirement is a pair at the finest granularity the guard can distinguish,
and a string picked to read well is exactly how the inherited fixture ended up
sitting 19 size steps, 9.5 pt, past the line it was supposed to pin.

The pair is tight for the reason it looks tight, which is worth stating because
a pair that flips through an unrelated code path would satisfy the rule and
prove nothing. Both strings take the same branch: no two-line split fits at any
size, so both fall to the greedy `_wrap`, and both wrap identically for the
first two lines. The ONLY difference is the third line's measured width against
the 302.0 pt limit, at `size=20.0` with `tracking=0.0` and
`horizontal_scale=100.0`:

| third line | 20.5 | 20.0 | 19.5 |
|---|---|---|---|
| `PNEUMONOULTRAMICROSCOPIC IS` | 307.8690 | 300.3600 | 292.8510 |
| `PNEUMONOULTRAMICROSCOPIC AS` | 314.6750 | 307.0000 | 299.3250 |

`A` is 6.64 pt wider than `I` at size 20.0, and 302.0 falls between the two rows
at exactly one size step. Line counts follow:

| headline | 21.0 | 20.5 | 20.0 | 19.5 | 19.0 | first size reaching 3 lines |
|---|---|---|---|---|---|---|
| `... Is` | 4 | 4 | 3 | 3 | 3 | 20.0 |
| `... As` | 4 | 4 | 4 | 3 | 3 | 19.5 |
| inherited | 4 | 4 | 4 | 4 | 4 | 10.5 |

The floor cannot be pinned more tightly than this. The loop only evaluates sizes
on the 0.5 grid, so any floor in `(19.5, 20.0]` behaves identically to 20.0; the
smallest floor moves that change behaviour at all are 19.5 and 20.5, and the
pair straddles both.

## Commands

Every block below was extracted from THIS FILE programmatically and executed in
a clean shell before submission, from the repository root. Quoted heredocs
(`<<'PY'`) so nothing inside needs escaping: WP-5.4b's own oracle failed to run
because a transcribed raw bytes literal put escaped quotes in literally.

The oracle is the REAL Python compiler. It is asked which strings it refuses
rather than reasoned at, and `_headline_layout` is called for the fitting side
so the chosen SIZE is read off Python rather than inferred from the fact that it
did not raise.

```
uv run python - <<'PY'
import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, "src")
from magazine.cover import CoverCompiler, CoverOverflowError

ART = Path("editions/010/art/rounds/2026-09-13T01-40-20/cover-wildcard-sign-punched-v3.png")
AUTHORS = ["FRANK RIETTA","ANTHROPIC","DARIO AMODEI","SANTI RUIZ","MICHAEL TRUELL",
           "WILSON LIN","DEEPSEEK-AI","JON LEE, CHAOMIN YU, BEN RIES"]
STEM = "Antidisestablishmentarianism Floccinaucinihilipilification Pneumonoultramicroscopic"
INHERITED = "Antidisestablishmentarianismxx Pneumonoultramicroscopic Floccinaucinihilipilification Supercalifragilisticexpialidocious"

def ed(headline):
    return SimpleNamespace(
        identifier="010", language="en", issue_number=10, place="Buenos Aires",
        publication_name="Berreta Futura", publication_date="2026-09-13", title=headline,
        cover={"layout": "framed", "headline": headline}, cover_art=ART,
        articles=[SimpleNamespace(author=a) for a in AUTHORS])

c = CoverCompiler(Path("."))
W = float(c.design["headline"]["width"])
print("headline width", W, "pt; sizes 29.0 down by 0.5; floor 20.0; line limit 3")

for label, headline in [("fits", STEM + " Is"), ("refuses", STEM + " As"), ("inherited", INHERITED)]:
    try:
        c._materialize_svg(ed(headline))
        lines, size = c._headline_layout(headline.upper().strip(), described_as=headline)
        print(f"{label}: FITS at size {size} in {len(lines)} lines {lines}")
    except CoverOverflowError as e:
        print(f"{label}: {e}")

def lines_at(up, size):
    words = up.split()
    best = None
    for split in range(1, len(words)):
        pair = (" ".join(words[:split]), " ".join(words[split:]))
        widths = tuple(c.display.measure(line, size=size) for line in pair)
        if max(widths) <= W:
            delta = abs(widths[0] - widths[1])
            if best is None or delta < best[0]:
                best = (delta, pair)
    if best is not None:
        return list(best[1])
    return c._wrap(up, c.display, size, W)

GRID = [round(29.0 - 0.5 * i, 1) for i in range(40)]
for label, headline in [("fits", STEM + " Is"), ("refuses", STEM + " As"), ("inherited", INHERITED)]:
    up = headline.upper().strip()
    counts = [len(lines_at(up, s)) for s in (21.0, 20.5, 20.0, 19.5, 19.0)]
    first = next((s for s in GRID if len(lines_at(up, s)) <= 3), None)
    print(f"{label}: lines at 21.0/20.5/20.0/19.5/19.0 = {counts}, first size reaching 3 lines = {first}")

for tail in ("PNEUMONOULTRAMICROSCOPIC IS", "PNEUMONOULTRAMICROSCOPIC AS"):
    print(tail, [round(c.display.measure(tail, size=s), 4) for s in (20.5, 20.0, 19.5)])
print("advance A minus I at 20.0:", round(c.display.measure("A", size=20.0) - c.display.measure("I", size=20.0), 4))
print("The Speed Limit at 29.0:", lines_at("THE SPEED LIMIT", 29.0))

from magazine.cover import PAGE_WIDTH
MAXW = PAGE_WIDTH - float(c.design["tab"]["width"]) - float(c.design["wordmark"]["right_reserve"])

def wordmark_first_fit(name):
    value = name.upper().strip()
    head, separator, tail = value.rpartition(" ")
    if not separator:
        head, tail = value, ""
    size = 42.0
    while size >= 2.0:
        head_width = c.bold.measure(head, size=size, tracking=-3.6, horizontal_scale=89.9)
        tail_width = c.bold.measure(tail, size=size, tracking=-3.6, horizontal_scale=105.1) if tail else 0
        if max(head_width, size * (97 / 42) + tail_width + (13 if tail else 0)) <= MAXW:
            return size
        size -= 0.5
    return None

def title_first_fit(text, max_size=19.0, width=190):
    size = max_size
    while size >= 2.0:
        if c.display.measure(text.upper(), size=size, tracking=0.2) <= width:
            return size
        size -= 0.5
    return None

print("wordmark max width", round(MAXW, 6), "floor 25.0 step 0.5 from 42.0")
w = wordmark_first_fit("Antidisestablishmentarianism Floccinaucinihilipilification")
print("  inherited wordmark fixture first fits at", w, "slack", round((25.0 - w) / 0.5), "steps")
t = title_first_fit("The Speed Limit And Its Discontents")
print("title floor 12.0 step 0.5 from 19.0 at width 190")
print("  inherited title fixture first fits at", t, "slack", round((12.0 - t) / 0.5), "steps")
PY
```

Baseline, then the four one-step perturbations against both fixture sets. The
driver takes `svg.rs` from `36df6e8` (the byte-identity anchor) and the
inherited tests from `a537a24` (this WP's base), so it reproduces both columns
of the table at any later commit, and it restores by content equality rather
than by `git checkout`.

```
cargo test --manifest-path mag/Cargo.toml --no-fail-fast
cargo fmt --manifest-path mag/Cargo.toml --check
cargo clippy --manifest-path mag/Cargo.toml --all-targets -- -D warnings
```

```
uv run python - <<'PY'
import subprocess
from pathlib import Path

ROOT = Path(".").resolve()
SVG = ROOT / "mag/src/cover/svg.rs"
TESTS = ROOT / "mag/tests/cover_modes.rs"

def blob(ref, path):
    out = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return out.stdout

PRISTINE = blob("36df6e8", "mag/src/cover/svg.rs")
INHERITED = blob("a537a24", "mag/tests/cover_modes.rs")
MINE = TESTS.read_text()
assert SVG.read_text() == PRISTINE, "svg.rs already diverges from 36df6e8"

LOOP = "if lines.len() <= 3 || size < 20.0 {"
BAIL = "if size < 20.0 {"
CASES = [
    ("size floor 20.0 -> 19.5", [(LOOP, LOOP.replace("20.0", "19.5")), (BAIL, BAIL.replace("20.0", "19.5"))]),
    ("size floor 20.0 -> 20.5", [(LOOP, LOOP.replace("20.0", "20.5")), (BAIL, BAIL.replace("20.0", "20.5"))]),
    ("line limit <= 3 -> <= 4", [(LOOP, LOOP.replace("<= 3", "<= 4"))]),
    ("line limit <= 3 -> <= 2", [(LOOP, LOOP.replace("<= 3", "<= 2"))]),
]

def run(args):
    out = subprocess.run(["cargo", "test", "--manifest-path", "mag/Cargo.toml", "--no-fail-fast"] + args,
                         cwd=ROOT, capture_output=True, text=True)
    text = out.stdout + out.stderr
    results = [l.strip() for l in text.splitlines() if l.startswith("test result")]
    failing = [l.split()[1] for l in text.splitlines() if l.startswith("test ") and l.rstrip().endswith("FAILED")]
    passed = sum(int(l.split("result: ")[1].split()[1]) for l in results)
    return len(results), passed, failing

def sweep(label, args):
    for case, edits in CASES:
        text = PRISTINE
        for old, new in edits:
            assert text.count(old) == 1, (case, old, text.count(old))
            text = text.replace(old, new)
        SVG.write_text(text)
        try:
            binaries, passed, failing = run(args)
        finally:
            SVG.write_text(PRISTINE)
            assert SVG.read_text() == PRISTINE
        print(f"{label} | {case}: binaries={binaries} passed={passed} failing={failing or ['(none)']}")

TESTS.write_text(INHERITED)
try:
    sweep("inherited", ["--test", "cover_modes"])
finally:
    TESTS.write_text(MINE)
    assert TESTS.read_text() == MINE
sweep("tightened", [])
print("svg.rs identical to 36df6e8:", SVG.read_text() == PRISTINE)
PY
```

## Tool versions

python 3.12.11 via `uv run` (Unicode 15.0.0; the system `python3` is 3.9.6 and
must not be used), rustc 1.96.0, resvg/usvg 0.47.0 and tiny-skia 0.12.0.

## Metrics

Baseline at `ba9c3ea`, tightened fixtures, `cargo test --no-fail-fast`: 17
binaries, 154 passed, 0 failed. `cover_modes` holds 12 of those, 11 of its own
plus one inlined `metrics::exif_tests` case, against 11 before this WP. At the
dispatch commit `a537a24` the same baseline is 152, the difference being two
`critic_text` cases added by WP-5.3b-i in between.

Discrimination, tightened fixtures, each perturbation reverted in place and the
revert asserted, each run over the WHOLE suite rather than one binary so that
"only the intended test" is a suite-wide claim. Enumerated and counted from the
enumeration: four rows, four flips.

| one-step perturbation | binaries | passed of 154 | failing |
|---|---|---|---|
| size floor 20.0 -> 19.5 | 17 | 153 | `a_headline_that_cannot_fit_is_refused` |
| size floor 20.0 -> 20.5 | 17 | 153 | `a_headline_of_three_lines_at_the_size_floor_still_fits` |
| line limit `<= 3` -> `<= 4` | 17 | 152 | both headline tests |
| line limit `<= 3` -> `<= 2` | 17 | 153 | `a_headline_of_three_lines_at_the_size_floor_still_fits` |

Both numbers are now pinned from both sides, each by a one-step move, and no
perturbation disturbs any test outside the two headline ones.

The `<= 4` row fails TWO tests and the reason is recorded rather than smoothed
over: with the limit at 4 the fitting fixture lays out four lines and panics at
`svg.rs:537`, `index out of bounds: the len is 3 but the index is 3`, because
the headline colour cycle `[ink, violet, ink]` has exactly three entries. Both
failures are genuine detections of that one perturbation, not collateral from an
unrelated test, and the panic is a second, independent reason the limit of 3 is
load-bearing. Python has the same three-colour cycle and the same latent
behaviour; it is not this WP's to change.

## Verdicts

`cargo test --no-fail-fast`: 17 binaries green, 154 tests. `cargo fmt --check`
and `cargo clippy --all-targets -- -D warnings` clean. `tools/nocomments.py`
green via the `nocomments` test.

Revision 43's rule 12 clause, hermeticity as a property of the whole replay
path, is satisfied by construction and by demonstration. The three blocks carry
no absolute path: they reach the tree as `src`, `mag/Cargo.toml`, `Path(".")`
and `editions/010/...`, and both git objects they read are named by commit
(`36df6e8`, `a537a24`) rather than by a file outside the checkout. They were
then EXTRACTED AGAIN and replayed in a SECOND worktree at `ba9c3ea`, which is
not the directory this WP was developed in, and all three exited 0 with the same
four flips. The three fenced blocks hash to
`e4daec69864037c715aaf7aeb24b35bd3aa56cb4999a7b28f7ebb0f1052ad059`, unchanged
between the run and this submission; the prose around them was edited after, the
commands were not.

`git status` clean apart from the two owned paths; `mag/src/cover/svg.rs` hashes
identical to `36df6e8` after every perturbation.

## Residuals

This WP changed FIXTURES only. It does not touch `headline_layout`, so the port
itself is neither more nor less proven than WP-5.4b left it; what changed is
that the two numbers in it are now pinned rather than merely accompanied by a
correct message.

**Two more inherited fixtures in this same file are loose at one step, and
this WP measured them rather than fixing them.** Revision 39 asks a successor
to SWEEP what it inherits, so the sweep was extended past the headline to every
numeric guard `cover_modes.rs` covers. The deck limit is genuinely tight:
WP-5.4b pinned it with fixtures at six and five wrapped lines, one step apart.
The other two are not, and WP-5.4b's own perturbations of them were not
one-step moves, which is why they read as verified:

| guard | floor | step | fixture first fits at | slack | WP-5.4b's perturbation | smallest flipping move |
|---|---|---|---|---|---|---|
| wordmark | 25.0 | 0.5 | 21.0 | 8 steps | 25.0 to 20.0, 10 steps | 25.0 to 21.0 |
| title | 12.0 | 0.5 | 10.5 | 3 steps | 12.0 to 8.0, 8 steps | 12.0 to 10.5 |

Both are the same defect as the headline in milder form: the fixture refuses
under any floor above the size at which it first fits, so the perturbation that
flipped it proved the guard exists and not where it sits. Neither is fixed here.
They are outside what this WP was dispatched to change, and they overturn a
verification another WP already had ACCEPTED, which is a finding for the plan to
dispatch rather than a fixture edit to slip in. The numbers above are what a
successor needs; the method is the one in `## The pair`.

The three MESSAGE-ONLY refusals in `svg.rs` (unknown layout, missing art, no
glyph) have no number to get wrong and are correctly message-only.

The three-colour cycle caps a fitting headline at three lines independently of
the guard. Nothing asserts that coupling; it surfaced here as a panic under
perturbation. Recorded, not fixed, because `mag/src/cover/svg.rs` is outside
this WP's Owns and the coupling is faithful to Python.

## What is and is not proven

PROVEN: the headline size floor is 20.0 and not merely "some floor", and the
headline line limit is 3 and not merely "some limit", each shown by a fixture
pair one step apart in the input and by a one-step move of the threshold in both
directions flipping exactly the expected test, suite-wide.

NOT PROVEN and not claimed: the wordmark floor of 25.0 and the title floor of
12.0, whose fixtures this WP measured as loose by 8 and 3 steps and did not fix
(see `## Residuals`); anything about the headline beyond those two
numbers; the PDF writer, the back cover, or `design.toml` loading. The
refusal MESSAGE was already proven by WP-5.4b and is re-asserted here against a
message Python produced, not re-derived.

No row in this WP compares an empty set against an empty set or a constant
against itself; every row has a FAIL and a pass on the same perturbation.

## Status

done
