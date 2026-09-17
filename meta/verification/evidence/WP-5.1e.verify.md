# WP-5.1e verification

## Base

Worker commit `10d705d` (base `abaa9aa`), correction commit `0f45c6b`. Plan
revision 24 at the time of the correction; `art_directed` had reached
revision 25 (`df1398d`) when this verdict landed.

## Prior rejection, recorded

The first submission was REJECTED at verify commit `aa4bc01`, on one
paragraph of reasoning and no code defect. The `luma601` section concluded
that no action was needed because `grep -rn "luma601\|19595" mag/src/`
matched only `critic/metrics.rs`. That search was structurally incapable of
finding the second implementation, so it proved nothing. Everything else was
verified and accepted at that commit and was not re-examined here.

## Verdict

**ACCEPTED.** The correction replaces the unsound paragraph, withdraws the
conclusion rather than defending it, and draws the reusable principle
accurately.

## Owns

`git show --stat 0f45c6b` lists exactly one file,
`meta/verification/evidence/WP-5.1e.md`, 69 insertions and 12 deletions. No
code, no other evidence file, no `*.verify.md`, no `baseline.json`.
`mag/src/**` is untouched by this commit.

## Both formulas confirmed at source

| claim | source | confirmed |
|---|---|---|
| `cover/art.rs:12` `grey`, per-mille | `r*299 + g*587 + b*114`, `(value + 500) / 1000`, `.min(255)` | yes, verbatim at that line |
| `critic/metrics.rs:541` `luma601`, PIL fixed-point | `(r*19595 + g*38470 + b*7471 + 0x8000) >> 16` | yes, verbatim at that line |

Both line references are exact.

## The search was structurally incapable, verified directly

`grep -rn "luma601\|19595" mag/src/` returns three hits, all inside
`critic/metrics.rs`. `fn grey` sits at `mag/src/cover/art.rs:12` and is
invisible to it. The per-mille constants `299|587|114` appear **0** times in
`metrics.rs`, and neither `luma601` nor `19595` appears in `art.rs`. The two
sites share no searchable token in either direction, so no single grep term
could have matched both. The evidence's characterisation is exact.

## The five points

1. **Replaced, not rewritten.** The diff deletes the twelve-line original and
   opens the new section by naming the failure: the search "could not have
   found the second implementation, so it proved nothing", recorded "rather
   than quietly rewritten, because the failure mode is the point". Both
   formulas appear in a table with their rounding.
2. **The conclusion is withdrawn, plainly and without hedging.** The evidence
   states "**The conclusion does not survive either**", that `cover.py`
   reaches greyscale through PIL's `convert("L")` which IS the fixed-point
   formula, that `metrics.rs::luma601` is therefore already correct and
   `grey` "is simply wrong", and that "the right disposition is the opposite
   of what this section first said". The thematic objection is conceded in
   the same breath: it ruled out `model/shared.rs` as a *destination* and
   "was never load-bearing", and "ruling out one destination was mistaken for
   ruling out the lift", with the one-word visibility change in
   `critic/metrics.rs` available all along. The fix is assigned to WP-5.4's
   rework rather than claimed here.
3. **The blind-spot note is sharpened correctly.** The pair differs in name,
   body, fixed-point scale and rounding, so neither audit key fires; the new
   part is that a manual search missed it too, because `299` and `19595`
   denote the same coefficient at different scales and share no substring.
   The evidence says detection failed at three levels, "including the one a
   person would reach for first", and states it indicts the WP's own method
   rather than only the audit's.
4. **The principle is stated accurately and its supporting fact is right.**
   Each implementation pinned to its own Python original by its own oracle is
   a stronger guarantee than the two Rust copies agreeing, "because agreement
   between two Rust copies is satisfied just as well when both are wrong".
   The supporting fact holds: WP-5.4's oracle caught `grey` as unfaithful to
   `convert("L")`, and no comparison between the two Rust functions would
   have, since they were never compared. The evidence also connects it to
   WP-5.4a's discipline of pinning its copies to Python over the whole plane
   rather than to the other Rust copy.
5. **The correction is in Residuals**, not buried in Metrics, and states that
   the widened audit "does NOT catch this pair and cannot be made to", with a
   pointer to the blind-spot section.

## Residuals

- The remedy itself is not in this WP. `art.rs` still computes its own luma;
  importing `luma601` belongs to WP-5.4's rework, which the evidence assigns
  explicitly. This verdict covers the record, not the fix.
- The widened audit remains green on this pair by design, not by oversight.
  A reader of the audit's output alone would not learn that a luma defect
  exists; the Residuals entry is the only place in this WP's record that says
  so.

## Status

done
