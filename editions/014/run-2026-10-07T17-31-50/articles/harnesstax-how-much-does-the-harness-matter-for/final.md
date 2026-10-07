---
source_ids:
- harnesstax-how-much-does-the-harness-matter-for-7e847601
content_mode: article
label: ARTICLE
---

We ran seven models through three harnesses (Claude Code, Codex CLI, and Pi) on SWE-bench Lite and Terminal-Bench 2.0. On these two benchmarks, the harness changed the bill far more than the result: the same model reached similar success rates at up to 5x the cost. Pi, a minimal open-source harness with four tools, was competitive on both cost and success. Models often did best outside their own provider's harness. These findings may be limited to the two benchmarks we tested, which the models may have seen during training.

## How we measured

We compared 21 model–harness pairs on the same 30 randomly sampled tasks from each benchmark, three attempts per task. Each harness ran in its native configuration at its high effort setting, capped at 100 agent turns. Success came from each benchmark's official evaluator. Token costs used one fixed direct-API price list, dated September 1, 2026, applied equally across harnesses. We estimated 95% confidence intervals with 10,000 bootstrap resamples. We will publicly release our profiling traces.

## Harness affects cost more than correctness

Claude Fable 5 solves 97.8% of attempts in Claude Code, 96.7% in Codex, and 96.7% in Pi, yet Claude Code costs about twice as much as Pi ($1.33 vs $0.67). Across shared models, using geometric means of cost ratios, Claude Code costs about 2.0x as much as Pi and 1.6x as much as Codex on SWE-bench Lite, and 1.5x as much as Pi on Terminal-Bench 2.0. The average harness effect on success stays within ±2% on SWE-bench Lite and within about ±5% on Terminal-Bench 2.0.

Paying more for essentially the same quality is a harness tax, and you may be paying it when you accept a coding agent's default harness without comparing alternatives. Model evaluations should therefore compare the same model across commonly used harnesses.

## A simple harness can be competitive

Pi reaches the Pareto frontier on both benchmarks with four tools: read, write, edit, and bash.

The cost gap does not come from taking more turns. For Fable 5 on SWE-bench Lite, Pi and Claude Code average 15.4 and 15.3 turns per attempt, yet Claude Code costs about twice as much for a 1.1% increase in success rate. Turn definitions vary across harnesses.

The tax can begin with the first model call. Across all seven models, Claude Code's mean initial context is over 10x Pi's, with longer instructions and larger tool schemas. This can raise costs, though total spending also depends on caching, generated tokens, and later calls.

Researchers can therefore work on state-of-the-art coding harnesses without access to proprietary ones or co-training with the model. Richer harness features may still benefit other models, workloads, or interaction settings. Harness complexity should be treated as an empirical trade-off.

## Models can perform competitively outside their own harness

Providers sometimes optimize models for their own coding environments. Yet across the six Anthropic and OpenAI models and both benchmarks, an alternative harness achieves the highest observed success rate in nine of twelve comparisons. Sonnet 4.6 solves 68.9% of attempts in Codex versus 66.7% in Claude Code on SWE-bench Lite, at a similar cost. On Terminal-Bench 2.0, GPT-5.6 Sol reaches 83.3% in Pi versus 78.9% in Codex, at about half the cost ($0.42 vs $0.76).

A shared provider does not guarantee the best pairing. The practical question remains which harness gives the best balance of cost and success for a given model and workload.

## What follows

A harness tax can go unnoticed when we focus only on task success. The natural next step is to evaluate harnesses and automate their selection in real development workflows, where requirements evolve, developers give feedback, and tasks extend across sessions.

As models become more capable, coding agents may need less of today's scaffolding. General-purpose coding agents should prioritize cost efficiency and reliability, since many tasks may not need add-on features. For harder problems at the edge of a model's capabilities, including scientific discovery, agents may still benefit from harnesses that guide exploration, evaluation, and learning from feedback. Users should not have to make these configuration choices themselves; we envision a harness that adapts as tasks unfold while remaining general.
