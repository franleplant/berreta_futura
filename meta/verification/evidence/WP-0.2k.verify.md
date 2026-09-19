# WP-0.2k verification: seed the baseline and make the ratchet operative

## Verdict: ACCEPTED

Every claim in `meta/verification/evidence/WP-0.2k.md` reproduced, from
worktrees the work was not done in, at the landed commit `b271911`. The seed,
the two refusals, the stale-corpus failure against the base commit's reporting,
the concurrency fix, the discharge of WP-0.2g's Residual 1 and the suite all
hold, and three of them reproduced to the digit. Two of the WP's own
`## What is and is not proven` gaps are closed here by execution rather than by
argument, and one new finding is recorded that the plan should act on before any
WP touches `--oracle-only`.

**Phase 3 can start.** Its stated precondition, "`mag parity 010` green against
`baseline.json` (no page regresses)", is executable at `b271911`: the digest is
seeded and returns `fresh` or refuses, the per-page comparison exists, the
working-tree half refuses a lowering by name end to end (measured below, which
the WP could not do), and a verifier commits a proposal rather than hand-editing
tiers. The gate is not vacuous: the 54 seeded rows are at the bottom rung, so
the first Phase 3 measurement has to earn every rise.

## Base, and where this was replayed

- Verified commit: `b271911`, parent `8a03c1a`. `git merge-base --is-ancestor
  b271911 art_directed` -> true at `f127381`.
- Replay worktrees, none of them the worker's: `vwp02k` (`b271911`, the
  replay), `vwp02k-base` (`be5258d`, the rule-11 comparison), `vwp02k-probe`
  (`b271911`, the attacks), plus a scratch git repository at `/tmp/minirepo`
  for the one check that needs a different `HEAD`.
- Rule 12 extraction was programmatic: the `## Commands` section was split on
  its `### ` headings and every ```sh``` fence written to `b1.sh` .. `b8.sh`,
  **8 blocks under 7 headings** (the base-commit heading carries prose before
  its fence, so a caption-then-fence pairing mis-associates them; counted by
  heading, not by position). Each was run with `zsh` from the worktree root.
- All 8 blocks ran. Block 6 failed on its first attempt with
  `[Errno 28] No space left on device` from the render adapter: the host filled
  to 100% (2.1 GiB free) mid-replay. **That is an environment failure, not the
  block's**, reported here per the fail-loud rule; after reclaiming ~20 GiB of
  day-old `target/` directories with `cargo clean`, block 6 reproduced exactly.
  Its aborted first run left the perturbed `final.md` in the worktree, because
  `set -e` skipped the block's own restore line; restored with
  `git show HEAD:<path> > <path>` and `git status --porcelain` confirmed clean
  before re-running.

## Owns and the diff check (rule 1)

`git diff --name-only 8a03c1a b271911` returns six paths: `mag/src/parity.rs`,
`mag/tests/parity_concurrent.rs`, `mag/tests/parity_fixture/mod.rs`,
`mag/tests/parity_ratchet.rs`, `meta/verification/baseline.json`,
`meta/verification/evidence/WP-0.2k.md`. **No `evidence/*.verify.md` is
touched.** `baseline.json` is touched and is licensed: the WP section names it
explicitly ("the second WP besides WP-0.2a licensed to write it under rule 1").

Two deviations, both recorded rather than waived:

1. **The three `mag/tests/parity_*` files are outside the literal Owns list**
   (`mag/src/parity.rs` and `baseline.json`). They are new files, so no other
   agent's work was at risk and rule 1c's logical-coupling hazard does not
   arise, and the WP's `Verify` line demands committed tests it has nowhere else
   to put. Precedent is stronger than the letter here: `be5258d` (WP-0.2g)
   modified `mag/src/parity.rs`, `mag/src/parity/display.rs` and
   `mag/src/parity/geometry.rs`, none of which were in its Owns
   (`mag/tests/parity_faults*`, `parity.yaml`), and was accepted. Not a ground
   for rejection; worth one line in a plan revision so the next comparator WP is
   told where its tests may live.
2. **Rule 1's own exception list is stale.** It exempts "a WP whose Owns names
   baseline.json explicitly (WP-0.2a: schema and empty state; WP-5.4g:
   cover-page seed rows)" and does not list WP-0.2k, while the WP section grants
   it. The WP section governs its own Owns; the list needs WP-0.2k added.

## What reproduced, by reproduction

Provenance for everything below: commit `b271911`, edition 010, staged-input
digest `e48eb5c638a0f25bfdfbb5e26bc989d56c1ecbac3ef85f103e90ed1ac8aac5fa`.
Render-identifying hashes are quoted as identifiers, never as values a reader
can re-derive: the WeasyPrint leg is not byte-reproducible (measured again
here).

### 1. The seed

`baseline.json` itself carries `staged_input_digest: e48eb5c6...` and
`seeded_at_commit: 20adcfb81cc866cd26870c5cac0623868c75c324`, not only the
evidence. Its `pages` object holds **54 entries, keys 2..55, contiguous**
(re-derived: `ks == list(range(min, max+1))`), and the set of distinct
`(tier, clauses)` pairs across all 54 is exactly `{("none", ())}`.

The digest reproduced **three ways**, the third independent of both the
comparator and the evidence's Python:

| route | result |
|---|---|
| `mag parity 010 --oracle-only` in a fresh worktree, fresh render | `staged inputs: fresh (e48eb5c6...)` |
| the evidence's Python re-derivation from `request.json` | `e48eb5c6...`, `agree: True`, 57 inputs |
| mine: `shasum -a 256` + `sort` + `awk` over the same rows, no Python, no Rust | `e48eb5c6...` |

The third route re-derives the digest FUNCTION independently (`targetPath`,
`\x1f`, per-file sha256, sorted, joined by `\x1e`, hashed). It does **not**
independently derive the input SET: it reads the same `request.json` the
comparator wrote, so it cannot discriminate a staging bug that omits a file.
Nothing available to a verifier can, short of reimplementing `render.rs`.

It discriminates: appending one byte to one staged manuscript moves the digest
to `dc11b707a7a017bc001b4fce5c3c853fead9b49f504b0ca4d4ff6b50817e9fe0`, which is
**character-for-character the value the evidence records**, so my corpus and the
worker's are the same corpus.

The rebase argument re-derived at the point of citation (rule 9):
`git diff --name-only` gives **57**, **13** and **1** changed files across
`be5258d..20adcfb`, `20adcfb..62e665a`, `62e665a..8a03c1a`; intersecting each
with the 57 staged `sourcePath`s gives **empty** three times. I added the
interval the evidence does not check, `8a03c1a..b271911` (**6** files), also
empty, and the fresh run at `b271911` reporting `fresh` confirms it.

### 2. The two refusals

**The working tree against `HEAD` runs before staging, in every mode.**
Reproduced in `--pre-rendered`, the mode that stages nothing: its verdict
carries `ratchet: not_evaluated`, `committed_check: "checked"`,
`pages_committed: 54`, `pages_recorded: 54`.

**The end-to-end refusal is exercised here for the first time on a raised
entry, which closes two of the WP's "not proven" items.** The WP could not do
this: every seeded row is at the bottom rung, so `none` cannot be lowered and an
empty clause list cannot lose a clause, and `HEAD:baseline.json` is not
something a WP may rewrite to suit a test. I built a scratch git repository
(`prompts/`, `meta/verification/{parity.yaml,baseline.json}`, the vendored
fonts, one PDF) whose **`HEAD` carries page 10 at `V1` with
`["page_count","boxes","text"]`**, and ran the shipped binary against four
working-tree variants through `MAG_PARITY_BASELINE`:

| working tree at page 10 | exit | message |
|---|---|---|
| unchanged (`V1`, 3 clauses) | 0 | `ratchet: not_evaluated (54 committed entries checked, ...)` |
| tier lowered to `G2` | 1 | `lowers 1 committed baseline entries ... page 10: tier lowered from V1 to G2` |
| clause `text` dropped | 1 | `lowers 1 committed baseline entries ... page 10: Tier S clauses dropped: text` |
| raised to `E` plus a clause | 0 | accepted |

So the tier-lowering and clause-drop branches are no longer unit-tested only.
The committed `mag/tests/parity_ratchet.rs` announces its mode per rule 2b and
in my replay printed `MODE: full, 54 committed page entries, exercising page 10
at tier none` and `MODE: tier-lowering not exercised, page 10 is at the bottom
rung`, which is the honest disclosure this closes.

**The comparator genuinely cannot write `baseline.json`.** Checked two ways, not
by absence of evidence. (a) Enumeration of every write site under
`mag/src/parity*`: `write_proposal` -> `<out_dir>/baseline-proposed.json`,
`write_verdict` -> `<out_dir>/verdict.json`, `store_oracle` ->
`<out_dir>/oracle-cache.json`, `hold` -> `<out_dir>/run.lock`, `report::write`
-> `<out_dir>/report.html` and `<out_dir>/report/`, and a raster scratch bitmap;
`baseline_path()` appears only on read paths. (b) Empirically, a run with
`MAG_PARITY_OUT_DIR=meta/verification`, the directory holding the file: exit 0,
`baseline.json` sha256 `ee366c97df803fb4...` **before and after**, and the run
left `verdict.json`, `report.html`, `report/` and `oracle-cache.json` beside it
(moved aside afterwards; `git status --porcelain -- meta/verification` back to
0 entries). The filename it would write is `baseline-proposed.json`, which is
not the file the ratchet reads under any setting of either environment
variable.

### 3. Stale corpus: fails now, reported before

Both halves reproduced, on the same one-byte perturbation.

| binary | bare | `--oracle-only` | `--oracle-only --set body` |
|---|---|---|---|
| `b271911` | exit **1**, no verdict | exit **1**, no verdict | exit **1**, no verdict |
| `be5258d` | - | exit **0**, verdict written | - |

At `b271911` each refusal names both digests (`run dc11b707...`, `baseline
e48eb5c6...`) and the only file in the output directory afterwards is
`oracle-cache.json`. **Three refusals promised by the caption, three counted**
(the block passes flags through a function taking `"$@"`; the zsh
word-splitting defect the evidence describes is genuinely fixed, and I hit the
same zsh trap myself in an unrelated helper during this verification, which is
independent confirmation that it is the shell and not the author).

At `be5258d`, the same stale corpus gives `base binary exit: 0`, a written
verdict, `page sets: refused (staged inputs differ from the baseline digest;
page sets not derived)` on stdout and `"page_sets_refused"` in the verdict.
**WP-0.2g's Residual 1 is discharged and its code was correct**; the defect was
the run continuing. Per rule 3b that behaviour is live on the branch for anyone
running a pre-`b271911` binary, and removing the now-unreachable field under
this commit is right: with an unconditional refusal there is no state in which
page sets are refused and the run goes on, so the field could only ever be
`null`. A tripwire in its place would fire on a state the code can no longer
enter.

### 4. Concurrency, by running it

`cargo test --test parity_concurrent`: **2 passed, 0 failed**, 6.96 s. Three
rounds each of the three live configurations:

| configuration | rounds 1-3 |
|---|---|
| `be5258d`, one hard-coded out dir | A-vs-A printed `pass` and A-vs-B printed `fail` every round; the single `verdict.json` held **fail, fail, fail** |
| `b271911`, one shared out dir | exactly **1** of 2 refused by name every round; `run.lock` left behind: **none** |
| `b271911`, one out dir each | A-vs-A exit 0 verdict `pass`, A-vs-B exit 1 verdict `fail`, every round |

My column for the base commit is `fail, fail, fail` where the worker measured
`fail, pass, fail` and its own replay measured `fail, fail, fail`. That is the
third independent measurement and it confirms the stated invariant rather than
the column: **one of the two runs always digests a verdict that is not its own,
and which one is not stable.** A reader must not take the column as a rule.

### 5. The suite, re-derived from its enumeration (rule 9)

`cargo fmt --check` clean, `cargo clippy --all-targets -- -D warnings` clean,
`cargo test` green. **22 test binaries**, counted by `grep -c '^test result'`,
with `96, 3, 12, 9, 9, 6, 5, 1, 4, 3, 6, 8, 3, 4, 1, 2, 1, 1, 4, 13, 2, 5`
passing and `0 failed` in all 22. Summed from that list, not carried beside it:
96+3+12+9+9+6+5+1+4+3+6+8+3+4+1+2+1+1+4+13+2+5 = **198**. The evidence's list
and total agree digit for digit.

Ratchet tests: `parity_ratchet` 1 passed, `ratchet_rules` 4 passed,
`measured_pages` 3 passed, each run as its own command so no runner truncation
hides a second failure.

### 6. Corpus figures, and what a verdict digest is worth

From my own renders at `b271911` (observations, not thresholds): 56 pages, 54
interior compared, **162** boxes / **54** rotations, **1733** colour entries,
**85** annotations of which **85** links, **68530** glyphs / **1501** shows,
page sets `body 34, code 0, furniture 54, openers 9, placement 11`. Every one
matches the evidence's table exactly, from a different render in a different
worktree, which independently supports revision 54's finding that corpus figures
do not move with the render.

Verdict digests, mine, quoted as identifiers: `--pre-rendered OLD OLD` gave
`e16aad0137e550cc` twice; `--pre-rendered OLD NEW` gave `74e96bca2cf33a2d`
twice. Neither equals the evidence's `dc5d3a2772a6d577` and `9c871ef1aa37fe7a`,
**and that is the predicted outcome, not a discrepancy**: the two reader hashes
in each verdict are `d52dae60db88fc19cc07` (leg A) and `4864ef9807e445f24c7b`
(leg B), two independent WeasyPrint renders of identical staged inputs, whose
bytes differ. What reproduces is pairwise determinism, every clause outcome and
every cardinality, and all three did.

## The self-comparison refusal: what holds, and what actually holds it

This was the brief's central question, and the answer has two halves.

**The refusal holds against every ordinary route.** I enumerated the whole CLI
surface (`mag/src/main.rs`: `--pre-rendered`, `--run`, `--oracle-only`, `--set`,
and nothing else) and could not construct a mode with two directories and a
digest:

- `--pre-rendered` returns from `stage_legs` with `digest: None`, verified from
  a real verdict: the emitted keys are `edition, mode, staleness, ratchet,
  self_comparison, inputs, domain, tier_s, tier_g, tier_v, tier_e`, with **no
  `staged_input_digest` key at all** and `staleness: not_staged`. The whole
  measure-and-propose block sits inside `if let Some(digest) = legs.digest`, so
  this mode cannot propose an entry whatever the two directories hold.
- `--oracle-only` passes `oracle.clone()` as both legs, one directory, so the
  two hashes are equal by construction: verified from a real run printing
  `self-comparison: both legs hash identically (deliberate for this mode)`,
  `ratchet: self_comparison`, `pages_measured: 0`, and **no
  `baseline-proposed.json` written**.
- Leg B's engine is the literal `"typst"` in `render_leg`, and `parse_engine`
  accepts only `weasyprint` or `typst`; `magazine.toml [render] engine` is
  consulted only when the flag is `None`, which it never is here. There is no
  environment variable, config key or flag combination that makes leg B a second
  WeasyPrint render. `--pre-rendered` also wins over `--run` and
  `--oracle-only`, so no combination reaches a digest.
- A hand-crafted `oracle-cache.json` is accepted (the cache is trusted input and
  may point anywhere, including outside the repository) but only ever supplies
  ONE directory used for both legs, so it cannot separate the hashes.
- `MAG_PARITY_BASELINE` moves only the side being checked: pointed at a baseline
  carrying a different digest, the run refuses on staleness naming both digests,
  and the committed half raised nothing.

**But the thing that holds it is not the guard.** `self_comparison` is
`a_reader_sha256 == b_reader_sha256` (`parity.rs:1044`), a hash test, not a mode
test, and I measured what that costs. Applying the shipped ladder to my real
`--pre-rendered OLD NEW` verdict, where both legs are WeasyPrint renders of
identical staged inputs: `self_comparison: false`, every clause pass, Tier V max
channel delta 0, and **all 54 pages would score `E` with five clauses**. The
only thing that stopped a proposal being written was the absent digest.

**I then constructed the bypass and it succeeded.** In the probe worktree,
`mag parity 010 --oracle-only` against a cached render directory, while the
compared artifact `en/reader.pdf` was swapped between those same two
byte-different, content-identical renders during the run (112 atomic renames
over 12 s, then settled): the run printed **no** self-comparison line and
reported

```
proposed baseline: /tmp/vprobe-race/baseline-proposed.json
staged inputs: fresh (e48eb5c6...)
ratchet: pass (54 committed entries checked, 54 recorded, 54 measured, 0 regressions)
```

and the proposal it wrote holds **54 pages at `tier: E` with
`["page_count","boxes","text","color","navigation"]`**, carrying the correct
digest and `seeded_at_commit`, ready for a verifier to commit. That is exactly
the artefact the WP exists to make impossible, produced by a WeasyPrint-only
mode with no typst leg anywhere.

**Why this is not a rejection.** The route requires mutating the comparator's
own input between its two reads of it. An agent able to do that can equally swap
a doctored PDF into both legs and make any clause pass, so it is not a boundary
this comparator defends or could defend, and no ordinary or accidental
operation produces it: render directories are timestamped and never reused, and
the `run.lock` this WP adds removes the one case where two runs shared a
directory. Judged as what it is: a faithful simulation, without any code change,
of the configuration the WP's own **Residual 3 recommends** (`--oracle-only`
rendering two independent oracle legs). Revision 55 already records the
dependency in the plan; this adds the measurement, which changes its status from
"the hash test would fail for exactly this case" to "here is the 54-page Tier E
proposal it writes".

**Should the guard be a mode test beside the hash test? Yes.** Three reasons,
and the first is decisive. The refusal is load-bearing in `legs.digest`, two
call sites away from anything named after it, so a future WP adding a digest to
`--pre-rendered` (which WP-0.2l's staging change makes newly attractive, since
it would then have inputs to hash) reopens it with no test failing. Second, the
WP's own residual recommends the shape that opens it, so the hazard is not
hypothetical but scheduled. Third, the mode is already in hand at the point of
the check: `Legs.mode` distinguishes `render` from `oracle_only`,
`typst_leg_failed` and `pre_rendered`, so `measure_pages` gating on
`mode == "render"` in addition to `!self_comparison` costs one condition and
makes the guard say what it means. Recommended as a plan item, not demanded of
this WP: it is a tightening, `mag/src/parity.rs` is comparator territory under
rule 1c, and rejecting a landed WP to add a condition against a state nothing
can currently reach would delay Phase 3 for no live defect. **The belt is
correct today; the braces are missing and the plan should schedule them before
any WP changes `--oracle-only` or gives `--pre-rendered` a digest.**

## The three disclosed findings, assessed

**1. Two WeasyPrint renders of identical inputs differ in bytes.** Confirmed
independently: `d52dae60db88fc19cc07` against `4864ef9807e445f24c7b`, equal at
Tier S text and colour, Tier E display list, Tier G at 0.000 pt and Tier V at
max channel delta 0. **The provenance audit's recommendation still works, with
its promise corrected.** Printing the `inputs` block beside the digest was
always doing two different jobs: the two reader hashes IDENTIFY the artifacts a
verdict compared, which is what detects a crossed-over verdict and is the audit's
actual use, and that job is unaffected. What it cannot do is let a reader
re-derive those hashes by rendering again. The digest is the half that
reproduces (three routes above) and it pins the corpus; the reader hashes pin
the run and must be quoted as identifiers. So: keep the habit, and never write
"reproduces" next to a WeasyPrint leg hash.

**2. The digest does not cover the renderer.** Confirmed by experiment, and
worse than the evidence's phrasing suggests. Appending
`p { letter-spacing: 0.37pt; }` to `src/magazine/assets/weasyprint-a5.css` and
re-rendering gave `staged inputs: fresh (e48eb5c6...)`, the same digest, while
the render changed enough to move the **page count from 56 to 60**, which a
cross-comparison of the two renders reports as `tier S page_count: fail (56 vs
60)`. So a renderer change that adds four pages to the edition leaves the
staleness guard entirely silent, and every recorded per-page tier would be
compared against pages that no longer exist. This is serious in a scheduled way
rather than a theoretical one: WP-1.5 has already changed that stylesheet once
as a sanctioned oracle change and WP-4.3 is required to change it again after
the flip. The evidence's mitigation, "a WP that changes the stylesheet must
reseed the baseline by hand", is prose of exactly the kind rule 6b says nobody
reads. Revision 55 promoted it from a residual to **WP-0.2l**, owned by the
staging path in `render.rs`, which is the right response; the measurement above
is offered as its severity evidence, and WP-0.2l should treat the fonts the same
way as the stylesheet. (Stylesheet restored with `git show HEAD:<path> >
<path>`; `git status --porcelain -- src` back to 0.)

**3. The run-against-baseline half has never compared real 010 pages.**
Accepted as adequate for now, with the reason stated rather than assumed. The
unit-level discrimination is genuine and per-perturbation, not a single
end-to-end green: one perturbation at a time takes page 3 from `E` to `V2` (a
display-list diff), to `V1` (raster fraction 0.005), to `G1` (`max_dy_pt` 1.0)
and to `none` (a line-count mismatch) while leaving page 2 at `E`; a text
difference removes only `text` from page 3's clause list; a navigation failure
strips `navigation` from every page; a glyph failure caps every page at `V2`.
That is a stronger demonstration than a live run of a corpus where everything
passes would have been, because a self-comparison exercises exactly one point of
the ladder. What remains untested is the wiring between the real verdict and
those functions, and a live run cannot test it until two legs differ. WP-3.1
owns it and should expect to debug the mechanism as well as the result; note
that at the branch tip WP-2.2a has landed a typst leg that renders, so the
`render` mode with two genuinely differing legs is reachable now, and WP-3.1's
evidence should record the first non-`none` proposal.

## Where this WP fell short of its brief, and why it is not disqualifying

**Target 4's cardinality sweep is not implemented, and the evidence does not say
so accurately.** The WP section requires "Extend cardinality reporting to every
Tier S collection clause per rule 10a", and revision 47 amended it to "report one
number only when the legs agree, and both when they differ", saying "WP-0.2k is
implementing the sweep as this lands". The evidence's whole treatment is one
sentence, "Rule 10a's both-legs form does not arise here: this WP adds no clause
cardinality", which answers a narrower question than the one asked. Measured:
`boxes` (`boxes_compared: a.boxes.len()`), `color` (`entries_compared`),
`navigation` (`annots_compared` and four more) and the glyph clause all still
report **leg A only**, so the amended both-legs form is not present anywhere.
Mitigating, and the reason this is not a rejection: rule 10a's enumeration of
what remained for this WP is "code blocks, figures and extracts", and `code_blocks`
is `not_evaluated` with its owner named (`WP-0.2b input level, WP-3.3 fixture`)
while **`figures` and `extracts` clauses do not exist in `TierS` at all** - a
clause that does not exist cannot report a cardinality. The fields that would
have to change for the both-legs form live in `mag/src/parity/display.rs` and
`mag/src/parity/geometry.rs`, **neither of which is in this WP's Owns**, so
implementing it would have required exactly the self-granted Owns extension rule
1 forbids. The same contradiction retires the other stranded item: the WP
section also asks it to fix `mag/src/parity/raster.rs:106`, in a file it does not
own, which it correctly declined and recorded as Residual 5.

So the WP is right to have left both, and right not to self-grant; what it owes
is the accurate sentence. **The plan owes a revision**: a WP section that asks
for changes in files its Owns excludes will strand those targets every time, and
the sweep needs either an Owns extension or a new comparator WP.

The same evidence is unusually good at the harder part of this discipline
elsewhere: it volunteers that the `Drop`-based lock release was rejected by
`mag/tests/rust_helpers.rs` and that it did not self-grant an exception, it
marks the unstable concurrency column as not a property, and its "not proven"
list names an owner for every item.

## What I could not discriminate (rule 10)

- **The staged input SET.** My third-route digest re-derivation reads the
  comparator's own `request.json`. If staging omitted a file that influences the
  render, all three routes would agree on a digest over 57 rows and none of them
  would notice. Only a reimplementation of `render.rs` staging would, and
  Residual 1 / WP-0.2l is the same hole seen from the other side.
- **Whether the per-page tier assignment is right for a real engine pair.** No
  such pair existed at `b271911`. I verified the ladder function against
  synthetic verdicts and against one real verdict by reimplementing it in Python
  (54 pages at `E` for a WeasyPrint pair, which is the correct answer for two
  identical-content renders and tells us nothing about a typst leg).
- **Whether `run.lock` survives every death.** Not attempted. The evidence
  states it does not survive `SIGKILL` and that the next run names the file; I
  did not test kill paths.
- **The `be5258d` concurrency column.** Three measurements now exist and they
  disagree by design; nobody can discriminate which run wins a race, and no
  reader should try.

## Findings for the plan

1. **Make the self-comparison guard a mode test beside the hash test** before
   any WP changes `--oracle-only`'s meaning (its own Residual 3) or gives
   `--pre-rendered` a digest (plausible once WP-0.2l stages the renderer). The
   54-page Tier E proposal above is what the current guard permits when the two
   reads differ.
2. **WP-0.2l should cover the fonts as well as the stylesheet**, and its
   severity is a 56-to-60 page swing with the digest reporting `fresh`.
3. **The digest half of the baseline is not ratcheted.** `guard_baseline`
   compares page entries against `HEAD` and says nothing about
   `staged_input_digest`, so a working tree may move the reference freely and
   only the orchestrator's rule-1 diff check stops it landing. Cheap hardening:
   report in the verdict when the working-tree digest differs from `HEAD`'s.
4. **Rule 1's baseline exception list should name WP-0.2k**, and the plan should
   say where a comparator WP's tests may live.
5. **A WP section must not ask for changes in files its Owns excludes.** Two of
   Target 4's three items were unreachable for that reason.

## Verdict

**ACCEPTED.** Reproduced from worktrees the work was not done in: the seed and
its digest by three routes, the mode-by-mode guard behaviour off real verdicts,
the stale-corpus refusal in all three staged modes against the base commit's
exit-0 report, the discharge of WP-0.2g's Residual 1, the concurrency fix under
real concurrency, 22 binaries and 198 tests re-derived from their enumeration,
and every corpus cardinality to the digit. Two of the WP's own unproven items
are closed here by execution. The one bypass I constructed requires mutating the
compared artifact mid-run, is not reachable by any ordinary use of the shipped
CLI, and is recorded as the measurement behind an already-agreed hardening
rather than as a live defect.

**Phase 3 can start.**
