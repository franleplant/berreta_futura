---
source_ids:
- how-the-claude-code-team-thinks-about-verificati-fdb3c1f1
content_mode: article
label: ARTICLE
---

On the Claude Code team, Claude writes and reviews about 90% of our code, so how our agents verify their work with evidence matters a great deal. Verification loops are what let you delegate. Without them you can run one or two Claudes, because you check everything yourself. With them you can run dozens or hundreds.

## Why it pays

In internal testing on structured file generation, a separate grader checking Claude's work against a rubric improved task success by up to 10 points over a standard prompting loop, with the largest gains on the hardest problems. Tests, benchmarks, and specs were once expensive to verify. Now an agent generates them cheaply, and once written they run as software, without many more tokens. Feed failures back as a hook or a CLAUDE.md rule, and the issue (mostly) stops recurring.

## Three tests worth investing in

Flaky tests train the agent to rerun them instead of fixing the code. Slow tests mean fewer runs across batches, which makes issues hard to pinpoint. Heavier tests belong before you commit.

**End-to-end.** If you focus on one type, pick this. These tests follow real user flows and are hard to fool: either the whole feature works or it doesn't, and they tell you what broke. Unit tests are faster and less flaky, but you can pass them and still break the feature, because neither the agent nor the test understands the full task. Give the agent hands and eyes on the running system through a skill that drives CDP, simulators, or API harnesses. A feature map can serve as its guide and grading rubric.

**Property tests.** Most tests encode what you thought might go wrong. Property tests reach the edge cases people miss, which is where agents often fail. You state something that can't fail, and a library such as fast-check, Hypothesis, or proptest throws thousands of inputs at it: round-trip encoding, invariants, idempotency, equivalence with naive but correct code. Those inputs don't share the bias of the agent that wrote the code. They also help with rewrites when the spec has drifted from production.

**Differential tests.** For large migrations, run the old and new systems on the same inputs, randomly generated or sampled from production. A difference is a bug or a breaking change. Normalize irrelevant factors like whitespace and keep a list of approved differences.

## How we verify

**Run the change.** Running the app end to end matters more than tests. You wouldn't ship an iOS change without trying it in a simulator, and the same goes for Claude. Use the Chrome extension for web, an iOS or Android MCP for mobile, computer use for desktop, a local service for backend. Codify this in a `verify` skill under `.claude/skills/`, close to the code; Claude uses it before committing. Make it fast and reliable, since it's your smoke test harness. This is how we test nearly all changes at Anthropic.

**Failures decide what needs a person.** Claude fixes failing checks. If one still fails after three rounds, it stops and brings in a human.

**Owners write the checks**, refining them until they flag what the owner would flag. A check that pulls in a reviewer says why.

**Reliability checks trigger on the diff.** Our checklist has 39 items, each with a trigger readable from a diff, a check, and the incidents or PRs behind it. One is "--resume loads old transcripts": when session storage or message types change, does a new field load safely? Claude checks only the matching items, usually 3 to 10.

**One reviewer, several rounds.** A second, more expensive reviewer is often worse than tuning the first. A REVIEW.md says what to watch. Each round builds on earlier rounds and past failures; it's cheaper and finds more.

**Changes can't modify their own checks.** If a change can modify the check that judges it, the check is broken. Code Review reads REVIEW.md from the base branch, never from the pull request. Reviews are reserved for commits: a passing review on an out-of-date commit means nothing. Cheap checks run first, so Claude runs tests, build, and linter before opening a PR, enforced with a hook or a `/goal`.

**New gates start in observe mode.** We stamp each commit with how it was verified, including "none." A commit gate can block a commit when the session lacked `/code-review` or `/verify`, with off, observe, and enforce modes. Observe logs what would have been blocked, so we can review false positives. Enforce blocks, though a commit message can explain why it went unverified, and after two blocks in a session the next commit passes so Claude doesn't get stuck. Claude Code isn't perfect.

**Review the reviewers.** We track reverted merges, changes a maintainer rejected, and a size-matched set of changes that stayed clean. Code Review's evaluation recreates the repo at review time for past incidents and reverts, with a one-sentence answer key; only findings that describe that bug score. Merged, stable changes act as a control against over-flagging, and the tuning set is kept apart from the test set. Recall is measured separately for raw findings, post-verification, and final review, to see whether the system loses bugs it had found. Severity matters too: findings are tagged Important, Nit, or Pre-existing, and the author isn't held responsible for the last. We tune recall up to the point where the next gain would be overfitting.

**Turn misses into rules.** One method mines human review comments and reverts for patterns that occur in at least two PRs and show in a diff; three agents try to disprove each, and a human approves it in a PR. The other replays three bug finders against a PR tied to a known incident. If at least two find the bug, it's detectable; if they miss it on a small diff, that gap earns a rule in REVIEW.md. Claude can't skip flaky tests, add sleeps, or retry until they pass. If it can't find the root cause, it deletes the test and writes down why. Rules grow if you let them, so we prune them on a routine.

With that in place, your job shifts from reading every diff to defining what "done" looks like and reviewing the evidence.
