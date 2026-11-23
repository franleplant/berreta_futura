---
source_ids:
- making-openclaw-ci-faster-and-95-cheaper-97e637dd
content_mode: article
label: ARTICLE
---

Tests were slowing our coding agents down. Our Blacksmith runners logged **158,546 hours** in the September peak week and **21,395** in the latest week: **86.5% less runtime**. The estimated value of that compute fell **95.5%**. Blacksmith sponsored the capacity; we did not pay those dollar amounts. The workload also changed, so neither reduction belongs to one fix. We cut pointless checks, made better use of each machine and made tests adapt. The reduction in compute value is measured. A faster path from PR to merge is not yet established.

## Where the limit was

Agents were producing code faster. They were also producing more tests, more jobs and more retries. About 89% of our code is TypeScript, so I began there. The broader lessons apply across languages: remove weak tests, balance work and stop repeating setup.

The measure I care about is **agent cycle time: PR creation to merge**. A cheaper machine is not a win if every dependent agent waits much longer. A faster machine is not a win if most of it sits idle. The job that never needed to start costs nothing and holds nobody up.

## Delete the waste first

My starting assumption in an agent-grown suite is that most tiny, implementation-mirroring unit tests are noise until they can demonstrate an independent contract. Models are very good at adding code. Deletion needs an explicit instruction and a place in the definition of done.

We put that pressure into a guard. From 24 October, a change over the test-line ceiling had to offset its added lines by deleting or consolidating tests, or justify a higher ceiling. By 13 November, a change could add **400 net new test lines** without an allocation record; larger additions needed a justified allowance.

In OpenClaw's core, test files fell by **417,906 lines net** between 28 September and 13 November. Tests and support peaked at **68.9%** of counted core code and fell to **63.2%**. These are net changes between snapshots, not a count of every deletion.

The audit rule: name the behavior a test protects, show a believable bug that would make it fail, and keep one strong owner for that contract.

## Run each check at the right stage

We separated the answer needed to merge a change from the broader proof needed to ship a release. Full CI on every main push is now opt-in; broader main validation runs hourly, and release validation has its own schedule. Main's CodeQL moved to an hourly schedule, and an unchanged, successful category can reuse its result for up to 24 hours.

Do not silently treat an old green run as proof for a newer commit. My rollout check was that releases did not suffer and full E2E runs did not reveal a new pattern of repeated regressions. That is an operational assessment, not a measured defect-rate claim.

ClawSweeper, our review bot, now gives a new PR one automatic review; follow-ups are requested. No isolated review-cost percentage is claimed.

## Test what changed

The selector is ordinary, deterministic code. It reads the exact diff, selects the tests that own the changed files, follows reverse imports to their callers, adds fixed policy and smoke checks, and hands the list to the existing runner. Every selected test records a reason. A missing dependency record is a reason to run more, not evidence that nothing can break.

Three completed PR runs executed **98.6–99.6%** fewer file/config/runtime entries than the full inventory. These are selected examples, not a fleet average. Selection rolled out around 6–7 November, and estimated daily compute cost fell from about **$7,738 on 5 November to $1,507 on 7 November**. Cleanup and runner changes had already accumulated, so that is not a price tag for the selector alone.

A learned ranking model runs in shadow: it records predictions and skips nothing. Its held-out AUC of 0.98276 is not a catch rate, and nothing shows it beats the dependency graph. In our experiments, some richer models missed regressions on held-out owners that the graph caught.

## Make the remaining work cheaper

Put cheap, deterministic checks before the next remote round trip. Our fast lint path uses Oxlint; `tsgo` stays as a fallback and for release validation. There is no measured ESLint-to-Oxlint percentage, and these gains cannot be added to the headline.

Once a job is small, setup can dominate. We use blobless checkouts, check that cache hits are real, and split one 55.1 MB archive into a 30.0 MB runtime package and a 0.48 MB tooling package. Those are package sizes, not measured startup savings.

Sharding is not parallelism. We had over-sharded. One change packed **95 planned Node shards into 63**. Another raised **18 jobs to 20** to balance a long tail, and the slowest job fell from **403 seconds to 300**. On a smaller runner, the same 240 files cost an estimated 41.7% less and took 16.5% longer.

## Did it get faster?

Our timing series stop at 4 November, before selection rolled out. The median successful CI run took 6m41s in June, 12m10s in September and 9m18s in the 4 November partial-day sample. Test selection, patch size and the system changed between checkpoints, so none of these is a speedup experiment. Across 1,714 merged PRs from 5 October to 4 November, my median delivery time was 37.8 minutes including drafts and 25.3 minutes without them.

The goal is lower cost *and* a shorter path to a trustworthy answer. We will keep tuning with agents, feed release failures back into the tests, and track PR creation to merge beside release failures and compute use. I want to package the reusable parts as a skill and a standalone repository. Neither is released yet.
