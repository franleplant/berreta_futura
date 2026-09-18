# WP-2.0b verification

Verdict: **ACCEPTED**, with three non-blocking findings.

## Base

Worker commit `e5e741a`, verified in a clean worktree at that commit.
Baseline: `cargo fmt --check` exit 0, `cargo clippy --all-targets -- -D warnings`
clean, `cargo test` green across all binaries (20 tests: 1 fault suite, 4 text
seam, 13 preflight, 2 helper audit).

## Owns

`git show --stat e5e741a` lists exactly four paths: `mag/src/parity.rs`,
`mag/src/main.rs`, `meta/verification/parity.yaml`,
`meta/verification/evidence/WP-2.0b.md`. The `parity.yaml` diff adds the
`page_sets:` key and nothing else. The `main.rs` diff is three clap flags
(`--run`, `--oracle-only`, `--set`) plus the orchestrator-granted seam consumer
test; both are within the WP-0.2 preamble's registration precedent and the
recorded grant. No `*.verify.md`, no `baseline.json`.

## Page sets: evaluated per run, not stored

The rules in `parity.yaml page_sets.rules` carry derivations, never page
numbers. Verified by grep: no literal `56`, `54` or `34` appears in
`parity.rs`, and the only digit in the `page_sets` block is the "rule 9"
citation.

Reproduced on the oracle leg: `body 34, code 0, furniture 54, openers 9,
placement 11`, and `54 = 34 + 9 + 11`, so openers and placement are disjoint on
this edition and body is exactly the remainder.

**Per-run derivation proved by perturbation.** Shifting one `layout.toc` entry
in the oracle leg's `en/edition-manifest.json`
(`an-alignment-assessment-of-recent-cybersecurity`, 11 to 12) changed `body`
from 34 to 36; restoring the manifest returned it to 34. The oracle cache is
keyed on `request.json`, not the manifest, so the cache stayed warm and the
change is isolated to the derivation. The sets are computed from the manifest
on every run.

## The staleness guard fires

Seeding `baseline.json` with a digest that cannot match (64 zeros) and running
`--set body` exits 1 with:

    staged inputs differ from the baseline digest: page-set scoring and ratchet
    comparison are refused until a verifier rebases baseline.json from a fresh run

Restoring the baseline, the same command exits 0 and scores `body`: 34 pages, 0
clauses differing. Demonstrated in the working tree and restored; `baseline.json`
is verifier-owned and the worker correctly did not commit a seeded copy.

The digest is computed from the oracle leg's own `request.json` (47 input rows),
hashing each row's `targetPath` with the content of its `sourcePath`, sorted,
and deliberately ignoring `sourcePath` itself. That choice is correct:
WP-2.0a's verification established that all 48 differing `request.json` leaves
between two checkouts are absolute paths, so including them would make the
digest checkout-dependent and defeat both the cache and the guard.

## `--oracle-only` is Tier E green end to end

Reproduced: page_count pass (56 vs 56), boxes 0 mismatches, text 0 pages differ,
colour 0, navigation 0 mismatches, Tier G max dx/dy 0.000 pt with 0 structure
mismatches, display list 0 pages differ, **glyph positions pass over 68,530
glyphs in 1,501 shows with 0 violations and worst ratio 0.0000**, Tier V dims
pass with max channel delta 0, and Tier E raster correctly `not_evaluated`
(revision 15 withdrew that guard). Exit 0.

Verdict byte-identical across two consecutive runs:
`38f91a9493a5a571801623c4b8a3af5d1c238d1fafe37b1ef8d01e2c7d7b443a` both times,
with the second run reporting `oracle leg: cached` as documented.

## The green-verdict-without-comparison class

This is the defect the worker's first implementation shipped, and the fix is
load-bearing.

**The failure mode reconstructs.** Removing `v.typst_leg.is_none() &&` from
`all_evaluated_pass` and re-running the default mode gives **exit 0** while the
console still prints `typst leg: fail`. Every clause passes because the typst
leg's failure sets `dir_b = dir_a`, so the oracle is compared against itself.
Restored, the same run exits 1. The guard is exactly what stands between a
failed leg and a green gate.

**As shipped it is correct**: exit 1, `mode: typst_leg_failed`, `typst_leg`
carrying the stub's message naming WP-2.2a, and `a_reader_sha256 ==
b_reader_sha256` recorded in the verdict.

`all_evaluated_pass` is otherwise sound: every clause is required via
`is_some_and`, so a clause that did not evaluate cannot count as a pass, and the
raster clause is excluded only by an explicit `not_evaluated` match rather than
by absence.

**One further self-comparison path exists and is green** (finding 1 below):
`--pre-rendered X X` exits 0 with `mode: pre_rendered` and equal input hashes.
That is a sanctioned self-test — WP-0.2a's verify clause required exactly it —
and the JSON records both the mode and the equal hashes.

## The seam export

`trace_elements`, `Element`, `Color` and `Face as TextFace` are `pub(crate) use`
re-exports; `display::extract`'s reach is unchanged.

**The consumer test genuinely proves reachability.** Deleting the two
`pub(crate) use` lines fails the build with
`error[E0432]: unresolved imports crate::parity::trace_elements,
crate::parity::Element, crate::parity::TextFace`. It is a compile-time proof.

**And it could not have been written in `mag/tests/`.** `mag/Cargo.toml`
declares `[[bin]]` and no `[lib]`, so integration tests cannot `use mag::...` at
all — which is why every test in `mag/tests/` reaches source through `#[path]`
includes, and exactly how WP-0.2h's unreachable seam hid: a `#[path]` include
bypasses module privacy, so the demonstration passed while the seam was
unusable. Placing the consumer test in `main.rs` under `#[cfg(test)]`, resolving
through `crate::parity::`, is the only construction in this crate that tests the
path a real consumer uses. That reasoning is correct and worth reusing.

## Stage-twice-and-assert

Reference stability specifies that both legs render from ONE staged copy so a
comparison cannot drift. `render::run` stages internally and `render.rs` is
outside this WP's Owns, so the implementation stages twice and asserts the two
digests match, bailing with both values if they differ.

**Judged acceptable.** It converts a guarantee by construction into a guarantee
by detection with a loud failure, and the property that matters — the two
compared legs saw identical inputs — holds either way, because a run whose
inputs moved aborts instead of reporting. The cost is a wasted render, not a
wrong answer.

Two bounds on that equivalence, recorded rather than waved through: the digest
covers what `request.json` enumerates (47 rows here), so a staged input not
listed there would be invisible to the assert; and the assert compares content
hashes, so agreement is as strong as SHA-256. Collapsing to a single staging
needs `render.rs` and is correctly left to a WP that owns it.

## Rule 9

No pass condition compares against a figure edition 010 happens to have today.
The evidence's `## Metrics` opens by stating its figures are observations and
citing rule 9, and the code carries no such literals.

## Findings, none blocking

1. **The console summary does not announce the mode.** `--oracle-only` and
   `--pre-rendered X X` both print a full green clause list with no indication
   that the two sides were the same bytes; `grep` for the mode in the console
   output of a self-comparison returns nothing. The verdict JSON records `mode`
   and both (equal) input hashes, so it is discoverable there, and an operator
   who typed `--oracle-only` knows what they asked for. The exposure is a script
   that passes the same directory twice by accident and reads the green as a
   real comparison. This is rule 2b's shape one layer out — an env-gated test
   must announce its mode, and so should a self-comparison. Recommend
   `summarize()` print `mode`, and warn when `a_reader_sha256 ==
   b_reader_sha256` outside `oracle_only`.

2. **No `## What is and is not proven` section.** Revision 27 made it required;
   this WP was briefed and landed before that revision, so the absence is
   chronological rather than a defect. Worth adding whenever the file is next
   touched.

3. **Stale-digest with no `--set` is silent.** When the digest is stale and
   `--set` is absent, `page_sets` is simply omitted from the verdict rather than
   marked refused. `verdict.staleness` still records `stale`, so it is
   discoverable, but the omission itself says nothing.

## Status

accepted
