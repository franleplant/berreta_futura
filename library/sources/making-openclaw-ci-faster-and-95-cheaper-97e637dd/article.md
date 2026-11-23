# Making CI faster and 95% cheaper

By Vincent Koc · November 17, 2026

Tests were slowing our coding agents down. We cut weekly runner-hours by 86.5% and the estimated value of that compute by 95.5%.

When I first talked about the dark factory—agents building software with other agents—people laughed. More people are now using agents this way. Ours ran into a different limit: not tokens, memory or disk, but tests.

Agents were producing code faster. They were also producing more tests, more jobs and more retries. Work piled up while we waited for checks to show that changes were safe to ship. We had a hard deadline to reduce how much compute we needed.

About **89% of our code is TypeScript**.[1](https://vincent.build/openclaw-ci-cost-reduction/#note-1) That is where I began with faster tools and adaptive testing. The broader lessons—remove weak tests, balance work and stop repeating setup—apply across languages.

Our Blacksmith runners logged **158,546 hours** in the September peak week and **21,395 hours** in the latest week: **86.5% less runtime**. The estimated value of that compute fell **95.5%**. Blacksmith sponsored the capacity—we did not pay those dollar amounts. The workload also changed, so neither reduction belongs to one fix. Here is what we changed: fewer pointless checks, better use of each machine and tests that adapt.

### Try this with your agent

Short on time? Send your agent this page and the [OpenClaw CI implementation](https://github.com/openclaw/openclaw/blob/a7d05c7af04aa17ac57c994da238d0c60f058ca6/.github/workflows/ci.yml), then give it this prompt:

```
Read https://vincent.build/openclaw-ci-cost-reduction/ and its linked OpenClaw CI implementation. Audit this repository’s CI and measure a baseline. Propose the highest-value changes, then implement them in reviewable steps. Preserve required checks; run the full suite when affected-test selection is uncertain. Verify correctness, feedback time and compute cost. Don’t assume OpenClaw’s tools or results transfer unchanged.
```

## Who runs the tests, and what we measured

GitHub Actions coordinates the work: which jobs run, their dependencies and their results. A runner is the machine doing that work. We use [Blacksmith](https://www.blacksmith.sh/) (and more recently, [boat.dev](https://boat.dev/)) to supply those runners on top of GitHub Actions.

Thank you to [GitHub](https://github.com/) for supporting OpenClaw with donated CI runners and a GitHub Enterprise plan.

Blacksmith sponsors these runners. Thank you to their team for making this work possible.

### What ran on those machines

| Weekly usage | 17–23 September | 6–13 November |
|---|---|---|
| Runner-hours | 158,546 | 21,395 |
| Jobs | 1,482,257 | 301,413 |
| Jobs per hour, average | 8,823 | 1,794 |
| Equivalent runners busy all week | 944 | 127 |

That is **86.5% fewer runner-hours** and **79.7% fewer jobs**. The September total is enough runtime to keep **944 runners busy around the clock** for a week; the latest total is equivalent to **127**. That is runner-hours divided by the 168 hours in each week, not peak concurrency. Runner sizes varied.

For another measure of scale, the main repository’s PR-triggered `CI` workflow ran **19,660 times** during 17–23 September—about **117 workflow runs an hour**. A workflow can fan out into many jobs. That count covers one workflow in one repository; the Blacksmith totals above cover all repositories on the account.

All repositories on our Blacksmith account; all outcomes. Heaviest: 17 Sep 00:00–24 Sep 00:00 UTC. Latest: 6 Nov 09:00–13 Nov 09:00 UTC. Hours rounded from recorded runtime minutes. The workload changed between weeks; this is not the same work replayed on two CI setups. [Source arithmetic](https://vincent.build/openclaw-ci-cost-reduction/#ledger).

Activity fell too: indexed commits in the main repository were about **44% lower** across the comparison weeks (3,850 → 2,149). That is one repository against organization-wide cost, with slightly different daily boundaries, so it is context—not a saving measured at equal activity levels. [Counting method](https://vincent.build/openclaw-ci-cost-reduction/#throughput-notes).

At Blacksmith’s published prices, keeping up the September week’s usage for 30 days would mean **$1.27 million worth of compute**. At the latest week’s usage, it would be **$57,324**[2](https://vincent.build/openclaw-ci-cost-reduction/#note-2).

A faster runner is useful, but it cannot fix poorly divided work. If each job spends most of its time preparing to run, buying faster execution tackles the smaller part of the problem. Our next step was to look at what we were asking those machines to do.

The workload changed over this period too. The chart measures the combined result, not a saving we can assign to each fix. We also need to know how quickly changes get checked, reviewed and merged.

The methods below are not tied to Blacksmith. We used its runners, but removing duplicate work, choosing relevant tests, reusing setup and balancing jobs apply to hosted runners and machines you operate yourself. The TypeScript examples show where we started, not where the ideas stop.

## The goal: finish changes sooner

I call this measure **agent cycle time: PR creation to merge**. It measures elapsed time for work done with agents, not every aspect of software quality.

Writing the patch is only part of that interval. A PR can wait for a runner, install the same dependencies again, run an oversized suite, fail, get fixed and repeat. Review adds another wait. If another agent needs that change, that agent has to wait too.

We have one objective: **finish useful work sooner, with less compute wasted along the way**. The first question is whether the work needs to run at all. Only then should we optimize the work that remains. A cheaper machine is not a win if it makes every dependent agent wait much longer. A faster machine is not a win if most of it sits idle.

Removing unnecessary work can improve both. The job that never needed to start costs nothing and holds nobody up.

Every optimization needs a tradeoff check. Making a runner cheaper can make people—and other agents—wait longer. Adding parallel jobs can shorten the wait while repeating setup and increasing the estimated cost. Removing unnecessary work can improve both, but only if it really is unnecessary and sits on the path to an answer. Deleting code is not proof that the system got better.

Start by removing unnecessary work, then measure what remains. Keep the behavior we need to protect, compare equivalent jobs, and look at cost and waiting time together.

The reduction in estimated compute value is measured; the PR-to-merge improvement is not yet established here. Lower estimated costs alone do not prove that more changes get finished. That needs comparable delivery and work-volume measurements, not just a count of commits. [Measurement notes](https://vincent.build/openclaw-ci-cost-reduction/#throughput-notes).

### What we changed

1. [Delete the waste before optimizing it.](https://vincent.build/openclaw-ci-cost-reduction/#cleanup) Make every test earn its place.
2. [Run checks at the right stage.](https://vincent.build/openclaw-ci-cost-reduction/#foreground-background)
3. [Stop paying for the same review twice.](https://vincent.build/openclaw-ci-cost-reduction/#review) Give repeat reviews a reason to run.
4. [Test what changed.](https://vincent.build/openclaw-ci-cost-reduction/#selection)
5. [Catch cheap failures locally.](https://vincent.build/openclaw-ci-cost-reduction/#local-checks) Use faster tools on the checks authors wait for.
6. [Stop rebuilding the same environment.](https://vincent.build/openclaw-ci-cost-reduction/#setup) Fetch less, restore caches and reuse safe setup.
7. [Pack, balance and size the remaining work.](https://vincent.build/openclaw-ci-cost-reduction/#runner) Optimize useful work, not job count.

## 1. Delete the waste before optimizing it

A test is useful when it catches a mistake we care about. More test code is not automatically more protection. My starting assumption in an agent-grown suite is that most tiny, implementation-mirroring unit tests are noise until they can demonstrate an independent contract. By noise I mean tests that restate the implementation, fail during harmless refactors, or stay green when the behavior they claim to protect is broken.

Models are very good at adding code. My reading: adding a test looks thorough; deleting one means showing that nothing useful is lost. Ask for a fix and it is easy to get another fixture, another mock and five assertions for behavior another suite already proves. Deletion needs an explicit instruction and a place in the definition of done. Otherwise the suite keeps growing even when the product barely changes.

Make every test earn its place before buying it a faster machine. Speeding up noise leaves the maintenance problem intact.

Our cleanup worked one subsystem at a time. Read the production code and its tests. Name the contract. Find the strongest test that proves it. Only then remove duplication—or repair a test that proves nothing.

### Set a limit on test-code growth

We put that pressure into a guard, not just a prompt. The original test-line ratchet told an over-budget change to **“Offset the added lines by deleting or consolidating tests elsewhere”**, or justify a higher ceiling. The rule was: once the suite is at its ceiling, further test lines must be offset by deletion or consolidation, or the ceiling must be raised with a stated justification. That was the 24 October guard. It is a limit on the amount of test code, not a reason to delete useful product code or the only regression test.

The rule evolved. By the 13 November checkpoint, the per-change policy allows **400 net new test lines** without an allocation record; larger additions need a recorded, justified allowance. So it is not a blanket one-line-in, one-line-out rule. The principle survives: make growth visible, make exceptions explicit, and reward consolidation. [Original guard](https://github.com/openclaw/openclaw/pull/182230) · [Versioned budget](https://github.com/openclaw/openclaw/blob/a7d05c7af04aa17ac57c994da238d0c60f058ca6/docs/ci/local-proof.md#test-line-budget).

### After the cleanup, how much core code is tests?

Focus on OpenClaw’s core, not every app and extension in the repository. At the article’s 13 November checkpoint, test files account for **56.5%** of counted core code. Test support adds **6.7%**, taking the combined share to **63.2%**. The remaining **36.8%** is implementation.

The share did not rise all the way through. Tests and support peaked at **68.9%** on 28 September, then fell to **63.2%** by 13 November. Move across the chart to compare tests and support with implementation.

**The cleanup is visible in the counts.** Between 28 September and 13 November, test files fell from 4,289,556 to 3,871,650 lines: **417,906 fewer lines net**. Test support grew by 137,366 lines, so tests plus support fell by 280,540. Implementation grew by 444,121 lines, which also lowered the test share. These are net changes between snapshots—not a count of every deletion, or savings attributed to one cleanup.

The test/spec category is not labelled “unit tests”: a file called `something.test.ts` can exercise a whole component. A full-release run also executes many of these same files; it is not an extra category of code. The chart measures the maintenance surface, not how much is waste or should be deleted.

Peter’s reported cleanup, not a reconstructed test-LOC series. [Open on X ↗](https://x.com/steipete/status/2103147927313199260)

The test-audit rule is simple: name the behavior a test protects, show a believable bug that would make it fail, and keep one strong owner for that contract.

In one cleanup, a test checked that a result was a correctly formatted SHA-256 value, then separately checked that it did not contain the word `synthetic`. The format already ruled that word out. We removed the second assertion and kept the independent disclosure check. Deliberately breaking the code confirmed that the remaining guard still caught the bug. [PR #191917](https://github.com/openclaw/openclaw/pull/191917).

All 12 test cases stayed. We removed duplicate work inside a test, not its independent protection.

### A cleanup goal you can reuse

Adapted from the cleanup goals I used for `libopus-wasm` and `libterminal`. It directs a repository-wide campaign, not a one-off audit or a superficial cleanup PR. Narrow PRs keep the work reviewable; the ledger keeps the agent moving through the whole scope.

```
/goal Run a sustained cleanup campaign across this repository's tests. Make every retained test earn its execution and maintenance cost.

Read each subsystem's production code before its tests. Identify the behavior contracts and realistic regressions worth protecting. Remove obsolete tests, implementation-mirroring assertions, duplicate coverage, unused fixtures and unnecessary mocks. Consolidate overlapping tests around the strongest behavior checks. Repair valuable flaky tests instead of preserving their retry tax.

Treat deletions and consolidation as first-class deliverables. Follow the repository’s test-line budget; justify genuinely new coverage rather than padding a replacement suite. Never offset growth by deleting an independent safety contract.

Do not stop after easy deletions or a small first PR. Work through every in-scope subsystem. Keep a ledger of completed areas, removed duplication, remaining contract coverage and unresolved risks; resume from it until the campaign is complete. Do not chase a deletion percentage or add replacement tests just to keep the count up.

For each change, run the affected checks and demonstrate that the retained test fails for the relevant broken behavior when practical. Never delete the only useful regression guard to make a failure disappear. Keep platform and integration boundaries that protect distinct behavior.

Validate and land narrow PRs within the repository's existing review and merge rules. Continue until every in-scope area is checked or has a precise blocker. No releases.
```

This is why the cleanup starts by reading the implementation, not sorting tests by runtime and deleting the slowest. Two similar-looking tests may protect different behavior; a very fast test may protect nothing useful. The question is what would break without it, and which remaining test would catch that break.

## 2. Put each check at the right stage

Not every check has to hold a PR open. We separated **the answer needed to merge this change** from **the broader proof needed to ship a release**.

### Stop starting work that will be superseded

A busy agent can push the next revision before the previous one finishes starting. The old run gets cancelled; the new run repeats setup. Those cancelled runs used compute without producing a useful result.

Earlier in the campaign, the full main-push path gained a 90-second admission delay: a superseding push could cancel it before a Blacksmith runner started. That optimization preceded the separation of full validation from every main push. It was not a delay on PR feedback. [The change](https://github.com/openclaw/openclaw/pull/95681).

We also moved main’s CodeQL analysis to an **hourly** schedule. A successful, unchanged category could reuse its result for up to 24 hours; changed, stale, failed or incomplete categories ran again. PR and manual security checks stayed. [Scheduling](https://github.com/openclaw/openclaw/pull/191097) · [Reuse rules](https://github.com/openclaw/openclaw/pull/191805).

Moving a check changes when its answer is needed; it should not make a required answer optional.

### Stop the job before paying for its setup

A skip is worth more before the runner starts. The examples below trace six real workflow changes: a gate at the job condition avoids allocation and setup; a late check can only avoid the work after it. Put the decision at the earliest stage that has enough information to make it correctly.

### Do not rerun the full suite after every merge

The full suite does not need to restart after every commit lands on main. The versioned workflow separates three jobs: give the PR its required answer before merge, run small guards on each main push, and let a scheduled worker check broader combinations on a named revision.

Broader main validation runs hourly; full release validation has its own schedule. Full CI on every main push is opt-in in the source. [Exact workflow and switch](https://vincent.build/openclaw-ci-cost-reduction/#main-policy-source).

A background worker needs a clear obligation: qualify a named revision, retain its results, and report failures to whoever can repair them. Do not silently treat an old green run as proof for a newer commit. Keep release gates attached to the version being shipped. That is the operational work required to move tests out of the author's immediate wait.

We did not turn every background job into optional work. My rollout check was that releases did not suffer and full E2E runs did not reveal a new pattern of repeated regressions. That is an operational assessment, not a measured defect-rate claim.

**Source and configuration detail**

At the article’s source revision, `OPENCLAW_CI_ON_PUSH=true` enables the full main-push path. The workflow retains small main-push guards, schedules main CI hourly, and schedules full release validation separately. This describes the versioned design; the live repository-variable value was not available to this audit. [CI source](https://github.com/openclaw/openclaw/blob/a7d05c7af04aa17ac57c994da238d0c60f058ca6/.github/workflows/ci.yml) · [Release validation source](https://github.com/openclaw/openclaw/blob/a7d05c7af04aa17ac57c994da238d0c60f058ca6/.github/workflows/full-release-validation-nightly.yml).

## 3. Stop paying for the same review twice

[ClawSweeper](https://github.com/openclaw/clawsweeper#readme) is OpenClaw's automated maintenance and code-review bot. It reviews pull requests and reports findings so contributors and maintainers can act on them. It is another consumer of compute and attention, not a free step outside the delivery process.

ClawSweeper gives a new PR **one automatic review**. Follow-up reviews are requested, rather than automatically repeating the entire review after every push. Use a new review when the patch is ready for another pass or when a change needs fresh scrutiny; a request is not itself a passing review.

Its [local-review CLI](https://github.com/openclaw/clawsweeper#local-run) lets us inspect a branch on our own machines without allocating an Actions runner. The standalone [AutoReview skill](https://github.com/openclaw/agent-skills/tree/main/skills/autoreview) offers another local review workflow. Local describes where the tooling runs, not an offline model: both use their configured model service.

For a clean, committed branch, run this from a built ClawSweeper checkout, replacing the repository and path:

```
pnpm run review -- --local-range \
  --target-repo owner/repo --target-dir ../your-repo \
  --base origin/main
```

Or, with AutoReview installed, run from the repository you want reviewed:

```
python3 "$HOME/.agents/skills/autoreview/scripts/autoreview" \
  --mode branch --base origin/main
```

The useful saving is avoiding redundant review starts and repeated findings while an author is still editing. Required CI, security checks and repository review rules remain. We did not move every review off CI, and no isolated review-cost percentage is claimed here.

## 4. Test the change, not the entire repository

Adaptive testing is the next step after cleanup: choose the remaining work from the change itself. Start with explicit ownership and dependencies. A changed test runs; a known production owner selects its related tests; shared, dynamic or uncertain paths widen the selection. A missing dependency record is a reason to run more, not evidence that nothing can break.

For our TypeScript-heavy repository, we began with the changed files, their owners and the code importing them. A change to one component should not automatically start tests for every unrelated component and platform.

For example, change a shared retry helper. Its own tests matter. So do tests of callers that import it. An unrelated UI component should not become relevant merely because it lives in the same repository. If we cannot establish the boundary safely, we run more.

Adaptive testing selects relevant tests, but smaller runs alone don’t prove complete coverage.

### Keep selection boring, deterministic and testable

We deliberately did not make this a complex AI scheduling system. Some teams use learned models or LLMs to choose tests. Our live path is ordinary code: the same revision, diff and rules produce the same selection. Every selected test should have a reason you can inspect. A model’s confidence is not a substitute for a dependency.

**Backtest the selector against regressions.** Take an earlier bug, restore the revision before its fix, and replay the change through the selector. Check whether it includes the test that exposes the bug, then run that test and verify the expected failure. Include deleted files, shared helpers, fixtures and renamed modules—not just easy sibling-test examples. A missed regression is a rule to repair or a reason to widen the fallback. This is a repeatable validation recipe, not a claim that we have replayed every historical bug.

### How we wired adaptive testing into CI

The implementation is a planner in front of the existing test runner. It turns a Git diff into a list of existing test files, then gives those files to their normal execution jobs.

**1. Start with an exact diff.** CI supplies the changed paths and comparison revision. Keep additions, deletions and rename information: removing a module can break its callers too. The planner also reads the current checkout and test inventory. A previous run’s dependency list is not a substitute for the code being tested now.

**2. Find the owning tests, then the callers.** In `test-projects.test-support.mts`, we map known inputs to explicit test owners, look for sibling and directory tests, and follow reverse imports to tests that consume the changed code. Package aliases are resolved as well. The aggressive PR policy bounds how far some searches go; it is not an unlimited walk through the repository. Changes to mocked exports have extra rules to retain affected mock consumers.

This is where the `retry.ts` example becomes real: select `retry.test.ts` because it owns the helper, and `send.test.ts` because its code consumes that helper. But an import graph cannot see every dependency. A test that reads a JSON fixture from disk needs an explicit owner rule or a recorded file dependency. “No import found” alone is not a reason to skip it.

**3. Add the checks the diff does not get to remove.** `ci-changed-node-test-plan.mts` combines the result with the applicable policy checks and fixed smoke tests. Changed tests remain eligible to run. Tests with protected owners follow their own rules. The small unchanged-input shortcut described below applies only to reviewed Markdown tests in directory fallback—not to every test that passed last time.

**4. Hand the selection to the existing runner.** The CI planner matches each selected file to its canonical test configuration, then constructs jobs with the appropriate runtime, setup and build requirements. Selecting the same file under Node and Bun still represents two executions. Missing executable owners or shard metadata cause the narrowed plan to be rejected, not treated as an empty successful test run. Broader coverage remains the fallback.

**5. Make the decision inspectable.** The selector records reasons such as `explicit-owner`, `import-consumer`, `policy-watch` and `fixed-smoke`. That lets us trace a surprising selection back to a rule. We check those rules with focused selector tests and regression examples; for the recorded-dependency pilot, we also deliberately broke a fixture and verified that the affected test was selected and failed. A smaller green run, by itself, cannot prove that selection is correct.

For local feedback, the repository exposes a changed-test command. Its defaults are not identical to the canonical CI planner; use the broader fallback when investigating a change that needs it:

```
pnpm test:changed

# With broad fallback
OPENCLAW_TEST_CHANGED_BROAD=1 \
  pnpm test:changed
```

Rollout has a separate control: setting the repository variable `OPENCLAW_CI_NODE_SELECTION=full` disables aggressive PR selection and its Markdown shortcut. Main, scheduled and release coverage retain their separate policies. That gives us a way to back out of the optimization without rewriting the tests.

Implementation at the article’s source snapshot: [owner and import selection](https://github.com/openclaw/openclaw/blob/a7d05c7af04aa17ac57c994da238d0c60f058ca6/scripts/test-projects.test-support.mts#L4769) · [CI planning and retained checks](https://github.com/openclaw/openclaw/blob/a7d05c7af04aa17ac57c994da238d0c60f058ca6/scripts/lib/ci-changed-node-test-plan.mts#L436).

Three illustrative, completed PR runs show what selection can do. For each, we reconstructed the full inventory and compared it with the executed entries:

Each entry is **a test file in a particular configuration and runtime**.[3](https://vincent.build/openclaw-ci-cost-reduction/#note-3) These examples show work avoided, not dollars attributable to it.

We also repaired accidental fanout: a Windows test-list edit had been selecting unrelated SDK suites. Replaying that same input after the fix reduced selected targets from **2,962 to 181** and planned Node jobs from **105 to 21**. That was a boundary repair, not a new selection system. [Source](https://github.com/openclaw/openclaw/pull/195392).

### The November drop came after weeks of smaller changes

The graph below shows the timing, not a clean attribution experiment. Cleanup and runner changes had already accumulated when adaptive selection rolled out around 6–7 November. Estimated daily compute cost then fell from about **$7,738 on 5 November to $1,507 on 7 November**. Read that as the result of a changing system and workload—not a price tag for the selector alone.

| UTC date | Compute value | Billed jobs |
|---|---|---|
| 2026-10-29 | $9,157.57 | 61,475 |
| 2026-10-30 | $8,410.59 | 59,062 |
| 2026-10-31 | $7,223.41 | 62,740 |
| 2026-11-01 | $4,737.62 | 43,187 |
| 2026-11-02 | $7,868.07 | 50,050 |
| 2026-11-03 | $7,933.37 | 54,393 |
| 2026-11-04 | $6,366.45 | 52,425 |
| 2026-11-05 | $7,738.20 | 65,397 |
| 2026-11-06 | $5,064.25 | 46,823 |
| 2026-11-07 | $1,506.55 | 36,838 |
| 2026-11-08 | $1,382.27 | 40,378 |
| 2026-11-09 | $1,814.45 | 39,950 |
| 2026-11-10 | $2,454.47 | 58,206 |
| 2026-11-11 | $1,889.16 | 51,337 |
| 2026-11-12 | $1,531.01 | 40,428 |

Cleanup, runner sizing and shard packing had been accumulating since the summer. Some of the setup and tooling work in sections 5–7 landed after the rollout. The step is therefore not an isolated measure of adaptive testing.

Nor should we invent a neat “60% first, 35% later” waterfall. The estimated daily cost on 5 November was already about **81.7% below** the September peak’s average daily cost. These cover different periods; they do not isolate the effect of each change.

### What is implemented—and what still runs in shadow?

The source-based selector answers a concrete question: which tests can this change affect? That works only as well as the relationships we can observe. We also explored whether past runs could add useful information—particularly when the source graph alone was incomplete.

The first implementations are already merged. **Recording dependencies** means watching which code and files a test reads. **Learning a ranking** means using past changes and failures to predict which tests are most likely to fail on the next change. The first records a relationship; the second makes a prediction. Implementing both does not mean giving both permission to skip tests.

Sampled CI already records test outcomes and dependencies. When compatible history is available, it also freezes a graph proposal and model scores before execution—without changing the scheduled tests. A [new CLI audit collector](https://github.com/openclaw/openclaw/pull/198330) adds separate outcome evidence without changing selection or displacing the ordinary history. This already records and checks predictions; it does not yet use them to skip tests.

### Try the prediction without skipping the tests

Say a proposed model picks 20 tests from a group of 1,000. We save its list, then run all 1,000 anyway. If a failing test is absent from the list of 20, we have found a miss. This is **shadow mode**: evaluate what a shortcut would have done without letting it remove protection. It costs the full run while we learn whether the prediction is trustworthy.

[Mozilla’s Firefox work](https://hacks.mozilla.org/2020/07/testing-firefox-more-efficiently-with-machine-learning/) used historical failures and relationships between changed files and tests to train an XGBoost model. Its shadow schedulers gave us a useful way to test a proposed shortcut before trusting it.

Our experiments fed a small decision-tree model records of changed code, test dependencies and test outcomes. We trained on one set of examples, then checked new examples and entirely held-out code owners. A model doing well on familiar examples was not enough: some richer models missed regressions on held-out owners that the source graph caught.

The dependency recorder had its own failure. A test read a fixture straight from disk; the import graph never saw that file. We declared it with Vite’s `addWatchFile`, then deliberately broke the fixture to check that the test was selected and failed on Node and pinned Bun.

Next, we’re experimenting with learned test selection and improving how we measure what gets skipped—and whether failures still get caught.

### Beyond TypeScript: select the right language owner

Some unnecessary work came from crossing a language boundary for no reason. A TypeScript-only PR could start the independent Rust toolchain and workspace proof.

We now compare the exact PR revisions to the TypeScript and Rust input lists. If the change belongs only to TypeScript, the independent Rust proof does not start. Rust configuration and sidecar fixture changes still select Rust; shared, deleted, unknown or incomplete inputs keep both owners. Manual and scheduled validation keep their existing rules.

One recorded Rust job took **81 seconds**. That identifies work an eligible change can avoid; it is not an 81-second reduction in the time to finish the whole PR. [Rust owner-selection change](https://github.com/openclaw/openclaw/pull/193865).

## 5. Catch cheap failures locally; use faster tools

A formatting error should not need a checkout, dependency install and remote test fleet before it reaches the author. Put the quickest useful checks where the change is made. Our recorded hook was pre-commit; the principle is to catch deterministic mistakes before the next remote round trip.

Start with formatting, lint and a focused test command. Add type checking where its latency is practical. Keep the local path easy for people and agents to invoke, and run the required checks in CI too: a skipped hook is not proof that a patch is correct.

Most of our code is TypeScript, so that toolchain was an obvious target. Our fast lint path uses **Oxlint**. The typechecker comparison below is a measured local invocation, not an end-to-end CI speedup.

We retained `tsgo` as a fallback and for release validation. A faster tool belongs on the checks authors wait for after checking its compatibility; it does not automatically replace the required release check.

The same approach applies outside TypeScript. A Go project can check formatting with `gofmt -l` and run `go vet` on the affected packages before its integration suite. A Rust project can run `cargo fmt --check` and check the affected package before a full platform matrix. These are examples readers can adopt, not changes we measured in this dataset; neither replaces the behavior tests.

Measure each command on your own repository. There is no measured ESLint-to-Oxlint percentage in this dataset, and these tool gains cannot be added to the headline cost reduction.

## 6. Stop rebuilding the same environment

Once selection makes a test job small, its fixed setup can dominate. Time checkout, dependency restoration, compilation, fixture creation and the actual tests separately. A test that takes seconds can still sit behind minutes of preparation.

### Fetch what the job needs

**Blobless checkouts** keep Git history available while fetching file contents on demand. We need the base revision to compare changes, but not every historical file blob up front. This is different from a shallow checkout that may omit the merge base. Our [timings-refit workflow combines full history with a blobless checkout](https://github.com/openclaw/openclaw/blob/a7d05c7af04aa17ac57c994da238d0c60f058ca6/.github/workflows/ci-test-timings-refit.yml#L22-L28). Check that your tooling gets a correct diff and that repeated lazy fetches do not erase the saving; no isolated checkout saving is measured here.

### Make cache hits real

A configured cache is not necessarily a useful cache. Check the restore result and the time still spent installing. Match reusable dependencies to their lockfile, toolchain and platform; do not reuse an incompatible build just because restoring it is fast. The same rule applies to package stores, compiler outputs and prepared test fixtures in other languages. Our [CI cache policy also distinguishes trusted writers from restore-only or cache-off candidates](https://github.com/openclaw/openclaw/blob/a7d05c7af04aa17ac57c994da238d0c60f058ca6/.github/workflows/ci.yml#L1445-L1499); sharing setup must not let an untrusted job poison later results.

### A smaller test run should need less setup

Choosing two test files does not help much if their job still downloads and prepares everything needed by the entire suite. The runner has to fetch tools and files before it can execute a test.

We replaced one **55.1 MB** all-in-one archive with a **30.0 MB** runtime package and a **0.48 MB** tooling package. A job restores the package it actually needs. These are package sizes, not a measured startup-time reduction. [Source](https://github.com/openclaw/openclaw/pull/195767).

### Trim platform setup, not the behavior under test

On mobile and Mac, startup is not just a JavaScript import. It is simulator boot, signing, toolchains and platform packaging.

Our iOS preparation uses [SimSlim](https://github.com/MobAI-App/simslim) to disable selected simulator background services, including Spotlight and Family / Screen Time. It keeps capabilities the app needs, such as Siri and connectivity. Preparation waits for boot, applies the configuration and verifies it; the native harness keeps stock and SimSlim comparison arms.

That is the principle: trim the environment without trimming the behavior under test. We have not reproduced a paired SimSlim speedup for this article, so there is no percentage attached to it. [Preparation source](https://github.com/openclaw/openclaw/blob/27af6ba36d11d10566950173ed7720f984aa920d/scripts/ios-simulator-prepare.sh) · [Qualification harness](https://github.com/openclaw/openclaw/blob/27af6ba36d11d10566950173ed7720f984aa920d/scripts/ios-release-e2e.ts).

### Load the tool once. Reset the test every time.

In selected Vitest lanes, `isolate: false` lets files reuse a worker. The expensive runtime stays loaded, but each test must still reset its mocks, fixtures and handles. Process, database and end-to-end lanes that depend on isolation keep it. Narrowing a fixture can also avoid starting parts of the application the test never uses.

The first measurement is case-execution time; the second is a whole invocation. Both preserve the stated cases, but they use different clocks and are not additive savings. Reuse the expensive preparation only where the next test still starts from the state it expects.

## 7. Pack, balance and size the remaining work

### Sharding is not parallelism

**Sharding** divides a suite into batches. **Parallelism** decides how many batches run at once. You can have 20 shards and run four at a time—or launch 20 separate machines.

We had over-sharded. Too many runners repeated checkout, installation and startup before doing a small amount of useful work. The problem recurred. In September, I was still writing: “we need to be careful of oversharding … we overallocate boxes.”

There are two separate decisions. First, put enough work in each job to make its setup worthwhile. Then distribute that work so the jobs finish at roughly the same time. A machine that finishes early cannot help a long-running job that already owns its files.

Packing reduces repeated preparation; balancing reduces the wait for the last job. In the real repository, one change packed **95 planned Node shards into 63**, keeping the gateway and agent suites isolated. Another deliberately increased **18 planned jobs to 20**—including **17 compact jobs before and 19 after**—to balance a long tail: the slowest observed job fell from **403 seconds to 300—25.6% shorter**. Fewer is not always better. Balanced work with little repeated setup is better. [Packing PR](https://github.com/openclaw/openclaw/pull/95649) · [Balancing PR](https://github.com/openclaw/openclaw/pull/104472).

Then size the machine for the work. A serial test gets little from dozens of cores. A memory-heavy job may need the larger machine even while its CPUs look idle.

The same 240 files cost an estimated 41.7% less at published prices and took 16.5% longer on the smaller runner. Both runs shared a known failing assertion, so this is a pricing comparison, not two passing release qualifications. We restricted the smaller class to qualified bundles; a memory-heavy Android CodeQL job went back up. [Source](https://github.com/openclaw/openclaw/pull/194271).

### Try the tradeoff on one job

The recorded 16-class and 32-class comparison below uses the same 240 test files. The cheaper runner took longer. Explore the alternatives to see how runner size, startup overhead and sharding interact; the 8-class, extra-shard and selection scenarios are **what-ifs**, not measured savings.

The **Worked example proposal** is the [eight-file illustration in the appendix](https://vincent.build/openclaw-ci-cost-reduction/#fig2), not the live production selector.

Three results are worth trying. Split the job into 8 shards and elapsed time falls, while setup is paid eight times. Turn on **Shadow** on 16-class: 15 seconds of overhead crosses a minute boundary, and the bill goes up. Choose the **Worked example proposal**: the proposal's share of test time decides the result, not its share of files.

## Did the cheaper factory also get faster?

**Historical timing: through 4 November.** These charts predate the adaptive-selection rollout. They show why a lower bill is not enough to declare the delivery problem solved.

Cheap CI is not enough. A patch can cost less to test and still take longer to land. We needed to watch two clocks: the time to get a CI result, and the time for a pull request to reach merge.

The first measures one feedback step. The second includes draft work, repeated checks, review and the wait to land. They belong beside one another—not added together, and not disguised as a count of agent tokens.

These checkpoints do not show a steady speedup alongside the bill reduction: the median is 6m41s in June, 12m10s in September and 9m18s in the 4 November partial-day sample. The median answers “how long did a typical successful run wait?” The 90th percentile shows the slower end. Neither is a speedup experiment: test selection, patch size and the system itself changed between checkpoints. The important result is the shape of the measured history, not a hand-picked fast run.

For the 30-day window from 5 October to the 4 November cutoff, my median delivery time was **37.8 minutes including drafts** and **25.3 minutes after removing draft intervals**, across 1,714 merged PRs. All of this predates the adaptive-selection rollout. Neither a long-lived draft nor a deliberate review hold is automatically CI waste.

The weekly series uses the same creation-to-merge definition throughout. The broader cohort gives context; the Vincent-only view keeps changes in the mix of authors from silently becoming a claim about one agent workflow. Draft-adjusted points use actual ready/draft events, not subtraction of unrelated medians.

We should not promise that shaving a minute off a job removes a minute from every delivery cycle. A check matters when it holds up the next decision. The engineering goal is lower cost *and* a shorter path to a trustworthy answer.

**How the two clocks were calculated**

**CI.** We enumerated all successful PR-triggered runs of the CI workflow on the third UTC day of each month from June to November, plus the partial day through 4 November, 14:11:47 UTC. Current-day successes must have been updated by that cutoff and all final jobs must have completed by then. We retained first attempts, ranked IDs by SHA-256 and selected 31 per day before inspecting durations. Each selected run requires a complete attempt-specific job inventory. Elapsed time is final non-skipped job completion minus workflow creation; parallel jobs are not summed. Median is the ordinary sample median, p90 the nearest-rank quantile. These are reproducible daily checkpoint samples, not full-month population medians. Success-conditioned sampling excludes slow failures and cancellations.

**Delivery.** The original, corrected census covers 25 June–22 September. We filled 23 September–4 November, 14:11:47 UTC using fully paginated, complete daily GitHub merged-PR searches, retaining the same historical author accounts. A later join date cannot add an author to this fixed cohort. Each value is merge timestamp minus PR creation timestamp, grouped into seven-day merge windows anchored on 25 June. One PR reports a merge before its creation even in GitHub’s direct API; it is excluded with its evidence retained, never clamped to zero. Recent open PRs are not zero-duration successes: they are excluded, so the series is completion-conditioned and can hide unfinished work. The last bucket is explicitly partial. These timestamps do not reveal when the agent first started work, active coding time or how much delay CI caused.

**Draft adjustment.** For Vincent’s PRs, ready-for-review and convert-to-draft events reconstruct draft intervals between creation and merge. Initial state comes from the first transition, or the final draft flag when there are no transitions. The original 2,209 measured PRs are retained and missing PR histories are fetched. Each PR’s draft time is removed before taking the weekly median. All my PRs in the delivery census have reconstructed draft history. Empty weeks remain gaps, not zeros. Different chart medians must not be subtracted to manufacture a “remainder.”

The repository stores the exact row-level timestamps, IDs, selection code, counts and calculations. The job-level examples elsewhere in this article explain mechanisms, not the aggregate trend.

## CI needs continuous optimization too

This is not a one-off cleanup. We now use agents to keep improving the CI process, not just to write the code that passes through it.

Failures caught during final release validation feed back into that work. We use those regressions to tune the tests and CI checks. A green PR is not enough if the release process still finds a failure.

We will keep tuning sharding and packing as the test suite changes, and keep removing AI-written tests that add maintenance without catching useful failures. The point is to remove redundant work, not the checks that protect real behavior.

We are also starting to use [Boat.dev](https://boat.dev/), with their sponsorship, and building our own Mac Studio cluster. Slow background workloads can use a different pool from urgent PR checks. Moving the work does not make its cost disappear; it lets us fit the machine and deadline to the job.

We are also continuing to evaluate [alternative test-selection tools and approaches](https://vincent.build/openclaw-ci-cost-reduction/#tried). Changing providers or tools is one option; making the existing work smaller and better balanced is another.

I want to track **PR creation to merge** alongside release failures and compute use. That is how we can tell whether each change helps, rather than just making one chart look better.

I want to package the reusable parts into a skill and a standalone repository: inventory the tests, collect dependencies, replay selections, prove fallbacks and roll out conservatively. Neither is released yet.

## Appendix: measurements and reproducible details

The main story describes the decisions. This appendix keeps the arithmetic, earlier observations and experimental limits available without making them the narrative.

**How the core test-code share was counted**

We count only tracked source under `src/` and `test/` at the immutable Git revision `a7d05c7af04aa17ac57c994da238d0c60f058ca6`. The allowlist is `.ts`, `.tsx`, `.mts`, `.cts` and `.rs`; the endpoint contains TypeScript-family source. Rust in the separate `crates/` tree is outside this core-only example. Documentation—including `.rst`—is not source code in this denominator.

We exclude all apps, web UI, extensions, packages, scripts and other top-level directories; dependency, vendor, build and documentation subdirectories; directories named `generated`, `__generated__` or ending in `.generated`; generated-name source and TypeScript declarations. These named exclusions are applied identically at all 25 revisions, not only to November. This scoped result replaces the earlier whole-repository 54.9% example; they use different denominators and must not be mixed.

Counts use scc 4.1.0, with blank and comment-only lines excluded. Each tracked path counts once; two different paths with identical content remain two maintained files. Fixtures, helper directories and explicit test-support/test-utils paths are support. Conventional `.test.*` and `.spec.*` files are tests; those explicitly named integration, E2E, live, browser or smoke form the integration category. Other test-named files and remaining source under `test/` are support. Everything else is implementation. Filenames do not establish semantic test level, usefulness or runtime cost; tests embedded in implementation files are not split out.

For each Monday from 1 June to 9 November, we select the latest first-parent revision before 00:00 UTC, then add the pinned 13 November revision. Each point divides its category counts by its own eligible core-source total. The retained per-file ledger, 25 revision IDs and reproducible counter record the exact scope and arithmetic.

**Cost ledger: every window, formula and denominator**

| Measure | Input and result | Scope / limit |
|---|---|---|
| Peak week | 17 Sep 00:00–24 Sep 00:00 UTC: $296,090.104 / 7 × 30 = $1,268,957.59 | Highest seven consecutive full days in retained export, 30 Jan–12 Nov 2026. Confirmed by a separate exact-window query. |
| Latest week | 6 Nov 09:00–13 Nov 09:00 UTC: $13,375.542 / 7 × 30 = $57,323.75 | 95.4826% lower estimated compute value. Usage was not held constant. |
| Thirty full days, no extrapolation | 14 Sep–13 Oct: $744,122.09. 14 Oct–12 Nov: $294,396.90. Down 60.4%. | Equal 30-day windows; includes the earlier expensive weeks. Not traffic-normalized. |
| PR-CI-only weeks | $261,909.68 → $7,614.57; down 97.1% | Same windows as peak/latest; one repository, workflow and trigger, all outcomes. |
| Actual runner usage | 9,512,769 → 1,283,713 runtime minutes; divide by 60 = 158,546.15 → 21,395.22 runner-hours (86.5% lower). Jobs: 1,482,257 → 301,413 (79.7% lower). | Same exact peak/latest windows, all Blacksmith repositories and outcomes. Runtime totals, not vCPU-hours; no monthly extrapolation. |
| Sponsorship | Blacksmith supported the compute | Dollar figures use Blacksmith’s published prices. Storage, GitHub-hosted runners and other providers are excluded. |

Exports were refreshed 13 November. Usage records can be revised after capture. A re-query of the older article window differed from its saved November 4 export; historical chart values remain labelled by capture date instead of being silently blended. Failed, cancelled and rerun cost categories overlap and are not additive.

Monthly dollar estimates multiply each week’s average daily compute value by 30. Blacksmith sponsored the compute. These totals do not isolate the effect of any one PR.

**Which workflows used the runners?**

These job counts show where repeated starts concentrate: CI is the first place to investigate. They do not say that CI caused 94% of the bill, or that runner time shifted from PRs to background validation.

**Commit volume and agent-cycle measurement**

GitHub commit search returned 3,850 indexed commits for 17–23 September and 2,149 for 6–12 November, scoped to `openclaw/openclaw` by committer date. Neither search reported incomplete results. These are not PR-to-merge cohorts, per-agent productivity or an organization-wide count. The latest search uses whole UTC dates rather than the cost window’s 09:00 boundary.

To measure agent cycle time, collect PR creation and merge timestamps, state the cohort and report median and tail duration. Separate open and abandoned PRs so successful merges do not hide unfinished work. Compare task mix and release outcomes before attributing a throughput change.

**Selection examples: source table and units**

| Completed PR CI run | Reconstructed full inventory | Executed entries | Reduction |
|---|---|---|---|
| [42312466737](https://github.com/openclaw/openclaw/actions/runs/42312466737) | 4,018 | 15 | **99.63%** |
| [42312163596](https://github.com/openclaw/openclaw/actions/runs/42312163596) | 4,480 | 16 | **99.64%** |
| [42315120712](https://github.com/openclaw/openclaw/actions/runs/42315120712) | 6,895 | 97 | **98.59%** |

## Did cheaper also get faster? The earlier timing record

**Historical timing series, captured 4 November.** This chart has not been extended with a comparable post-rollout latency sample. Each dot uses the same repository, CI workflow and pull-request trigger. Move left for lower cost; move down for shorter feedback.

The week with the highest compute value in this CI-only scope began 21 September. By the latest complete week (26 October), cost per 100 CI runs moved from **$1,176.10 to $296.62** (74.8% lower), while run volume was 12.3% lower. The sampled median wait moved from **15m21s to 11m47s**; p90 moved from 25m53s to 23m40s. The June starting point was $177.22 per 100 runs: cheaper than the peak does not mean cheapest in the history. These are observed weekly comparisons, not a fixed-workload experiment.

**Definitions, limits and every weekly value**

**Cost per 100 CI runs.** Weekly compute value at Blacksmith’s published prices for `openclaw/openclaw`, workflow `CI`, event `pull_request`, divided by GitHub’s count of created runs in the same window, ×100. All created runs count, including failed, cancelled and skip-only runs. A lower ratio can reflect avoided jobs or a changed workload, not just faster execution. It is a period-normalized ratio, not an invoice joined to 100 exact run IDs: billing activity and run creation can fall on opposite sides of a week boundary. GitHub-hosted work and storage are outside this compute-cost scope.

**Cost per 100 billed jobs.** The same compute value divided by Blacksmith’s own billed-job count, ×100. This keeps both parts on the same usage-date basis. Neither unit-cost trend holds job size or the test matrix fixed; the workflow evolves.

**CI runs per merged PR.** All PR-triggered runs of this workflow divided by all merged PRs in the repository that week. This is checking intensity, not a retry rate: runs include unmerged PRs and legitimate new pushes, and rerunning an existing run does not create a new ID. Numerator and denominator are period totals, not the same set of PRs.

**Feedback time.** Each week samples up to 31 successful, first-attempt runs uniformly from that week’s success population. The sampler uses a reproducible seed and fetches complete attempt-specific job inventories. Time runs from creation to the final non-skipped job completing. Median and nearest-rank p90 exclude failures, cancellations and unfinished work, so they are not an all-outcome service-level measure. p90 from a small sample is especially noisy. The week of 15 June includes several long waits on 19–20 June; its p90 is over ten hours and remains in the chart. The optional log time scale keeps that tail visible without flattening the other weeks.

**Counts and cutoff.** GitHub run searches are recursively divided into non-overlapping windows below the API’s retrieval ceiling. Merged-PR totals are from complete repository-wide searches, not the article’s smaller author cohort. No missing week is filled with zero. Connecting dots shows chronology, not causation or proof of the best possible cost and speed.

**The earlier eight-file shadow walkthrough**

This synthetic walkthrough is an experimental teaching example, not the live selector. All eight files still run in shadow; its timings are invented. The animated walkthrough above illustrates the live source-aware rule without pretending to be a captured production run.

## Freeze the prediction before observing the answer

A selector can look perfect if it learns from the very run it is supposed to predict. The shadow experiment therefore records its proposal before tests start, executes the scheduled inventory independently, then compares predictions with outcomes. The learned score has no path back into that test list.

This diagram concerns the historical-graph and learned pilot, not the deterministic PR planner described above. At the 14 November source checkpoint, the implemented pilot requires provenance-bound observations: repository, source revision, runtime, configuration, lock inputs and compatible prior history. Missing or incompatible history is a reason for fallback, never evidence that a file is irrelevant.

**Why the records needed fixing**

- Interrupted runs originally lost observations written only at the end. [Early inventory writes](https://github.com/openclaw/openclaw/pull/191827) preserve unknown outcomes instead of inventing passes.
- [Oversized exports](https://github.com/openclaw/openclaw/pull/191931) retain outcomes even if dependency data is unavailable. A missing graph stays missing.
- [Failed workflows can contribute complete observations](https://github.com/openclaw/openclaw/pull/192574); an unrelated job failure need not erase them. Cancelled histories remain ineligible.
- [A single exact comparison in preflight](https://github.com/openclaw/openclaw/pull/192669) avoids relying on shallow test-worker Git history.
- [Shared path tables](https://github.com/openclaw/openclaw/pull/192704) made large graphs fit the export budget. The reported 30.7 MB → 3.77 MB fixture is a storage/correctness result, not a CI saving.

These fixes improve the quality of future selection evidence. They should not be counted as tests already skipped because of model predictions. Native Bun-test execution is still outside the observation pilot's coverage; a blank record is not a passing test.

## Where the model fits—and what it does not know

The dependency graph supplies a direct reason to include a test: it loaded a changed file. A model could help rank less obvious candidates. But adding a model does not make the evidence problem disappear.

The current model is a small local decision tree, not an LLM call. Its one learned question is about word overlap in file paths. It assigns one of two scores. It does not reorder tests or remove them, and it uses no API tokens.

The evaluation reported a ranking AUC of 0.98276. That measures how positives rank above negatives in this particular dataset. It does not mean the selector catches 98% of production bugs. The examples were controlled mutations, and the source audit found no evidence that the model outperformed the dependency graph.

That is why the model’s score belongs in the observation record, not in a headline about money already saved.

**Technical: model inputs, evaluation and score interpretation**

The model in `scripts/ci-adaptive-model.json` was trained on 120 rows from controlled source mutations. It was allowed three levels of depth and used one. It asks how much the words in two file paths overlap. `src/shared/retry.ts` and `src/shared/retry.test.ts` overlap completely, so that test scores 0.9565. `src/shared/backoff.test.ts` overlaps by a third, so it scores 0.

The tree has five features available, including dependency membership, and it does not read that one. On its evaluation corpus its predictions still matched dependency membership. The corpus was eight shared modules, each with its own test file, so a matching path and a real dependency were probably the same thing there.

Its held-out ranking AUC is 0.98276, on 64 rows containing six positives. That is not a catch rate, and it does not mean 98% of bugs are found. The rows are planted mutations, not natural regressions. The scores are raw class-balanced leaf values, not calibrated failure probabilities, and nothing shows that the model beats the dependency graph.

So it runs locally, uses no tokens, adds a number to a record, and has no authority over any test. There is no threshold, no reordering and no network call.

**Technical: what 0.98276 is made of**

Six positives and 58 negatives make 348 pairs, and 342 / 348 = 0.98276. The tree gives only two score values, so with ties counted as half, the one count that fits is all six positives high and two of the 58 negatives high as well. Those two negatives tie with six positives each, which gives up 6 of the 348 pairs. This split is derived from the reported number; the PR does not state it. Training had 120 rows and 10 positives, and evaluation used separate owner groups. The scores are still not probabilities.

## Before the shadow pilot gets permission to skip

Zero misses in a small sample prove little. With no misses across N independent faulty changes, the 95% upper bound on the miss rate is close to 3 / N:

| Independent faulty changes, none missed | Miss rate could still be |
|---|---|
| 30 | about 10% |
| 100 | about 3% |
| 300 | about 1% |
| 3,000 | about 0.1% |

Revisions from one regression episode count once. By 14 November, the audit work had recovered historical failures, but had not established a qualified same-revision cohort for measuring learned-model recall. The controlled-mutation results are not a substitute.

The first readout will compare usable-data coverage, native Bun gaps, observed failures, fallback causes and paired job costs. Enabling historical-graph or learned omission needs a separate rollout decision, with a stated miss budget, sampled same-revision audits and a way to turn it off. This does not describe the already deployed deterministic planner or its narrowly qualified unchanged-input reuse. Matching graph inputs do not grant permission to omit a test.

## We also tested alternatives

Building on the native test runner was not the only option. The investigation compared local models, hosted ranking and existing test-impact tools. The question was not just which one returned fewer tests. It was how each handled missing data and whether its results could be trusted in this repository.

**Comparison results, versions and experiment limits**

Before any of this merged, bounded private experiments compared the obvious alternatives. These results apply to the pinned versions and to OpenClaw's setup. A blocked row means a missing prerequisite, not a verdict on the tool.

| Option | Result | Decision |
|---|---|---|
| Native Vitest recorder | Fixture gap repaired with a declared input, on Node and pinned Bun | Build on it |
| Local models: logistic, CART, boosting, XGBoost | Whole-owner holdouts. Full-feature trees missed regressions the graph caught | Keep the pipeline, no skip authority |
| Jev / System 1 | 35 corrected live calls, 341 valid scores | Promising for ranking, no skip authority |
| jev-test-impact | Partial or empty answers silently dropped unanswered tests | Not adopted directly |
| vitest-impact 0.3.0 | Useful fallback rules; root multi-project config unsupported | Borrow the ideas |
| vitest-affected 0.9.0 | Peer range rejects Vitest 5; stale graphs warn but stay valid | Not at this version |
| Nx 24.0.3 | Separates data from ordering dependencies; six graph cases, no task executed | Borrow the distinction |
| Smart Tests, Develocity | Need a workspace and a licensed endpoint | Blocked |

The first live Jev batch used descriptive mutation IDs, and those names leaked clues such as comment controls into the provider's input. The batch was caught, marked diagnostic only, and repeated with opaque IDs. Those live calls belonged to the private experiment. The merged stack makes no provider calls.

## Runner comparison method

The [interactive runner comparison](https://vincent.build/openclaw-ci-cost-reduction/#fig4) is in the main article, beside the matched-job evidence.

Less elapsed time is not automatically less compute. Fewer selected files are not automatically less cost either. Setup remains, each execution rounds up to a billing unit, and safety audits still run the full suite.

The cost model in [#191229](https://github.com/openclaw/openclaw/pull/191229) includes those effects. It allows an optimization to have negative savings. In shadow mode, all the tests run and observation adds overhead, so that overhead is a cost—not a saving.

The main-body cost explorer uses that arithmetic on the matched runner job. Both 16-class and 32-class are recorded. Everything else is a what-if.

## What we can claim—and what we cannot

**The change in compute usage and its estimated value is observed.** The latest week is 95.5% below the September peak when both are expressed as an estimated 30-day compute cost at Blacksmith’s published prices. This includes changes in traffic, platforms, job size and selection. It is not a same-workload experiment.

**The PR-CI-only result is also large.** For `openclaw/openclaw` / `CI` / `pull_request`, the compute in the same two seven-day windows was valued at $261,909.68 and $7,614.57, down **97.1%**. The estimated 30-day cost for that work is $1,122,470 → $32,634. Billed jobs fell 84.3%; average cost per billed job fell 81.5%. A fixed workflow name is not a fixed workload.

**Selection is deployed; its measured units are narrower.** The completed-run examples show 98.6–99.6% fewer executed file/config/runtime entries. A saved campaign summary reports 86.28% fewer unique file/run entries in a wider three-hour sample; its arithmetic was checked, but the underlying run-level census and precise window were not reproduced here. It is not used for the headline. The planner repair shows 80% fewer planned Node jobs on one input. These overlap; adding the percentages would be meaningless.

**Model scoring is implemented, not authorized to omit tests.** Its score neither skips nor reorders tests, and the merged scoring path uses no provider tokens. Natural-regression recall, superiority to the deterministic baseline, and net savings after collection overhead remain unproven.

**Local speedups are real but local.** The 37.6% invocation and 44.3% case-execution reductions preserve the stated test cases. They do not establish workflow p50/p90 or end-to-end PR delivery improvements. The timing charts retained here stop at 4 November; there is no comparable post-rollout latency census in this refresh.

## From more machines to less work

1. **June–July: make parallelism useful.** Fewer unnecessary bot starts, 95 → 63 planned shards, then a different rebalance with 18 → 20 jobs and a shorter straggler. Job count alone was never the objective.
2. **September–October: fit the machine.** Qualify serial tooling on smaller runners; retain larger machines where memory and useful parallel work require them. Move or retire unnecessary workflows without pretending work moved to another provider vanished.
3. **31 October–4 November: reuse proof; build the observation chain.** Main CodeQL becomes hourly with per-category baselines. The graph-and-model pilot records proposals, provenance and results, still in shadow.
4. **5–8 November: selection and sizing become the main story.** Deterministic PR selection reduces the live test inventory; remaining broad triggers and SDK fanout are narrowed. Estimated daily compute cost falls sharply. Three completed runs show 98.6–99.6% fewer executed entries in their planned lanes.
5. **9–13 November: attack fixed overhead.** Worker preparation reuse, timing repairs, compiler qualification and same-case cleanup reduce the work left after selection. Narrow unchanged-input qualification supplements the planner; learned omission stays off.

The campaign did not find one magic classifier. It moved up and down the stack: refuse an irrelevant event, select the work affected by a real change, do not split tiny work into dozens of jobs, give each job the machine it can use, and stop rebuilding the same environment.

The chronology groups overlapping work; it is not a set of additive savings.

### Notes & sources

**1. Code mix.** TypeScript was 89.2% of 517,461,426 GitHub-detected source bytes on 13 November 2026. This is neither a line count nor a cost share. [Back to the story ↑](https://vincent.build/openclaw-ci-cost-reduction/#two-axes)

**2. Cost window.** Estimated value of Blacksmith-sponsored compute at published prices: each window’s daily average projected over 30 days. Blacksmith sponsored this compute; these are estimates, not invoices. Latest week ends 13 November 2026, 09:00 UTC. All organization repositories and outcomes. [Arithmetic and source ledger](https://vincent.build/openclaw-ci-cost-reduction/#ledger).

**3. Test counts.** A planned entry counts a file, configuration and runtime together, not an individual test case. The three runs are selected examples, not a fleet average. [Full source table](https://vincent.build/openclaw-ci-cost-reduction/#evidence).

**4. Timing & scope.** Historical feedback series stop at their 4 November capture. Actions examples use complete first-attempt job inventories fetched 13 November; different commits, not controlled replays. Implementation links describe the named changes at the time.

**Attribution.** The experience, sponsorship and rollout assessment are mine; Peter’s cleanup is his report. The /goal adapts my retained cleanup instructions. Private logs and provider exports are not published.

**How this article was made.** Written with Fable, fact-checked and revised with Codex; earlier design with Fable and Claude Opus. OpenClaw is a collective effort.
