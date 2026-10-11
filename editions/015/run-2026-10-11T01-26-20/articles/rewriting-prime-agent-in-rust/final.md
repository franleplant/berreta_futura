---
source_ids:
- rewriting-prime-agent-in-rust-5bb1c16a
content_mode: article
label: ARTICLE
---

Since we launched Prime Agent in August, it has been downloaded more than 300,000 times and has processed over 8 trillion tokens. Today we're shipping it rewritten from the ground up in Rust. Over two weeks, Prime Agent orchestrated a swarm of over 2,000 agents to rewrite itself, across 10,000+ Prime Sandboxes and over 200 billion tokens from Prime Inference's GLM-5.3 endpoint. Our part was the verification: an objective check for every kind of parity with the TypeScript version, so the agents could measure their own progress and catch regressions before merging. Those checks only verified the behavior they exercised; internal use found the rest, and reaching release quality took weeks of follow-up with humans in the loop. Time to input is now roughly 14x faster than TypeScript, with over 80% less memory after startup.

## Why Rust

TypeScript let us ship quickly, but its types are optional and vanish at runtime, errors travel as unchecked exceptions, CPU-heavy work like rendering and parsing large sessions competes with keyboard input on one event loop, and every process pays for a JavaScript runtime and garbage collector.

- **Performance:** Prime Agent is a long-running daemon with a worker process per session. Native code without a garbage collector accounts for most of our memory and startup gains.
- **Concurrency:** one daemon streams model output, runs tools, relays messages between agents, and serves every client. `Send` and `Sync` let the compiler check what can move between threads and what can be shared.
- **Compile-time guarantees:** exhaustive enums, ownership, lifetimes, and Clippy's pedantic lints rule out whole classes of bugs, which matters when agents write most of the code.

## How Prime Agent rewrote itself

We wanted the agents to work autonomously, so the human work was setting up verification:

- **TUI parity:** both binaries run against the same scripted model, and a differential suite diffs the terminal frames they render across user flows.
- **Harness parity:** the same runs diff session transcripts and the requests each binary sends to the model provider.
- **Protocol parity:** every daemon protocol message type is checked against the TypeScript implementation.
- **Feature parity:** since scripted flows cannot cover an entire interface, agents audited the TypeScript product component by component, classing each as matching, partial, or missing.

A single root agent divided the work into a topological order of tasks and wrote no product code, which kept it free to monitor, merge, and work with us on priorities. We kept generation and verification in separate agents, since an agent that writes code is biased when evaluating it. Each task passed through four:

- **Planner:** writes the spec, the ground-truth TypeScript behavior, and the parity check.
- **Implementer:** writes the Rust in its own worktree.
- **Reviewer:** inspects the pull request adversarially, on a different model and in a separate context, looking for reasons it is wrong.
- **Verifier:** compiles and runs the parity checks and tests in a fresh Prime Sandbox.

A failure at review or verification sends the work back to the implementer with the findings; the PR merges once both pass.

The port also let us restructure the code. It is split into nine crates with a one-way dependency graph that Cargo enforces. The largest file is now ~2,500 lines, down from ~15,000. Each session runs in its own worker process, so one failing leaves the others running. Platform-specific concerns sit behind traits, so Windows support meant implementing those traits rather than rewiring the daemon.

## Refining the work

The parity checks only verified the behavior they exercised. Once the main RLM loop reached parity, we moved our rewrite agents onto the Rust build, and from then on Prime Agent Rust was improving itself. Then our team moved onto it for daily use, which exposed bugs and missing behavior outside the tests' coverage. Agents reviewed logs and traces from beta users to diagnose and fix issues. Over the following weeks, Prime Agent still wrote and tested the changes, while humans found problems, directed the work, and reviewed all results.

## Hillclimbing performance

We built a benchmark harness that runs each harness on a fresh 4-core, 8 GB Prime Sandbox, in a real terminal driven through a screen emulator against a scripted model, so timings reflect what a user sees and exclude inference. Noise checks withhold any result too unstable to compare.

A second orchestrator then ran for three days with one objective: improve the benchmarks without breaking parity. Agents profiled to find where time and memory went, workers measured each candidate against the current code on the same sandbox, and two reviewers on different frontier models checked that behavior still matched. We gave the loop no numeric targets, since a fixed threshold tends to become a stopping point. It logged over 144 experiment and audit records and merged over 69 changes. Most gains came from moving work off the startup and render paths, replacing polling with event-driven waits, and releasing memory once large sessions finished loading.

## Results

| | Prime Agent (Rust) | Prime Agent (TS) | Claude Code | Codex CLI | Pi | Hermes |
|---|---|---|---|---|---|---|
| First paint | 23.6 ms | 722.8 ms | 264.6 ms | 296.8 ms | 306.3 ms | 1,715.3 ms |
| Time to type (cold) | 55.8 ms | 737.8 ms | 348.4 ms | 324.6 ms | 317.7 ms | 2,094.5 ms |
| Installed size | 59.6 MB | 172.1 MB | 492.4 MB | 446.8 MB | 456.0 MB | 960.1 MB |
| Memory after startup | 106.0 MB | 607.4 MB | 226.9 MB | 344.4 MB | 138.1 MB | 194.6 MB |

External harnesses were measured with our own runtime suite. Without a common benchmark standard, these comparisons should be interpreted with caution.

## What's next

With the infrastructure work done, we're accelerating on capabilities and evals, and making the multi-agent workflows behind this rewrite available to you. Prime Agent now has native Windows support (beta), installs through Homebrew, and remains open source:

```bash
curl -fsSL https://app.primeintellect.ai/prime-agent/install.sh | sh
```
