# WP-5.4b-ii the wordmark and title refusal fixtures straddle their size floors

## Base

Dispatched at `6366eb3`, plan revision 47. The dispatching session was killed
by a rate limit and resumed against a moved branch, so the work was REBASED
onto `0978ebb`, plan revision 51, which is the commit every count in
`## Metrics` carries and the commit the oracle and sweep below were run at.
LANDED directly on top of `aa8bdac`, plan revision 61, which is this commit's
parent. The gate below was run at `6d18c77`, one commit earlier: the swap was
refused a second time, `aa8bdac` is a plan revision touching no path this WP
reads or writes, and rather than claim a run it did not do, this file names the
commit each run was made at and the parent separately. The suite
total moves as other WPs land, 183 at the measurement commit against 223 at
the landing base, which is why the two are named separately and why no bare
total appears anywhere in this file.

Between dispatch and measurement the branch took `20adcfb` (WP-5.3b-ii),
`9acc797` (a verification), `3b57c36` (a helper lift into
`mag/src/model/shared.rs`) and plan revisions 49, 50 and 51. None touches
`mag/src/cover/**` or `mag/tests/cover_*`. Between measurement and landing it
took twenty more, of which exactly one, `a911ff1` (WP-5.4c's cover PDF writer),
DOES touch `mag/src/cover/` and `mag/tests/cover_*`;
`mag/tests/cover_modes.rs` is byte-unchanged across the whole range, so every
rebase carried cleanly.

**The landing took two attempts and the first was REFUSED BY THE
COMPARE-AND-SWAP working as designed**, which is worth recording because
revision 50 added that rule after the opposite outcome. `B` was captured as
`a911ff1` BEFORE rebasing and passed as the expected-old; revision 58 landed in
between, so the swap was refused rather than silently succeeding against a
stale parent. The response was to rebase again onto the NEW tip, never to
re-read the tip and retry, which is the move revision 50 identifies as the
cause of the defect it was written for. The second rebase crossed WP-2.2b and
WP-0.2k's acceptance, so the gate was RE-RUN rather than assumed, and
`## Verdicts` names all three runs with their commits.

This WP was killed by a session rate limit TWICE mid-work, once mid-sweep. Both
times the first act on resuming was to hash `mag/src/cover/svg.rs` against
`36df6e8`, before reading anything else, because a perturbation left in place
is the one way a fixture-only WP can do damage. It matched both times, and it
matches at submission.

Follow-up to WP-5.4b-i (landed `25184fb`), which tightened the HEADLINE pair
and, sweeping what it had inherited per revision 39, measured these two as
loose and declined to fix them. Revision 49 states the finding this WP
discharges: **a multi-step perturbation is not evidence of tightness, only of
non-inertness.**

Owns: `mag/tests/cover_*` and this file. `mag/src/cover/svg.rs` is NOT owned
and ends byte-identical to `36df6e8`, git blob
`d2275caf9513df033dc47a470eebac3d99a46719`, sha256
`7d595c94d3d461591a424052a2e62b35052723085828d7f00c8680e664bee935`. Every
perturbation below was applied to a pristine copy taken from that commit and
reverted in place, with the revert asserted by content equality after each
run. The hash was re-checked first thing on resuming, because this session was
killed mid-work and WP-5.4b-i had a mid-sweep kill leave the file perturbed.

## The defect

Two numeric guards in `mag/src/cover/svg.rs`:

- `wordmark_size`, a size floor of `25.0` walked down from `42.0` in steps of
  `0.5`, refusing when `max(head leg, tail leg) > 320.527559` at every size on
  the grid. The tail leg is `size * (97/42) + tail_width + 13`; the head leg is
  the head measured at `horizontal_scale` 89.9.
- `fit_display_line`, a size floor of `12.0` walked down from the layout's
  `title_size` in steps of `0.5`, refusing when the measured width exceeds the
  caller's limit at every size on the grid (`190.0` pt for `honored_plate`).

The inherited fixtures refuse under any floor far above the one they are meant
to pin, so the perturbation that flipped them proved that a guard EXISTS and
not WHERE IT SITS:

| guard | floor | step | inherited fixture first fits at | slack | WP-5.4b's perturbation | smallest flipping move |
|---|---|---|---|---|---|---|
| wordmark | 25.0 | 0.5 | 21.0 | 8 steps | 25.0 to 20.0, 10 steps | 25.0 to 21.0 |
| title | 12.0 | 0.5 | 10.5 | 3 steps | 12.0 to 8.0, 8 steps | 12.0 to 10.5 |

Every figure in that table is re-derived at the point of citation (rule 9)
rather than carried from the brief or from WP-5.4b-i's prose. The first-fit
sizes come from the oracle block, which prints `inherited first fit 21.0` for
the wordmark and `inherited first fit 10.5` for the title at the same grid and
the same limits the Rust walks. The perturbations attributed to WP-5.4b come
from WP-5.4b's OWN artifact, `meta/verification/evidence/WP-5.4b.md` lines 220
and 221, which read `wordmark floor 25.0 to 20.0` and `title floor 12.0 to
8.0`. The step counts are arithmetic on those: 8 = (25.0-21.0)/0.5,
10 = (25.0-20.0)/0.5, 3 = (12.0-10.5)/0.5, 8 = (12.0-8.0)/0.5.

Measured, that is not a claim about a hypothetical looseness. Against the
INHERITED fixtures all FOUR one-step moves of these two floors leave the whole
suite green, while the headline's four, tightened by WP-5.4b-i, all flip. The
`inherited` rows in `## Metrics` are that measurement.

## The pairs

Both pairs share a stem and differ in ONE GLYPH, the final letter, `l` against
`s`. Both are calibrated to the boundary rather than chosen for realism: a
string picked to read well is exactly how the inherited fixtures ended up 8 and
3 steps past the line they were supposed to pin. The refusing side of each pair
happens to read as ordinary English and the fitting side does not, which is the
shape to expect and not a reason to move either one.

**Wordmark**, stem `Berreta Incomprehensibilitie` (28 characters):

- fits: `Berreta Incomprehensibilitiel`, first fits at 25.0
- refuses: `Berreta Incomprehensibilities`, first fits at 24.5

**Title**, stem `The Speed Limit And Its Apostle` (31 characters):

- fits: `The Speed Limit And Its Apostlel`, first fits at 12.0
- refuses: `The Speed Limit And Its Apostles`, first fits at 11.5

The pairs are tight for the reason they look tight, which is worth stating
because a pair that flipped through an unrelated code path would satisfy the
rule and prove nothing. Each pair takes ONE code path and differs in ONE
measured quantity.

The wordmark guard takes the `max` of two legs, and which leg binds is part of
the claim. For both strings of the pair the head leg is 84.0566 pt at size 25.0
against a limit of 320.527559, so the TAIL leg binds, exactly as it did for the
inherited fixture (397.5778 pt of tail against 311.0875 pt of head). The
tightening does not move the guard onto a different leg:

| wordmark | 25.5 tail | 25.0 tail | 24.5 tail | first fit |
|---|---|---|---|---|
| `...itiel` | 327.4452 | 319.7958 | 312.1465 | 25.0 |
| `...ities` | 329.8400 | 322.1437 | 314.4473 | 24.5 |
| inherited | 407.3882 | 397.5778 | 387.7675 | 21.0 |

The limit of 320.527559 falls between the two rows at exactly one size step:
0.7318 pt of headroom on the fitting side and 1.6161 pt of overhang on the
refusing side, the whole separation being the 2.3478 pt by which `S` is wider
than `L` at size 25.0 and `horizontal_scale` 105.1.

| title | 12.5 | 12.0 | 11.5 | first fit |
|---|---|---|---|---|
| `...Apostlel` | 197.3750 | 189.7280 | 182.0810 | 12.0 |
| `...Apostles` | 198.2000 | 190.5200 | 182.8400 | 11.5 |
| inherited | 219.0000 | 210.5120 | 202.0240 | 10.5 |

The limit of 190.0 falls between the two rows at exactly one size step: 0.2720
pt under on the fitting side and 0.5200 pt over on the refusing side, the whole
separation being the 0.7920 pt by which `S` is wider than `L` at size 12.0.

Neither floor can be pinned more tightly than this. Both loops evaluate sizes
only on the 0.5 grid, so any wordmark floor in `(24.5, 25.0]` behaves
identically to 25.0 and any title floor in `(11.5, 12.0]` identically to 12.0.
The smallest moves that change behaviour at all are 24.5 and 25.5, and 11.5 and
12.5, and each pair straddles both.

### Rule 10c: neither side of a pair is a value the wrong branch also produces

Rule 10c landed while this WP was verifying: a straddle pair must assert that
its two expected values DIFFER FROM EACH OTHER and that neither coincides with
the refusal or fallback path, because a pair both of whose sides can come from
one wrong branch is decoration. Applied to all four pairs in
`cover_modes.rs`, the two this WP authored and the two it inherited, with the
boundary each check establishes stated rather than only the finding:

| pair | fitting side expects | refusing side expects | can one branch produce both? |
|---|---|---|---|
| wordmark (this WP) | `Ok(svg)` | `Err("Publication wordmark cannot fit: Berreta Incomprehensibilities")` | no |
| title (this WP) | `Ok(svg)` | `Err("Cover title cannot fit on one line: THE SPEED LIMIT AND ITS APOSTLES")` | no |
| headline (inherited, `25184fb`) | `Ok(svg)` | `Err("Cover headline cannot fit: ...")` | no |
| deck (inherited, `25184fb`) | `Ok(svg)` | `Err("Cover deck cannot fit: ...")` | no |

The boundary checked, in three parts, because "no" on its own is an assertion
rather than a check:

1. **The two expected values differ categorically**, `Ok` against `Err`. The
   `accepted` helper panics on `Err` and the `refusal` helper panics on `Ok`,
   so neither test can be satisfied by the other side's outcome. This is the
   structural difference rule 10c asks for and it is stronger than a pair of
   distinct strings, which could still both be reachable from one branch.
2. **There is NO FALLBACK BRANCH to coincide with.** Read in the source rather
   than assumed: `wordmark_size` (`svg.rs:187`) and `fit_display_line`
   (`svg.rs:346`) each either RETURN a size computed from the loop or `bail!`.
   Neither has a default-value arm, a `unwrap_or`, or a catch-all that could
   emit a plausible value on the wrong path. The failure mode rule 10c
   describes, an expected value that the fallback also produces, has no site
   here to occur at.
3. **Each refusal message is unique to its own bail site and embeds the
   fixture's own string**, so it cannot be produced by a different refusal.
   `Publication wordmark cannot fit: {publication_name}` is emitted at exactly
   one place, and the fixture name appears in the expectation, so a refusal
   from the deck, headline, title, missing-art or unknown-layout guard would
   produce a different string and fail the assertion.

**And the empirical check, which is stronger than all three.** A pair whose
sides a single wrong branch could both satisfy would NOT flip when the
threshold moves one step, because the branch would keep producing the same
outcome. Every pair here flips in BOTH directions at one step, shown in
`## Metrics`: moving a floor up fails the fitting side and leaves the refusing
side passing, moving it down does the reverse. That is the discrimination rule
10c is trying to secure, measured rather than argued.

The one thing this does NOT establish is recorded under NOT PROVEN rather than
folded into the "no" above: `Ok` pins that the guard did not refuse, not WHICH
SIZE it chose.

Four tests are COMMITTED, two per guard, so that a future change to either
floor cannot leave the suite green. A demonstration that exists only in a
perturbation run is not a guard; the pair in the tree is:

- `a_publication_wordmark_at_the_size_floor_still_fits`
- `a_publication_wordmark_that_cannot_fit_is_refused`
- `a_title_of_one_line_at_the_size_floor_still_fits`
- `a_title_that_cannot_fit_on_one_line_is_refused`

`cover_modes.rs` also gains a `compile` helper that `refusal` and a new
`accepted` both call, and a `deck_of` helper for the two deck fixtures. Counted
from the enumeration rather than asserted: `grep -c "let mut builder = Builder
{"` gives 6 before and 4 after, so the refactor removes two hand-rolled copies
of the builder setup while serving two NEW fitting tests that would otherwise
have added two more. The refactor changes no input to any test. It is shown to
be behaviour-preserving by the `tightened` sweep rows for the headline, which
reproduce WP-5.4b-i's recorded flips test for test, and by the deck and raster
tests passing unchanged throughout.

## Commands

All FOUR blocks below were extracted from THIS FILE programmatically and
executed in a clean shell before submission, from the repository root. Quoted
heredocs (`<<'PY'`) so nothing inside needs escaping. No block carries an
absolute path or reads anything gitignored: they reach the tree as `src`,
`mag/Cargo.toml`, `Path(".")` and `editions/010/...`, all tracked, and the
three git objects they read are named by commit (`36df6e8`, `25184fb`) rather
than by a file outside the checkout.

The oracle is the REAL Python compiler. It is ASKED which inputs it refuses
rather than reasoned at, and its last section drives `_materialize_svg` end to
end on all four fixture strings so the accept/refuse verdict comes from Python
rather than from arithmetic reproduced beside it. The caption's scope words are
worth checking against the output on replay (revision 49): "both pairs" means
the four strings named in `## The pairs` and the two inherited strings they
replace, and nothing wider.

```
uv run python - <<'PY'
import sys
from pathlib import Path

sys.path.insert(0, "src")
from magazine.cover import CoverCompiler, PAGE_WIDTH

c = CoverCompiler(Path("."))
BOLD, DISPLAY = c.bold, c.display
MAXW = PAGE_WIDTH - float(c.design["tab"]["width"]) - float(c.design["wordmark"]["right_reserve"])
TITLE_WIDTH = 190.0
WORDMARK_GRID = [round(42.0 - 0.5 * i, 1) for i in range(81)]
TITLE_GRID = [round(19.0 - 0.5 * i, 1) for i in range(35)]
WORDMARK_STEM = "Berreta Incomprehensibilitie"
TITLE_STEM = "The Speed Limit And Its Apostle"

def wordmark_legs(name, size):
    value = name.upper().strip()
    head, separator, tail = value.rpartition(" ")
    if not separator:
        head, tail = value, ""
    head_width = BOLD.measure(head, size=size, tracking=-3.6, horizontal_scale=89.9)
    tail_width = BOLD.measure(tail, size=size, tracking=-3.6, horizontal_scale=105.1) if tail else 0
    return head_width, size * (97 / 42) + tail_width + (13 if tail else 0)

def wordmark_first_fit(name):
    return next((s for s in WORDMARK_GRID if max(wordmark_legs(name, s)) <= MAXW), None)

def title_width(text, size):
    return DISPLAY.measure(text.upper().strip(), size=size, tracking=0.2)

def title_first_fit(text):
    return next((s for s in TITLE_GRID if title_width(text, s) <= TITLE_WIDTH), None)

print("python", sys.version.split()[0])
print(f"wordmark max width {MAXW!r} pt; sizes 42.0 down by 0.5; floor 25.0")
print(f"title width {TITLE_WIDTH} pt tracking 0.2; sizes 19.0 down by 0.5; floor 12.0")

print("\nwordmark: max(head leg, tail leg) <= max width")
for label, name in [
    ("fits", f"{WORDMARK_STEM}l"),
    ("refuses", f"{WORDMARK_STEM}s"),
    ("inherited", "Antidisestablishmentarianism Floccinaucinihilipilification"),
]:
    legs = {s: wordmark_legs(name, s) for s in (25.5, 25.0, 24.5)}
    cells = " ".join(f"{s}: head {legs[s][0]:.4f} tail {legs[s][1]:.4f}" for s in (25.5, 25.0, 24.5))
    print(f"  {label:9s} first fit {wordmark_first_fit(name)} | {cells} | {name!r}")

print("\ntitle: measured width <= 190.0")
for label, text in [
    ("fits", f"{TITLE_STEM}l"),
    ("refuses", f"{TITLE_STEM}s"),
    ("inherited", "The Speed Limit And Its Discontents"),
]:
    cells = " ".join(f"{s}: {title_width(text, s):.4f}" for s in (12.5, 12.0, 11.5))
    print(f"  {label:9s} first fit {title_first_fit(text)} | {cells} | {text!r}")

print("\nglyph swap at the boundary, one step of the size grid apart")
print(f"  wordmark tail leg at 25.0, 'L' minus 'S': "
      f"{wordmark_legs(f'{WORDMARK_STEM}s', 25.0)[1] - wordmark_legs(f'{WORDMARK_STEM}l', 25.0)[1]:.4f} pt")
print(f"  title width at 12.0, 'S' minus 'L': "
      f"{title_width(f'{TITLE_STEM}s', 12.0) - title_width(f'{TITLE_STEM}l', 12.0):.4f} pt")

print("\nPython refuses exactly the strings the Rust fixtures expect")
from types import SimpleNamespace
from magazine.cover import CoverOverflowError

ART = Path("editions/010/art/rounds/2026-09-13T01-40-20/cover-wildcard-sign-punched-v3.png")
AUTHORS = ["FRANK RIETTA", "ANTHROPIC", "DARIO AMODEI", "SANTI RUIZ", "MICHAEL TRUELL",
           "WILSON LIN", "DEEPSEEK-AI", "JON LEE, CHAOMIN YU, BEN RIES"]

def edition(layout, name, headline):
    return SimpleNamespace(
        identifier="010", language="en", issue_number=10, place="Buenos Aires",
        publication_name=name, publication_date="2026-09-13", title=headline,
        cover={"layout": layout, "headline": headline}, cover_art=ART,
        articles=[SimpleNamespace(author=a) for a in AUTHORS])

for layout, name, headline in [
    ("framed", f"{WORDMARK_STEM}l", "The Speed Limit"),
    ("framed", f"{WORDMARK_STEM}s", "The Speed Limit"),
    ("honored_plate", "Berreta Futura", f"{TITLE_STEM}l"),
    ("honored_plate", "Berreta Futura", f"{TITLE_STEM}s"),
]:
    try:
        c._materialize_svg(edition(layout, name, headline))
        print(f"  {layout:14s} accepted {name!r} / {headline!r}")
    except CoverOverflowError as error:
        print(f"  {layout:14s} refused: {error}")
PY
```

Repo gates:

```
cargo test --manifest-path mag/Cargo.toml --no-fail-fast
cargo fmt --manifest-path mag/Cargo.toml --check
cargo clippy --manifest-path mag/Cargo.toml --all-targets -- -D warnings
```

Baseline, then EIGHT one-step perturbations against BOTH fixture sets: this
WP's four, plus WP-5.4b-i's four headline moves re-run to show the refactor
preserved them. The driver takes `svg.rs` from `36df6e8` (the byte-identity
anchor) and the inherited tests from `25184fb` (WP-5.4b-i's landing commit), so
it reproduces both columns at any later commit, and it restores by content
equality rather than by `git checkout`. Every run is over the WHOLE suite, not
one binary, so "only the intended tests" is a suite-wide claim.

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
INHERITED = blob("25184fb", "mag/tests/cover_modes.rs")
MINE = TESTS.read_text()
assert SVG.read_text() == PRISTINE, "svg.rs already diverges from 36df6e8"

WM = "if size < 25.0 {"
TL_LOOP = "while size >= 12.0 && self.fonts.display.measure(text, size, 0.2, 100.0)? > width {"
TL_BAIL = "if size < 12.0 {"
HL_LOOP = "if lines.len() <= 3 || size < 20.0 {"
HL_BAIL = "if size < 20.0 {"

def tl(v):
    return [(TL_LOOP, TL_LOOP.replace("12.0", v)), (TL_BAIL, TL_BAIL.replace("12.0", v))]

CASES = [
    ("wordmark floor 25.0 -> 25.5", [(WM, WM.replace("25.0", "25.5"))]),
    ("wordmark floor 25.0 -> 24.5", [(WM, WM.replace("25.0", "24.5"))]),
    ("title floor 12.0 -> 12.5", tl("12.5")),
    ("title floor 12.0 -> 11.5", tl("11.5")),
    ("headline size floor 20.0 -> 20.5", [(HL_LOOP, HL_LOOP.replace("20.0", "20.5")), (HL_BAIL, HL_BAIL.replace("20.0", "20.5"))]),
    ("headline size floor 20.0 -> 19.5", [(HL_LOOP, HL_LOOP.replace("20.0", "19.5")), (HL_BAIL, HL_BAIL.replace("20.0", "19.5"))]),
    ("headline line limit <= 3 -> <= 4", [(HL_LOOP, HL_LOOP.replace("<= 3", "<= 4"))]),
    ("headline line limit <= 3 -> <= 2", [(HL_LOOP, HL_LOOP.replace("<= 3", "<= 2"))]),
]

def run():
    out = subprocess.run(["cargo", "test", "--manifest-path", "mag/Cargo.toml", "--no-fail-fast"],
                         cwd=ROOT, capture_output=True, text=True)
    text = out.stdout + out.stderr
    results = [l for l in text.splitlines() if l.startswith("test result")]
    failing = sorted(l.split()[1] for l in text.splitlines() if l.startswith("test ") and l.rstrip().endswith("FAILED"))
    passed = sum(int(l.split("result: ")[1].split()[1]) for l in results)
    return len(results), passed, failing

def sweep(label):
    for case, edits in CASES:
        text = PRISTINE
        for old, new in edits:
            assert text.count(old) == 1, (case, old, text.count(old))
            text = text.replace(old, new)
        SVG.write_text(text)
        try:
            binaries, passed, failing = run()
        finally:
            SVG.write_text(PRISTINE)
            assert SVG.read_text() == PRISTINE
        print(f"{label} | {case}: binaries={binaries} passed={passed} failing={failing or ['(none)']}", flush=True)

TESTS.write_text(INHERITED)
try:
    print("baseline inherited:", run(), flush=True)
    sweep("inherited")
finally:
    TESTS.write_text(MINE)
    assert TESTS.read_text() == MINE
print("baseline tightened:", run(), flush=True)
sweep("tightened")
print("svg.rs identical to 36df6e8:", SVG.read_text() == PRISTINE)
PY
```

The latent panic under `line limit <= 3 -> <= 4`, MEASURED rather than quoted
from WP-5.4b-i, because rule 11 makes another WP's mechanism a hypothesis until
this one reproduces it. Scope words: this block runs ONE perturbation and ONE
test, and prints only lines matching `panicked`, `index out of bounds` or
`svg.rs:`; it says nothing about any other test or perturbation.

```
uv run python - <<'PY'
import subprocess
from pathlib import Path

ROOT = Path(".").resolve()
SVG = ROOT / "mag/src/cover/svg.rs"
PRISTINE = subprocess.run(["git", "show", "36df6e8:mag/src/cover/svg.rs"],
                          cwd=ROOT, capture_output=True, text=True).stdout
assert SVG.read_text() == PRISTINE, "svg.rs already diverges from 36df6e8"
HL = "if lines.len() <= 3 || size < 20.0 {"
SVG.write_text(PRISTINE.replace(HL, HL.replace("<= 3", "<= 4")))
try:
    out = subprocess.run(["cargo", "test", "--manifest-path", "mag/Cargo.toml", "--test", "cover_modes",
                          "a_headline_of_three_lines", "--", "--nocapture"],
                         cwd=ROOT, capture_output=True, text=True)
    for line in (out.stdout + out.stderr).splitlines():
        if "panicked" in line or "index out of bounds" in line or "svg.rs:" in line:
            print("PANIC>", line.strip())
finally:
    SVG.write_text(PRISTINE)
    assert SVG.read_text() == PRISTINE
print("restored:", SVG.read_text() == PRISTINE)
PY
```

## Tool versions

python 3.12.11 via `uv run` (the system `python3` is 3.9.6, has different
Unicode tables, and must not be used), rustc 1.96.0, resvg/usvg 0.47.0 and
tiny-skia 0.12.0.

## Metrics

Baseline at `0978ebb`, `cargo test --no-fail-fast` over the whole tree: 18
binaries, 183 passed, 0 failed with the tightened fixtures, 181 with the
inherited ones, the difference being the two fitting tests this WP adds.
`cover_modes` holds 14 of those, 13 of its own plus one inlined
`metrics::exif_tests` case, against 12 before this WP.

Both totals are derived from the enumeration rather than carried alongside it:
the driver sums the `N passed` field of every `test result` line in the run and
counts those lines as `binaries`.

**The disputed `cover_modes` count, settled by stating its DOMAIN.** WP-5.4c
reported 12 and the planner enumerated 11 by name, both at `a911ff1`. Neither
is wrong and they are not the same measurement. Re-derived here, at `a911ff1`,
by the two enumerations:

| domain | at `25184fb` | at `a911ff1` | with this WP |
|---|---|---|---|
| `#[test]` functions written in `mag/tests/cover_modes.rs` | 11 | 11 | 13 |
| tests the `cover_modes` BINARY runs | 12 | 12 | 14 |

The gap is exactly one and it is structural, not a miscount: `cover_modes.rs`
opens with `#[path = "../src/critic/metrics.rs"] pub mod metrics;`, and that
file carries exactly one `#[test]`,
`orientation_is_read_when_present_and_ignored_otherwise`, which the binary
therefore runs and the file does not contain. So 11 is the file's own tests and
12 is the binary's, and a count of this file must say which. This WP adds two,
`a_publication_wordmark_at_the_size_floor_still_fits` and
`a_title_of_one_line_at_the_size_floor_still_fits`, moving both domains by two
and leaving the gap at one.

**Nothing in this measurement aborts early, and the `binaries` column is the
check for that rather than an ornament.** A run that stopped at the first
failing binary would evidence only the first failure, so the sweep uses ONE
`cargo test --no-fail-fast` over the whole workspace rather than
`--test a --test b`, which stops at the first failing binary. Every row below,
including the rows that fail, reports the SAME binary count as its baseline,
18 at `0978ebb`: no binary was skipped, so a row listing one failing test is a
statement about all 18 and not about the first one to break. The single row
that fails two tests names both.

**The defect, measured.** Against the INHERITED fixtures, of the four one-step
perturbations of the two floors this WP owns, exactly ZERO flip a test.
Enumerated and counted from the enumeration: four rows, zero FAILs. The four
headline rows are carried alongside as the control, and all four of those DO
flip, which is what distinguishes "these fixtures are loose" from "this sweep
cannot detect anything".

| one-step perturbation | inherited fixtures, binaries | passed of 181 | failing |
|---|---|---|---|
| wordmark floor 25.0 -> 25.5 | 18 | 181 | (none) |
| wordmark floor 25.0 -> 24.5 | 18 | 181 | (none) |
| title floor 12.0 -> 12.5 | 18 | 181 | (none) |
| title floor 12.0 -> 11.5 | 18 | 181 | (none) |
| headline size floor 20.0 -> 20.5 | 18 | 180 | `a_headline_of_three_lines_at_the_size_floor_still_fits` |
| headline size floor 20.0 -> 19.5 | 18 | 180 | `a_headline_that_cannot_fit_is_refused` |
| headline line limit `<= 3` -> `<= 4` | 18 | 179 | both headline tests |
| headline line limit `<= 3` -> `<= 2` | 18 | 180 | `a_headline_of_three_lines_at_the_size_floor_still_fits` |

**The fix, measured.** Same eight perturbations against the TIGHTENED fixtures,
each reverted in place and the revert asserted by content equality, each run
over the WHOLE suite so that "only the intended test" is a suite-wide claim.
Enumerated and counted from the enumeration: eight rows, eight flips, of which
the first four are this WP's and each fails EXACTLY ONE test.

| one-step perturbation | binaries | passed of 183 | failing |
|---|---|---|---|
| wordmark floor 25.0 -> 25.5 | 18 | 182 | `a_publication_wordmark_at_the_size_floor_still_fits` |
| wordmark floor 25.0 -> 24.5 | 18 | 182 | `a_publication_wordmark_that_cannot_fit_is_refused` |
| title floor 12.0 -> 12.5 | 18 | 182 | `a_title_of_one_line_at_the_size_floor_still_fits` |
| title floor 12.0 -> 11.5 | 18 | 182 | `a_title_that_cannot_fit_on_one_line_is_refused` |
| headline size floor 20.0 -> 20.5 | 18 | 182 | `a_headline_of_three_lines_at_the_size_floor_still_fits` |
| headline size floor 20.0 -> 19.5 | 18 | 182 | `a_headline_that_cannot_fit_is_refused` |
| headline line limit `<= 3` -> `<= 4` | 18 | 181 | both headline tests |
| headline line limit `<= 3` -> `<= 2` | 18 | 182 | `a_headline_of_three_lines_at_the_size_floor_still_fits` |

Both floors are now pinned from both sides, each by a one-step move, and no
perturbation disturbs any test outside the two belonging to the guard moved.
In particular `footer_caption_still_dispatches_through_materialize`, the OTHER
caller of `fit_display_line`, survives both title-floor moves untouched.

The four headline rows reproduce WP-5.4b-i's recorded flips exactly, test for
test, which is what shows the `compile`/`accepted`/`deck_of` refactor preserved
behaviour. Their `passed` column differs from WP-5.4b-i's 154 only because the
suite has grown; the FLIPS are identical, which is the part being claimed.

The `<= 4` row fails TWO tests, and the reason is measured here rather than
carried from WP-5.4b-i's report of it. Re-running that one perturbation with
`--nocapture` prints:

```
thread 'a_headline_of_three_lines_at_the_size_floor_still_fits' panicked at
tests/../src/cover/svg.rs:537:24:
index out of bounds: the len is 3 but the index is 3
```

With the limit at 4 the fitting headline fixture lays out four lines and
indexes a three-entry colour cycle. Both failures are genuine detections of
that one perturbation, not collateral from an unrelated test.

## Verdicts

`cargo test --no-fail-fast`, three runs, each named with its own commit because
a total is a measurement with a timestamp and the timestamp is the commit:

| commit | role | binaries | passed | failed | `cover_modes` |
|---|---|---|---|---|---|
| `0978ebb` | measurement, every `## Metrics` count | 18 | 183 | 0 | 14 |
| `a911ff1` | first rebase, after WP-5.4c | 23 | 217 | 0 | 14 |
| `6d18c77` | second rebase, gate for this landing | 23 | 223 | 0 | 14 |

The gate was RE-RUN at each rebase rather than carried forward, because a
rebase changes what must be re-verified and not only where a commit sits:
`a911ff1` landed `mag/src/cover/pdf.rs` and four `mag/tests/cover_pdf*` files,
and `6d18c77` arrived with WP-2.2b's typeset work and two more plan revisions.
The suite total moved 183 to 217 to 223 across them while `cover_modes` stayed
at 14 and nothing failed at any of the three, which is the shape a fixture-only
change should have. `cargo fmt --check` and
`cargo clippy --all-targets -- -D warnings` clean at the landing base.
`tools/nocomments.py` green via the `nocomments` test. No verdict.json is
produced or consumed by this WP; it touches no parity artifact. `cargo fmt --check` and `cargo clippy --all-targets -- -D warnings`
clean. `tools/nocomments.py` green via the `nocomments` test. No verdict.json
is produced or consumed by this WP; it touches no parity artifact.

Rule 12's replay clause is satisfied by construction and by demonstration. All
four `## Commands` blocks were EXTRACTED AGAIN from this file programmatically,
by a script that reads the section between the `## Commands` and
`## Tool versions` headings and shells each fenced block with
`bash -o pipefail -c`, and replayed in a SECOND worktree at `02f1d35`, which is
neither the directory nor the commit this WP was developed in.

**What the replay reproduces is the FLIPS, not the totals, and the difference
is the point of naming the measurement commit.** At `02f1d35` the suite is 19
binaries and 185 passing on the inherited fixtures, against 18 and 181 at
`0978ebb`, because WP-5.1f landed a binary and tests in between. Every row's
`failing` list is identical at both commits. A bare total would be unanchored;
a flip is not.
All four blocks exited 0. The comparison was made programmatically rather than
by eye, matching rows by `(fixture set, perturbation)` and comparing the
`failing` list: **16 rows at each commit, the same 16 keys, 16 of 16 identical
failing lists, 0 differing.** Binary counts 18 at `0978ebb` against 19 at
`02f1d35`, which is the expected and only difference. Of the 16 rows, 12 flip
at least one test: all 8 `tightened` rows, and 4 of the 8 `inherited` rows,
the four headline ones. The four `inherited` rows for the wordmark and title
floors flip nothing at either commit, which is this WP's reason to exist,
reproduced independently of the tree it was found in.

The four fenced blocks hash to
`8fff7eaf308c5403c3aea95e80071b23d3564d782a2ad183b83cbdaf1ffca800`, unchanged
between the replay and this submission: the prose around them was edited
afterwards and the extractor re-run to confirm the digest did not move. The
commands were not edited.

`git status` clean apart from the two owned paths; `mag/src/cover/svg.rs`
hashes identical to `36df6e8` after every perturbation and at submission.

## What is and is not proven

PROVEN: the wordmark size floor is 25.0 and not merely "some floor", and the
title size floor is 12.0 and not merely "some floor". Each is shown by a
committed fixture PAIR one step of the guard's own 0.5 grid apart in the input,
and by a one-step move of the threshold in both directions flipping exactly the
expected test and nothing else, suite-wide. The tests are
`a_publication_wordmark_at_the_size_floor_still_fits`,
`a_publication_wordmark_that_cannot_fit_is_refused`,
`a_title_of_one_line_at_the_size_floor_still_fits` and
`a_title_that_cannot_fit_on_one_line_is_refused` in
`mag/tests/cover_modes.rs`. The negative check is the `tightened` half of the
sweep table; the reason it was needed is the `inherited` half, where the same
four moves flip nothing.

PROVEN, and worth separating because the guard has two legs: the wordmark pair
pins the TAIL leg, `size * (97/42) + tail_width + 13`, which is the leg the
inherited fixture also bound. The head leg is 84.0566 pt against a 320.527559
pt limit for both strings, so it never binds.

NOT PROVEN and not claimed: the wordmark's HEAD leg is not separately pinned by
a one-step pair. A head-dominated pair exists and was measured while choosing
these fixtures (`Antidisestablishmentarianismi Review` first fits at 25.0,
`...arianisml Review` at 24.5), and it was NOT adopted, because adopting it
would have moved the binding leg off the one the inherited fixture exercised
and lost that coverage rather than added to it. Pinning both legs is a second
pair, owned by whoever next holds `mag/tests/cover_*`; it is recorded in
`## Residuals` so it has an owner rather than being an unowned gap.

NOT PROVEN and not claimed, and it is rule 10c's residue rather than its
finding: **`Ok` pins that the guard did not refuse, not WHICH SIZE it chose.**
All four fitting tests, the two this WP authored and the two it inherited,
assert acceptance and not the selected size, so a defect that returned the
wrong size while still accepting would pass them. It is NOT the property these
guards assert, and the one-step perturbations discriminate the accept/refuse
branch in both directions, which is what rule 10c is for. But the gap is real
and it should be named rather than absorbed into a "no".

It is closable in this file alone, and the hard part of the recipe is already
done here: the knobs are clean. `wordmark.right_reserve` is read at exactly one
place, `svg.rs:189`, inside the wordmark's `max_width`; `headline.width` at
exactly one place, `svg.rs:491`, inside the wrap, with the headline's x coming
separately from `headline.x` at `svg.rs:545`; and `honored_plate.title_size` is
the `max_size` argument only. All three live in `design()` in
`mag/tests/cover_modes.rs`, so a size-pin test needs no change outside this
WP's Owns. The shape, for the wordmark, with the numbers measured by the oracle
block above: the fitting fixture's markup under `right_reserve` 78.0 and under
73.0 must be IDENTICAL, since the tail leg at 25.5 is 327.4452 against a
widened limit of 325.5276 so the chosen size is still 25.0; and under 83.0 it
must DIFFER, since the limit of 315.5276 falls below the 319.7958 tail leg at
25.0 and forces exactly one step to 24.5, whose leg is 312.1465. The equality
and the difference together pin the size rather than the outcome. Owner: the
next holder of `mag/tests/cover_*`. Not done here because it changes what every
floor perturbation disturbs, so it invalidates the measured table in
`## Metrics` and needs the whole eight-perturbation sweep re-run, which is a
successor's work rather than a late edit to a verified one.

NOT PROVEN and not claimed: anything about `fit_display_line`'s OTHER caller.
`footer_caption` calls it at `title_size` 26.0, and the fixture pair here is
`honored_plate`'s. The sweep shows the footer_caption raster test is
undisturbed by both title-floor moves, which establishes that 010's own title
sits far above the floor, not that the footer_caption call site is pinned.

NOT PROVEN and not claimed: the ported arithmetic itself. This WP changed
FIXTURES only and does not touch `wordmark_size` or `fit_display_line`, so the
port is neither more nor less proven than WP-5.4b left it. What changed is that
the two numbers in it are now pinned rather than merely accompanied by a
correct message. Also not touched: the PDF writer (WP-5.4c), the back cover,
and `design.toml` loading.

The refusal MESSAGES were already proven by WP-5.4b and are re-asserted here
against messages Python produced in the oracle block's last section, not
re-derived by hand.

No row in this WP compares an empty set against an empty set or a constant
against itself. Every `tightened` row has a FAIL and a pass on the same
perturbation, and the `inherited` rows that report no failure are reported
precisely because the absence IS the finding.

## Residuals

**A second wordmark pair pinning the HEAD leg.** The guard's `max` has two legs
and only the tail leg is pinned at one step. The head-dominated pair is already
measured: with tail `Review`, head `ANTIDISESTABLISHMENTARIANISMI` first fits
at 25.0 (314.1613 pt against 320.527559) and `...ARIANISML` at 24.5 (320.5592
pt at size 25.0, 0.0316 pt over the limit, and 312.3356 at 24.5). Whoever next
holds `mag/tests/cover_*` can add it in four lines. Not done here because this
WP was dispatched to tighten two guards and a third fixture pair is new
coverage rather than the fix.

**The three-colour headline cycle still caps a fitting headline at three lines
independently of the guard**, and this WP MET and REPRODUCED the panic
WP-5.4b-i predicted rather than repeating its report: under
`line limit <= 3 -> <= 4` the fitting headline fixture lays out four lines and
panics at `mag/src/cover/svg.rs:537:24`, `index out of bounds: the len is 3 but
the index is 3`, printed by the fourth `## Commands` block. Recorded, not
fixed. `svg.rs` is outside this WP's
Owns, the coupling is faithful to Python, which has the same three-colour
cycle, and it is UNREACHABLE while the limit is `<= 3`, so it is NOT live on
the branch and no consumer needs to avoid this code. It is a second,
independent reason the limit of 3 is load-bearing.

**The defect this WP fixes WAS live on the branch** in the sense rule 3b cares
about, and is now discharged: the wordmark and title floors shipped with
fixtures that could not detect a one-step change to either number, so any WP
that moved them by one step would have seen a green suite. No consumer needs to
avoid the code, because the CODE was correct throughout; what was defective was
the evidence that it was.

The three MESSAGE-ONLY refusals in `svg.rs` (unknown layout, missing art, no
glyph) have no number to get wrong and remain correctly message-only.

**`mag/tests/cover_*` now has two owners, noticed at the rebase rather than
reasoned about.** WP-5.4c landed as `a911ff1` while this WP was verifying and
added `cover_pdf.rs` plus three `cover_pdf_*_expected.txt` files, all of which
match the Owns glob this WP and WP-5.4b-i were given. Nothing was lost:
`cover_modes.rs` is byte-unchanged between `0978ebb` and `a911ff1`, so the
rebase carried cleanly, and this WP's diff touches neither the PDF fixtures nor
`pdf.rs`. But a glob assigned to two live WPs is the mechanical-conflict shape
rule 1 serializes for, and the next WP briefed against `mag/tests/cover_*`
should be given the file names rather than the glob. Recorded for the plan
rather than acted on, since it caused no collision here.

**WP-5.4c's numeric guards are NOT swept by this WP.** It added a PDF writer
with its own expectation files, landed after this WP's measurement commit, and
`mag/src/cover/pdf.rs` is explicitly outside this WP's Owns. The straddle rule
binds on inheritance, so whoever next holds these fixtures inherits that sweep;
this WP's sweep covered the four numeric guards reachable through
`materialize`, namely the wordmark and title floors it fixed and the headline
and deck limits it re-checked.

## Status

done
