---
source_ids:
- harness-learning-enables-generalizable-test-time-e88ac636
content_mode: article
label: ARTICLE
---

A language-model agent is its model plus its harness: the program that decides what the model sees, which tools it can use, and how execution proceeds. We train a proposer model to rewrite that harness from execution feedback, with reinforcement learning and the revised harness's task score as reward. At test time both models stay frozen; only the code changes. On 21 unseen Reasoning Gym families, training raises mean revision scores from 0.32 to 0.62, and the trained 4B proposer beats its 35B teacher on average. A proposer trained on HotpotQA transfers to two unseen QA benchmarks. Proposers trained on single revisions keep improving harnesses over several rounds; training on revision sequences gives mixed results.

## The idea

Different tasks call for different ways of organizing model calls and tools, so the harness should adapt to the task at hand. We treat this as meta-learning over executable programs. In the inner loop, the proposer reads the task description, the current harness and an execution report, and writes a code edit: a span of existing code and its replacement. Harness revisions play the role that weight updates play in gradient-based adaptation. In the outer loop, we train the proposer on how those edits turn out.

Selection differs by setting. On Reasoning Gym we sample one candidate per round and keep it only if its development score beats the current harness. On QA we sample eight and advance to the best, even when it scores below its parent.

## How the proposer learns

We optionally start with supervised fine-tuning on teacher revisions that improved the seed. Then GRPO: each candidate's reward is its score on scoring questions, disjoint from the feedback questions, plus a small reward for edits that parse and run. The reward is local to one revision, a surrogate for the quality of the final harness.

## Reasoning Gym

Proposer and solver are Qwen3.5-4B; the teacher is a 35B model. The seed harness makes one solver call.

On 21 unseen families, mean single-revision scores rise from 0.32 for Base to 0.62 after RL. The gain shows in the mean over all proposals, so it doesn't depend on picking the best one. After RL, the average proposal beats the seed; Base and SFT proposals fall below it on average. The trained 4B proposer averages 0.62 against the teacher's 0.56, though the teacher scores higher under oracle best-of-eight selection.

The main figures exclude five unseen families that both the 4B proposers and the teacher find hard to address with an algorithmic harness. Over all 26 unseen families, means are 0.282 for Base, 0.415 for SFT, 0.528 for Single-step RL and 0.501 for the teacher.

Five sequential proposals reach or exceed the oracle best of eight independent ones, and beat their average. On format-varied questions, Single-step RL gets most of its five-round gain in the first revision.

## Multi-hop QA

Here a Qwen3-4B proposer revises a two-hop retrieve-and-summarize harness for a Qwen3-8B solver, trained with RL on HotpotQA and with no teacher.

Both RL proposers keep improving past the first revision and finish above Base on all three benchmarks, including the two unseen ones, while Base ends below the seed on HotpotQA and MuSiQue. The first revision accounts for only one third to two thirds of the ten-round gain. On MuSiQue, Single-step RL averages 0.15 exact match for independent revisions, barely above the seed, against 0.27 after ten rounds. On both unseen benchmarks, the average final run beats even the oracle best of 80 independent proposals. That comparison matches proposals per run but leaves total compute and feedback unmatched.

## Training on sequences

Training on successive revision states doesn't consistently beat training on single revisions. On Reasoning Gym, Multistep RL ends above Single-step RL on canonical questions and below it on format-varied ones. In QA the two finish nearly level. Iterative improvement, it seems, can emerge from single-revision training.

## What changes in the harnesses

Training cuts the share of proposals that fail to run or score zero. On unseen Reasoning Gym families that share falls from 38% for Base to 8% after RL; SFT alone leaves it nearly unchanged, at 35%.

On Reasoning Gym, the proposers mostly write interpreter loops that let the solver express a computation as code and hand it to the runtime. Asked to add helper tools, they often write a correct algorithm and then fail at question parsing, tool communication or answer extraction. A generated component contributes only when these interfaces also work.

In QA, RL keeps multi-hop retrieval, while Base sometimes reduces the harness to one solver call. A common RL edit keeps summaries to guide the next search and passes raw passages to the answering call, separating the evidence needed to form a query from the evidence needed to answer.

The seed may explain why QA gains last longer: it already holds a workflow whose depth, evidence access and search triggers can each be refined. Differences in training and selection prevent us from attributing the contrast to the seed alone.

## Limits

Training uses prescribed revision prompts, a fixed solver and, for Reasoning Gym, one teacher. Whether rewards that assign credit across rounds would make longer revision chains more effective remains open. Future work could try stronger teachers, proposers that inspect and test code with tools, and joint training of proposer and solver.
