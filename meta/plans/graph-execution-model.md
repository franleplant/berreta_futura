# Plan — one graph: capture → produce ⇄ judge → art → render

Status: **proposed**, not started. Written 2026-08-01 against branch `writing-overhaul`.

Archived sources for everything cited here live in [`meta/docs/`](../docs/) and are
linked inline. They were retrieved 2026-08-01; each carries a provenance header.

---

## 1. What this plan is for

The pipeline should express one thing:

> Sources are captured. Production writes articles from those sources (m:n) in
> declared styles. Judges read each piece and hand findings back to the writer.
> That loop repeats until the judges pass. Art is generated and a human picks
> variants. Then the renderers build the PDFs and the web edition, and a human
> reads the final PDF.

**Exactly two human gates exist in that sentence:** picking art variants, and
reading the finished PDF. Everything else iterates on its own.

Today the pipeline does approximately this, but expresses it across two
different mechanisms, and the central loop is not in either of them.

---

## 2. Diagnosis

### 2.1 `produce_graph.py` is a completion-checking formalism, not an execution one

It answers *"is this edition done?"* It cannot answer *"what runs next, and how
do we get there."* The evidence all points one way:

- `validate_node_specs` refuses any backward `consumes` edge
  (`src/magazine/produce_graph.py:489`): *"the table is in traversal order and a
  backward reference would be a cycle."* The loop is unrepresentable **by
  construction**.
- Judge nodes resolve against the **latest round only**
  (`_judge_state`, `produce_graph.py:911`). A failed lens is `READY` with detail
  `"round 2 returned changes_required"` — a point-in-time snapshot, not an
  iteration.
- `MAX_ROUNDS = 3` lives at `produce.py:190`, invisible to the graph. The graph
  cannot distinguish "round 1, budget intact" from "round 3, one failure from
  escalation."
- The actual loop is `for round_number in range(1, self.max_rounds + 1)` at
  `produce.py:1050`.

A DAG-with-states is a **report**. Reports cannot contain loops, so the loop
went somewhere else. That is the root cause, and it is why adding image nodes,
render nodes, or a visible round budget all feel like fighting the model.

What is needed is not a DAG that tolerates a cycle. It is a **state machine with
conditional edges**, where a node returns *where to go next*.

### 2.2 Two orchestrators, one nested in the other

`workflow.py` (2,932 lines) drives a linear 17-entry `CHECKPOINT_ORDER`
(`workflow.py:109`) with a hand-written method and if-chain per checkpoint.
`produce_graph.py` is a declared node table. The graph is resolved **inside a
single entry** of the checkpoint tuple (`workflow.py:1507`).

Consequence: the graph covers roughly the produce stage only. Capture, coverage,
cover, illustrations, build, bench, render review and release are checkpoints,
not nodes — and every remaining human gate lives in the checkpoint layer.

### 2.3 Adding a node is not one edit

The declaration claims nodes are cheap to add, and the table half delivers. But
acceptance predicates are dispatched by node id in an if-chain, and
`_edition_node_state` **raises** on an id it does not recognise
(`produce_graph.py:1006`). So a new node needs a table row *and* a resolver
edit. The predicate must hang off the spec.

### 2.4 Mid-loop state survives only under one backend

`_produce_piece` constructs `record = PieceRecord(...)` fresh every invocation
(`produce.py:1020`) — it never loads the prior record. Under `--backend agent`
this is fine and elegant: each round's answer is looked up on disk, so rounds
replay for free. Under the autonomous `codex exec` backend a run that dies at
round 2 restarts at **round 1 with a new paid writer call**, and `previous_notes`
is seeded from `_last_round_notes` only inside the `if filed:` branch
(`produce.py:1046`). `production_record.py` states notes are stored so *"a
resumed run must be able to hand round three the notes that round two wrote in a
process that has since exited"* — that intent holds on one backend only.

### 2.5 One cache policy applied to two different economics

`work_identity` = digest(prompt file) + digest(inputs), applied uniformly to
every dispatched call. Text and art have opposite cost profiles, and a uniform
policy means a craft-lens revision in round 3 invalidates the article's opener
illustration. That is the caching failure to avoid.

---

## 3. Framing

The shape is a **known, named pattern**, not a novel one — treating the loop as
exotic is what produced the current model.

**Evaluator–optimizer.** Anthropic's own name for it, and the cookbook
implementation is structurally this pipeline: generate, evaluate, and on failure
re-generate with the feedback *and previous attempts* in context, terminating on
PASS or a retry limit. See
[`meta/docs/evaluator-optimizer-anthropic.md`](../docs/evaluator-optimizer-anthropic.md)
and [`meta/docs/building-effective-agents-anthropic.md`](../docs/building-effective-agents-anthropic.md).
AWS ships the same thing as prescriptive guidance —
[`meta/docs/evaluator-reflect-refine-aws.md`](../docs/evaluator-reflect-refine-aws.md).

`produce.py` already has the semantics right: `findings` + `previous_manuscript`
+ `previous_notes` is exactly "feedback plus previous attempts." **Only the
representation is wrong.**

**Human-in-the-loop as interrupts.** LangGraph's rule of thumb —
*interrupt on irreversible, high-blast-radius actions only, not every step* — is
precisely the two-gate policy above. See
[`meta/docs/langgraph-interrupts.md`](../docs/langgraph-interrupts.md).

**Durable state = checkpoint and resume.** Not deterministic replay. The
requirement is *persistent state in the graph with proper invariants*: a
completed step is not re-executed because the log says it completed. Restate's
write-up of the paradigm is the clearest statement of the primitive —
[`meta/docs/restate-what-is-durable-execution.md`](../docs/restate-what-is-durable-execution.md),
[`meta/docs/restate-key-concepts.md`](../docs/restate-key-concepts.md). We take
the *idea*, not the engine (§6).

**Node-level caching for the expensive half.** ComfyUI's model — cache keyed on a
node's declared inputs, bypass-and-re-enable hits cache rather than
regenerating — is the right parallel for art. Its cache implementation is
archived at [`meta/docs/comfyui-execution-caching.md`](../docs/comfyui-execution-caching.md).

**Rejected framing (recorded so it is not re-derived):** build systems
(make/Bazel/Dagster asset graphs). Content-addressed staleness is prominent in
the current code, but it is a consequence of a design choice, not a requirement
of the domain. Leading with it is what made the loop look like an edge case.

---

## 4. Target architecture

```
                    ┌─────────── TEXT SUBGRAPH (iterate hard, cheap to re-run) ───────────┐
sources ──> write ──┤                                                                     │
   │                └──> gates ──> judge.{worth,evidence,shape,teaching,craft,mechanics} ──┤
   │                                   │                                                  │
   │                        conditional edge: any lens != approved                        │
   │                        AND rounds_remaining > 0  ──> back to write                   │
   │                                   │                                                  │
   │                        rounds exhausted ──> escalated (see §8)                        │
   │                                                                                      │
   │                                                              every piece settled ────┤
   │                                                                                      │
   └──> art_brief ──> art.variants ──> [HUMAN: pick variant] ──> art.registered ──────────┤
        (coarse key)   (cached, CAS)      interrupt #1                                     │
             ART SUBGRAPH (expensive, cache hard, rarely re-run)                           │
                                                                                          v
                                                              fit ──> build ──> render ──> package
                                                                                          │
                                                                        [HUMAN: read PDF] │
                                                                            interrupt #2  v
                                                                                       release
```

### 4.1 Node kinds

Three declared kinds, replacing today's `classification` strings:

| Kind | Meaning | Examples |
|---|---|---|
| `programmatic` | This package computes it. No model call. | `gates`, `fit`, `validate`, `build`, `render`, `package`, `settled` |
| `agentic` | A model or a fleet worker answers it. | `write`, `judge.*`, `art.variants`, `edition` |
| `human` | A person must act. **Exactly two exist.** | `art.select`, `render_review` |

Making `human` a declared *kind* rather than an emergent string is what turns
"exactly two human gates exist" into a test instead of a hope.

### 4.2 `NodeSpec` gains three fields

- **`edges`** — conditional next-hops, not just `consumes`. A judge node's edges
  include a back-edge to `write` guarded on `any(verdict != approved) and
  rounds_remaining > 0`. This is the change that removes the red flag.
- **`predicate`** — the acceptance check, co-located with the declaration,
  replacing the resolver if-chain (§2.3).
- **`cache_policy`** — per node kind, not global (§4.4).

### 4.3 Loop state

The round counter, accumulated findings, and prior notes become **declared loop
state on the edge**, not locals in a `for` body. Consequences:

- `mag produce --graph` can print `round 2 of 3`.
- Escalation stops being a surprise terminal state and becomes a visible
  countdown.
- The retry budget is declared next to the order it governs, which is the
  property the node table was written to get.
- `graph-flow`'s max-execution-step guard is the same idea; see §6.

### 4.4 Cache policy per node

| Node | Invalidates on | Must **not** invalidate on |
|---|---|---|
| `write` | sources, prompt file, findings, notes | — |
| `judge.*` | manuscript bytes (it read them) | — |
| `art.*` | art direction, article identity, **art brief** | **manuscript bytes** |
| `build` / `render` | all manuscripts, all assets, CSS, fonts | — |

The art row is the whole point. Keying art on a coarse authored art brief rather
than `manuscript_sha256` is what makes image caching correct rather than
accidental, and it is a **modelling** decision, not an implementation detail.

Note the genuine coupling in both directions: art prompts derive from what the
article is about, and art presence changes text page budgets
(`produce.py:2364` imports `illustrated_opener_intro_budget`). The subgraphs are
not disjoint — the text→art edge is real, and deliberately *coarse*.

### 4.5 Content-addressed asset store

`assets/by-hash/<sha256>.<ext>` plus small YAML pointing at hashes. Then:

- a regenerated-identical image costs nothing,
- a rejected variant stays recoverable, which is what makes human variant
  picking cheap,
- large binaries stop bloating git history while provenance stays in it.

`asset_sha256` is already computed on cover candidates. What is missing is the
store.

### 4.6 The four seams

1. **Declaration** — `NodeSpec` + edges + predicate + cache policy.
2. **Resolution** — pure read: files → node states. Never moves an edition.
3. **Dispatch** — `runner.CommandRunner` (autonomous) and the `reply.md` queue
   (cooperative). Unchanged; this seam is already right.
4. **Store** — content-addressed, for answers *and* assets. **Missing today.**

Three exist. The fourth is what the image-caching requirement is really asking
for.

---

## 5. What is already right (do not rebuild)

- **m:n sources → articles.** `manifest.py:109` — `source_ids` per article with
  one `source_body_sha256` pin per entry. `coverage_checkpoint` enforces that the
  queue equals the union of `articles[].source_ids` exactly.
- **Styles.** `produce.py:771` resolves `writer_prompt_path(piece.content_mode)`
  → one of four prompt files. First-class and per-piece.
- **Lens vocabulary.** `PIECE_JUDGE_LENSES` with the repair-order vs stage-order
  split, `covers`, `reads_source`, `blocking_halts_piece`. Genuinely good; port
  as-is.
- **Parallelism.** `stage_order()` groups lenses by stage and runs within a stage
  concurrently; `concurrency.ordered_map` fans out; independent pieces draft in
  parallel. Not a gap.
- **The final human gate.** `render_review_checkpoint` (`workflow.py:2278`)
  already reads `reader.pdf` + `home/booklet-a4.pdf` per language behind a
  machine `render-critic.json` pass. This *is* interrupt #2. Keep it.
- **Provenance.** Per-round prompt digests, backend, argv, model. The reason the
  ed-4 audit is now possible. Non-negotiable; it constrains §6.

---

## 6. Build vs adopt — decided: own it, steal the vocabulary

Researched 2026-08-01. Survey archived at
[`meta/docs/rust-agent-ecosystem-2026.md`](../docs/rust-agent-ecosystem-2026.md).

**Not adopting LangGraph.** Two structural blockers: its checkpointer wants state
as serialized thread-state, and our state must be a git tree because provenance
is a product requirement; and it assumes *the framework makes the model call*,
whereas the cooperative backend inverts that so a subagent fleet or a human with
`cat >` can answer a node. That inversion is the genuinely unusual thing here and
it survives every reframing.

**Not adopting Temporal.** Deterministic replay forbids the derive-from-disk
resolution the model rests on; state leaves git; and its replay-determinism check
turns in-flight prompt edits into crashes rather than the documented schema
migration they are. The Rust SDK is in Public Preview as of 2026, pre-1.0, no GA
date — [`meta/docs/temporal-rust-sdk-public-preview.md`](../docs/temporal-rust-sdk-public-preview.md).

**Not rewriting in Rust.** WeasyPrint is Python-only and is the production
renderer, so a Rust orchestrator means Rust graph → subprocess → Python render,
plus rewriting ~36k portable lines. The cited Rust wins (memory, cold start,
25–44% latency) do not bind here: latency is LLM calls measured in minutes and
the memory ceiling is WeasyPrint.

**Steal from `graph-flow`** (LangGraph-inspired Rust engine;
[`meta/docs/graph-flow-readme.md`](../docs/graph-flow-readme.md)). Its feature
list is this plan's requirements verbatim: cyclic graphs via `GoTo(task_id)`,
conditional edges on runtime context, `WaitForInput` to pause for a human,
session persistence across process restarts, and per-task timeouts plus
max-execution-step limits. At v0.6.0 / ~8.9k downloads / 357 stars / one
maintainer it is not something to put an edition through — but that a five-concept
library covers the whole surface is **evidence the surface is small**. Read its
API as the best available spec; implement it where our state already lives.

**Escape hatch, if timers or multi-machine execution ever matter:** Restate has a
Python SDK alongside the Rust one, so that door opens without a language change.
Not needed now — there is no timer requirement.

**Borrowed stance:** checkpoint-and-resume, **not** deterministic replay. Same
conclusion reached from two directions.

---

## 7. Phases

### Phase 0 — vocabulary (no behaviour change)

- Node kinds → `programmatic | agentic | human`.
- `NodeSpec` gains `edges`, `predicate`, `cache_policy`.
- Move acceptance predicates onto specs; delete the resolver if-chain and the
  `_edition_node_state` raise (`produce_graph.py:1006`).
- Types and docs only. **Exit criterion:** adding a node is one edit, provable by
  a test that declares a throwaway node without touching a resolver.

### Phase 1 — make the loop a graph citizen ← *the phase that matters*

- Replace `for round_number in range(...)` (`produce.py:1050`) with a conditional
  back-edge `judge.* → write` carrying findings, notes and the round counter as
  declared loop state.
- Retry budget becomes a property of the edge; `MAX_ROUNDS` leaves `produce.py`.
- `--graph` prints `round 2 of 3` and the remaining budget.
- Load the piece record instead of constructing it (`produce.py:1020`), and seed
  `previous_manuscript` / `previous_notes` from the last recorded round
  unconditionally rather than only under `if filed:` — this converges both
  backends onto one resume story (§2.4).
- **Exit criterion:** the graph, not `produce.py`, decides whether to loop; a run
  killed at round 2 resumes at round 3 under both backends.

### Phase 2 — split the subgraphs by cache policy

- Text: checkpoint-and-resume step log; content hashing reduced to the
  hand-edit guard.
- Art: `art_brief` → `art.variants` → `art.select` (`human`) →
  `art.registered`, with the CAS store under `assets/by-hash/` and the coarse
  art-brief cache key.
- Remove the produce.py firewall that makes image generation unreachable, and
  declare art nodes as `agentic` with an image work contract. `runner.py` already
  has the image path.
- **Exit criterion:** re-running produce after a craft revision generates zero
  images; rejected variants remain on disk and selectable.

### Phase 3 — render terminal, checkpoints collapsed

- `fit`, `build`, `render`, `package` become `programmatic` terminal nodes.
- `workflow.py`'s `CHECKPOINT_ORDER` (`workflow.py:109`) folds into the node
  table; the 2,932-line checkpoint layer goes away.
- **Exit criterion:** a test asserts the whole graph contains exactly two `human`
  nodes — `art.select` and `render_review`.

### Phase 4 — durable-execution library (only on demand)

Revisit only if a real timer, cross-host fleet, or multi-edition scheduling need
appears. Restate's Python SDK is the cheapest door.

---

## 8. Decisions

**Settled:**

- Humans pick art variants. This stays a gate — interrupt #1.
- Humans read the final PDF. Interrupt #2. Nothing else gates.
- Text iterates aggressively; art does not.
- Stay in Python. Own the engine (~400 lines), steal the vocabulary.
- Checkpoint-and-resume with invariants, not deterministic replay. Durability
  means *persistent state in the graph*, nothing more.

**Open — needs a call before Phase 1 ships:**

1. **Escalation policy.** With no human gate before the PDF, what happens when a
   piece cannot clear its lenses in 3 rounds? Options: raise the budget; ship the
   piece with findings attached to the PDF review; drop the piece from the
   edition. Today it is `human-review` at `workflow.py:1458`, which contradicts
   the two-gate goal.
2. **`_ADVISORY_REVIEW_CHECKPOINTS` flip.** The existing plan to make the six
   advisory lenses blocking (`workflow.py:166`) would **add six human-review
   gates after build**, directly against this design. Those checkpoints
   re-record verdicts the per-piece judges already produced — unifying onto the
   graph dissolves the duplication instead of requiring the flip. Decide whether
   the flip is superseded.

---

## 9. Sources

All archived under [`meta/docs/`](../docs/), retrieved 2026-08-01.

| Doc | Why it matters |
|---|---|
| [evaluator-optimizer-anthropic.md](../docs/evaluator-optimizer-anthropic.md) | The pattern, with a reference loop and termination condition |
| [building-effective-agents-anthropic.md](../docs/building-effective-agents-anthropic.md) | Where evaluator-optimizer sits among the workflow patterns |
| [evaluator-reflect-refine-aws.md](../docs/evaluator-reflect-refine-aws.md) | Same pattern as cloud-vendor prescriptive guidance |
| [langgraph-interrupts.md](../docs/langgraph-interrupts.md) | Human-in-the-loop as interrupt/resume; the "irreversible actions only" rule |
| [graph-flow-readme.md](../docs/graph-flow-readme.md) | Closest existing spec: `GoTo`, conditional edges, `WaitForInput`, max-step guard |
| [restate-what-is-durable-execution.md](../docs/restate-what-is-durable-execution.md) | Journaled steps, resume-without-re-running — the primitive we want |
| [restate-key-concepts.md](../docs/restate-key-concepts.md) | Workflow vs virtual object; the Phase 4 escape hatch |
| [comfyui-execution-caching.md](../docs/comfyui-execution-caching.md) | Node-level cache keyed on declared inputs, for the art subgraph |
| [rust-agent-ecosystem-2026.md](../docs/rust-agent-ecosystem-2026.md) | Rust survey; durable execution missing across agent crates |
| [temporal-rust-sdk-public-preview.md](../docs/temporal-rust-sdk-public-preview.md) | Rust SDK maturity, for the record |

Maturity figures checked on crates.io 2026-08-01: `restate-sdk` 0.11.0 (407k
downloads), `temporalio-sdk` 0.5.0 (public preview), `graph-flow` 0.6.0 (8,917
downloads, 357 stars, one maintainer).
