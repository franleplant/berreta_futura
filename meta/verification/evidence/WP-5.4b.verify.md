# WP-5.4b verification

## Verdict

ACCEPTED, at rework commit `2b2ab9a`.

Both defects from the rejection at `be6ec61` are fixed and verified by
reproduction rather than by reading. One new finding is recorded below: a
PRE-EXISTING refusal fixture is insensitive to one of its two thresholds. It
is not a defect in this rework and the evidence does not overclaim it, so it
is a residual rather than grounds for rejection.

## Rejection record

`36df6e8` was rejected at `be6ec61` for two evidence-level defects, no code
defect:

1. The recorded oracle did not run. `rb"\1 fill=\"none\""` is a raw bytes
   literal, so the escaped quotes inserted literally and resvg rejected the
   SVG at char 92. Correcting only the escaping reproduced all three digests,
   so the work was sound and the provenance was not reproducible.
2. Refusal coverage understated itself. `svg.rs` carries six `bail!` sites;
   three were tested, one disclosed as uncovered, and two were neither.

## Base

Worker commit `2b2ab9a`, parent `e19727c`. Verified in a fresh worktree at
`2b2ab9a`.

## Owns

`git show --stat 2b2ab9a` lists exactly two files:

    mag/tests/cover_modes.rs              |  67 +++++++++++++
    meta/verification/evidence/WP-5.4b.md | 182 +++++++++++++++++++++--------

`git diff --stat 36df6e8 2b2ab9a -- mag/src/cover/svg.rs` is empty, so the
ported code is unchanged and both defects were indeed evidence-level. No
`*.verify.md`, no `baseline.json`, and neither `mag/src/cover/pdf.rs` nor
`mag/tests/cover_pdf.rs` (WP-5.4c's, in its own worktree) is touched.

## Defect 1: the oracle now runs as recorded

Both `## Commands` blocks were extracted PROGRAMMATICALLY from the evidence
file and executed, per rule 12, rather than retyped:

    uv run python - <<'PYEOF'
    import re, pathlib
    t = pathlib.Path("meta/verification/evidence/WP-5.4b.md").read_text()
    sec = t.split("## Commands")[1].split("## Tool versions")[0]
    blocks = re.findall(r"```[a-z]*\n(.*?)```", sec, re.S)
    for i, b in enumerate(blocks):
        pathlib.Path(f"/tmp/wp54b_block{i}.sh").write_text(b)
    PYEOF
    bash /tmp/wp54b_block0.sh
    bash /tmp/wp54b_block1.sh

Both are now quoted heredocs (`<<'PY'`), so nothing requires escaping and the
raw-bytes-literal trap cannot recur structurally.

Block 0 (the oracle) reproduced all three digests exactly:

| mode | digest | size |
|---|---|---|
| `framed` | `ece03e915b38e0d3fc36cf68499c4f63c3bad698992210119ba07035fcb11aca` | 1748x2480 |
| `honored_plate` | `c46b2db485d6bcba195cbda9e37ad9ecbcfca6baa0dc2561af1e4522322a02e9` | 1748x2480 |
| `footer_caption` | `4b4549e9b97ead363014cb94eb8ff3e6af4491c7f865bd0bba3fd665988190b2` | 1748x2480 |

The `footer_caption` value matches WP-5.4's committed hash, which is the
stand-in edition's self-validation on a mode this WP did not port.

Block 1 (the refusal probe) reproduced five Python-captured messages:
wordmark, title, deck-refuses-at-six-wrapped-lines, deck-fits-at-five, and
headline.

## Defect 2: all six bail sites exercised

`grep -n "bail!" mag/src/cover/svg.rs` gives six sites, each with a test
asserting full-message equality:

| site | message | test |
|---|---|---|
| `:193` | Publication wordmark cannot fit | `a_publication_wordmark_that_cannot_fit_is_refused` |
| `:352` | Cover title cannot fit on one line | `a_title_that_cannot_fit_on_one_line_is_refused` |
| `:520` | Cover headline cannot fit | `a_headline_that_cannot_fit_is_refused` |
| `:566` | Cover deck cannot fit | `a_deck_that_cannot_fit_is_refused` |
| `:590` | Cover art is missing | `missing_cover_art_is_refused_by_every_mode_that_places_it` |
| `:723` | unknown layout | `an_unknown_layout_is_refused_as_python_refuses_it` |

Six sites, six covered, plus `a_deck_of_five_wrapped_lines_still_fits`
pinning the fitting side of the deck boundary.

## Threshold perturbation

Each perturbation applied to `svg.rs` in place and reverted afterwards;
`mag/src/cover/svg.rs` restored from a pristine copy and confirmed clean at
the end.

Baseline: 11 passed, 0 failed.

| perturbation | result |
|---|---|
| wordmark floor `25.0` to `20.0` | `a_publication_wordmark_...` FAILS, alone |
| deck limit `> 5` to `> 6` (one unit) | `a_deck_that_cannot_fit_is_refused` FAILS, alone |

Both worker claims reproduce, and each fails only its own test. The deck's
one-unit sensitivity is the specific claim the rework rested on and it holds.

## Finding: the pre-existing headline fixture is half-insensitive

Applying the same method to the three refusals that predate this rework:

`missing cover art` (`:590`) and `unknown layout` (`:723`) are CATEGORICAL
refusals with no numeric threshold to move, so the technique does not apply
to them. A categorical refusal cannot sit far past a boundary.

`headline` (`:520`) has two thresholds, and discriminates on only one:

| perturbation | result |
|---|---|
| headline size floor `20.0` to `15.0` (both sites, lines 514 and 519) | test STILL PASSES |
| headline line limit `<= 3` to `<= 6` (line 514) | test FAILS, alone |

So the fixture pins the line-count rule but not the size floor: the headline
string is long enough that it refuses even when the shrink floor drops by a
quarter. A regression moving that floor from 20.0 to 15.0 would go
undetected by this fixture.

This is exactly the weakness the worker identified and fixed in its own first
deck fixture, present in a fixture it inherited rather than wrote. It is NOT a
false claim: the evidence states that all six messages are covered "with three
of them additionally perturbed at their threshold rather than only their
text", which is accurate, and it does not assert that the other three
discriminate. Recorded as a residual for whoever next touches these fixtures,
with the note that only the headline is actionable, since the other two have
no threshold.

## The worker's general point

Its claim is that full-message equality is cheap to satisfy and proves less
than it looks, because a refusal fixture can sit so far past the boundary that
it refuses under any plausible rule, and only threshold perturbation
distinguishes the two. Confirmed, and this verification supplies a third
instance beyond its own deck: the headline fixture passes a 25% reduction of
its size floor. The distinction belongs in the record per rule 10 and is
partially there already; the evidence names which three were threshold-tested
but does not name which of the remaining three COULD be. Suggested wording for
a future revision: mark each refusal as threshold-discriminating,
message-only, or categorical.

## Metrics

- extracted command blocks: 2 of 2 run as recorded
- digests reproduced: 3 of 3
- `bail!` sites: 6 of 6 covered with full-message equality
- threshold perturbations reproduced: 2 of 2, each failing only its own test
- threshold perturbations newly applied to pre-existing fixtures: 2 on
  headline (1 discriminates, 1 does not), 0 applicable on the other two
- baseline: fmt clean, clippy `-D warnings` clean, 17 test binaries green

## Tool versions

`uv run python` 3.12.11, rustc 1.96.0, poppler 25.08.0. Note this machine
carries a second Python (system 3.9.6, Unicode 13.0.0); all Python here is
`uv run python`.

## Verdicts

Worker evidence at `2b2ab9a` verified. No verdict.json is produced by this WP.

## Residuals

1. The headline refusal fixture does not discriminate on its size floor
   (20.0 to 15.0 still refuses). Actionable; the deck's method applies.
2. `missing cover art` and `unknown layout` are categorical and have no
   threshold; recorded so nobody reads their absence from the perturbation
   table as a gap.
3. The contributor-less deck path and the PDF writer remain not proven, as
   the WP's own section states. WP-5.4c is building the writer.

## What is and is not proven

PROVEN by this verification: that both recorded command blocks run as written
when extracted from the evidence file; that the three digests reproduce; that
all six `bail!` sites are covered; and that the wordmark and deck fixtures
discriminate at their thresholds, the deck by one unit.

NOT PROVEN: that the headline fixture discriminates at its size floor (it does
not, shown above); anything about the PDF writer, the back cover, or
`design.toml`, none of which this WP claims.

## Status

done
