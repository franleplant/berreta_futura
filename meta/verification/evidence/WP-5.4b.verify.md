# WP-5.4b verification

## Base

Worker commit `36df6e8` ("feat(cover): WP-5.4b cover modes and refusal branches").
Verified in a fresh worktree at that commit. Pre-land HEAD for this verify file
recorded in Status below.

## Verdict

**REJECTED**, on two evidence-level defects. No defect was found in the ported
code: both new mode hashes reproduce exactly, the discrimination is genuine and
mode-independent, and WP-5.4's acceptance survives intact. The rejection is that
the recorded oracle **does not run as recorded**, and that the refusal-coverage
statement **understates what is uncovered**.

## Owns

`git show --stat 36df6e8` lists exactly four files:

- `mag/src/cover/svg.rs` (+333)
- `mag/tests/cover_footer_caption.rs` (+38/-1)
- `mag/tests/cover_modes.rs` (+216)
- `meta/verification/evidence/WP-5.4b.md` (+219)

Within Owns (`mag/src/cover/` except `text.rs`, `mag/tests/cover*`, its evidence).
No Cargo change, no `*.verify.md`, no `baseline.json`, `text.rs` untouched. Clean.

## Baseline

`cargo test` green: 16 binaries, 144 tests, 0 failures, exit 0.
`cargo fmt --check` clean. `cargo clippy --all-targets -- -D warnings` exit 0.

(The evidence says 15 binaries; the measured figure is 16. Erratum, not a defect —
sibling WPs landed test binaries underneath.)

## Defect 1: the recorded oracle command does not run

Extracted verbatim from the evidence's first fenced block and executed from the
worktree, the oracle **panics**:

```
pyo3_runtime.PanicException: called `Result::unwrap()` on an `Err` value:
ParsingFailed(InvalidChar2("a quote", 92, TextPos { row: 5, col: 85 }))
```

Cause, at evidence line 28:

```python
out = re.sub(rb"(<rect data-slot=\"" + slot + rb"\"[^>]*?) fill=\"[^\"]+\"", rb"\1 fill=\"none\"", out, count=1)
```

The replacement `rb"\1 fill=\"none\""` is a **raw** bytes literal, so `\"` remains
backslash-quote and is inserted literally into the SVG. resvg then rejects the
document at char 92 (`\`), which is exactly the reported position. The patterns
are fine — in a regex, `\"` is an escaped quote — only the replacement is wrong.

**The hashes are nonetheless correct.** Changing only that escaping (raw literals
re-quoted so no backslash survives, no other edit) reproduces all three digests:

| layout | digest | claimed | size |
|---|---|---|---|
| `framed` | `ece03e915b38e0d3fc36cf68499c4f63c3bad698992210119ba07035fcb11aca` | match | 1748x2480 |
| `honored_plate` | `c46b2db485d6bcba195cbda9e37ad9ecbcfca6baa0dc2561af1e4522322a02e9` | match | 1748x2480 |
| `footer_caption` | `4b4549e9b97ead363014cb94eb8ff3e6af4491c7f865bd0bba3fd665988190b2` | match | 1748x2480 |

So the work is sound and the **provenance is not reproducible**. This is the same
class WP-5.1b was rejected for (replaying `## Commands` did not reproduce the
committed oracles) and that WP-5.4 was rejected for two rounds ago (an oracle with
no command producing it). A reader following the record gets a panic, not a hash.

Remedy: correct the replacement literal and re-run to confirm the block as written
emits the three digests.

## Defect 2: the refusal-coverage statement understates what is uncovered

`mag/src/cover/svg.rs` carries **six** `bail!` sites. The evidence enumerates three
as covered and names **one** more as deliberately uncovered, leaving two that are
neither tested nor disclosed:

| site | message | status |
|---|---|---|
| `:193` | `Publication wordmark cannot fit` | **untested, undisclosed** |
| `:352` | `Cover title cannot fit on one line` | **untested, undisclosed** |
| `:520` | `Cover headline cannot fit` | tested |
| `:566` | `Cover deck cannot fit` | untested, disclosed |
| `:590` | `Cover art is missing` | tested (both placing modes) |
| `:723` | unknown layout | tested |

This matters because **WP-6.1 depends on this WP**: deleting the Python must not
delete a capability nothing has proven, and two ported refusals are currently
neither exercised nor recorded as unexercised. The `## What is and is not proven`
section lists the proven side accurately; its not-proven side is incomplete, which
is the failure mode that section exists to prevent.

Remedy: either cover them or name them, with the same honesty as the deck entry.

## Verified claims

**Both modes reproduce**, first run, no tuning — see the table above. Dimensions
1748x2480 premultiplied RGBA as claimed.

**The stand-in edition is validated, not assumed.** Running the oracle on
`footer_caption` reproduces WP-5.4's committed
`4b4549e9b97ead363014cb94eb8ff3e6af4491c7f865bd0bba3fd665988190b2` byte for byte.
That self-check is what makes the two new digests trustworthy: the harness is shown
correct against a hash it did not produce, on a mode this WP did not port.

**The SVGs are correctly not compared.** Confirmed as a PNG-encoding difference:
Rust and Python encode the graded art differently, so the base64 payload diverges
while the decoded pixels agree. Comparing rasters rather than markup is the right
call and matches WP-5.4's precedent.

**Discrimination reproduced, and the two oracles are independent.** Each
perturbation was applied in place and reverted:

| perturbation | `framed` | `honored_plate` | `footer_caption` |
|---|---|---|---|
| headline colour violet to ink (`svg.rs:533`) | **FAIL** | pass | pass |
| `honored_plate` right_edge 8.0 to 9.0 (`svg.rs:651`) | pass | **FAIL** | pass |

Each fails only its own mode, so neither oracle is covering for the other. The
`footer_caption` raster test in `cover_footer_caption.rs` passed under both.

**Refusals fire for the stated reason.** All three assert **exact full-message
equality**, not a substring, and the messages match Python's templates read from
`cover.py`: `Unknown cover layout {layout!r}: expected framed, footer_caption, or
honored_plate`, `Cover art is missing: {edition.cover_art}`, and `Cover headline
cannot fit: {...}`. The overflow headline was chosen by asking Python which strings
it refuses rather than by guessing, which is the right method.

## WP-5.4's acceptance survives

The `Design` extension forced a +38/-1 edit to `mag/tests/cover_footer_caption.rs`,
which is inside this WP's Owns but carries WP-5.4's acceptance. Read as a diff
rather than as a description, it is **entirely construction**:

- `#[allow(dead_code)]` on the `#[path]` include of `svg.rs`
- a widened `use` (adding `Art`, `Deck`, `Footer`, `Headline`, `HonoredPlate`)
- new fields in `design()`: `palette.violet`, `tab.overdraw`, and the `headline`,
  `art`, `deck`, `footer` and `honored_plate` structs

No line containing an assertion, an expectation path or a digit-string was touched;
the single deletion is the one-line `use` replaced by its multi-line form. Both
assertions are unchanged in count (2 before, 2 after) and both read **committed
oracle files** rather than inline literals, so the expectations cannot have moved
with the test. Confirmed by blob hash across WP-5.4's rework, its evidence fix and
this commit:

| file | e639b32 | c084e16 | 36df6e8 |
|---|---|---|---|
| `cover_zone_expected.json` | `b94e3189…` | `b94e3189…` | `b94e3189…` |
| `cover_footer_caption_expected.txt` | `1228bfa8…` | `1228bfa8…` | `1228bfa8…` |
| `critic_metrics_expected.json` | `39be9e81…` | `39be9e81…` | `39be9e81…` |

`critic_metrics_expected` matches the claimed
`39be9e815b4403a8bcd8b27c07944fe3daa29e31`.

**Its discrimination proof re-runs intact.** Reverting `art.rs:40` from
`luma601(pixel)` to the per-mille formula fails zone statistics with exactly the
claimed numbers while the raster passes in the same run:

```
top_mean diverged from PIL: 109.56702330964686 against 109.56689949397072
test zone_statistics_match_the_python_compiler ... FAILED
test footer_caption_raster_matches_the_python_compiler ... ok
```

That is the aggregation gap still demonstrated, so WP-5.4's acceptance is intact.

## Judgments

**The uncovered deck-overflow reasoning is weaker than the WP allows.** The stated
reason is that the refusal message includes the full text, so a fixture would pin a
string of no significance. But the WP solved exactly that problem for the headline,
by asking Python which strings it refuses rather than inventing one, and the same
method applies to the deck. The branch is implemented at `svg.rs:566` and WP-6.1
rests on this WP's coverage, so I would cover it rather than record it. The
contributor-less deck path is a better candidate for deliberate non-coverage, since
it turns on a stand-in attribute rather than a string.

**The missing PDF writer is confirmed and correctly recorded.** `mag/src/cover/`
contains `art.rs`, `outline.rs`, `raster.rs`, `svg.rs` and `text.rs` — no PDF
module. The `pdf` matches in `svg.rs` are coordinate variables (`pdf_baseline`),
not a writer. So all three cover modes are proven at SVG-and-raster level only, and
the guard "add coverage, not a second writer" could not apply because there is
nothing to add to.

Consequences, and both are already visible in the record rather than latent:
WP-5.6 depends on WP-5.4 and must produce covers natively, so it cannot do so until
a writer exists — WP-5.4's own `## What is and is not proven` lists the writer as
not built, and this WP repeats it. WP-6.1 depends on WP-5.4b, and its guarantee is
narrower than "the cover capability is proven": what is proven is that three
layouts produce byte-identical **SVG rasters**, not that a cover **PDF** can be
written. Both WPs state this accurately, which is the section doing its job. The
orchestrator has a WP-5.4c (cover PDF writer) tracked, which is the right home.

## Status

`rejected` — two evidence-level defects, no code defect. Remedies are a corrected
oracle literal with a confirming re-run, and a completed not-proven list covering
`svg.rs:193` and `svg.rs:352`.
