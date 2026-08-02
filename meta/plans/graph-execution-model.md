# Plan — a graph engine for the magazine

Status: **proposed**, not started. Revision 5, 2026-08-02, branch `writing-overhaul`.

Revisions 1–4 designed backwards from the existing code and grew baroque. This one
starts from the problem. It is much shorter, and that is the point.

Sources archived in [`meta/docs/`](../docs/). Review history in [§8](#8-history).

---

## 1. The model — two orthogonal layers

Earlier revisions had one model and it fought itself. There are two, and separating
them is what makes the rest simple.

### Layer 1: the lifecycle is a state machine

Per article:

```
drafting → gated → judging (parallel: worth, mechanics, evidence, shape, teaching?, craft)
                → deciding ─┬→ settled
                            ├→ drafting          ← the loop is a transition
                            └→ escalated
```

**A loop is a transition.** Not an instancing trick, not an unrolled generation.
Revisions 1–4 spent their length inventing "round generations" and "attempt epochs"
because they started from a DAG, and a DAG cannot loop. A state machine can, and the
whole apparatus becomes unnecessary.

Parallel states cover the lenses. Actors cover instances — one per article, one per
edition, one for art. Guards cover the budget. None of this needs inventing.

### Layer 2: staleness is a dependency question

A state machine says *where you are*. It cannot say *what is still valid*. "Should
this image be regenerated" is a question about whether inputs changed, and no state
machine models it.

So each state that produces an artifact declares its inputs, and its output is valid
while those inputs hash the same. That is the whole of layer 2 (§4).

**These are orthogonal, and conflating them is what went wrong before.** Lifecycle
says what happens next; hashes say what survives. Neither substitutes for the other.

### What follows

**There are not two kinds of node.** Deterministic and agentic differ only in whether
re-running is free. One kind, one cache rule.

**Who answers is not the machine's business.** Three answerers — a local script, a
model, a person. All three are "a state waiting for an event." That is dispatch.

### What follows from it

**There are not two kinds of node.** Deterministic and agentic differ only in a
cache rule. Deterministic: re-run freely. Agentic: keep the first answer until an
input changes. One kind of node, one field.

**Who answers is not the graph's business.** Three answerers — this process, a
model, a person. That is dispatch. The graph is indifferent.

Argo Workflows proves this shape works at scale, and is worth imitating. It declares
a node whose output is `supplied: {}` — a placeholder to be filled in later "through
the CLI, API, etc." No pod is created and nothing of theirs stays alive; the answer
arrives by an authenticated `set` followed by `resume`. One state machine therefore
treats *a human typed it*, *an agent fleet returned it*, and *a model answered it* as
the same event. That is the design, independently arrived at by a CNCF-graduated
project.

**A loop is not a construct.** A loop is instantiation driven by data. Round 2
exists because round 1's decision said so. Per-article graphs, per-edition graphs,
per-round graphs are all the same mechanism used three ways.

**Running the graph is:** walk it, dispatch what is ready, exit. Re-invoke until
nothing is pending. No daemon, no sandbox, no suspend/resume machinery.

**Waiting is free.** A node awaiting a human or an outside agent is not a paused
process. It is a node whose output does not exist yet. Nothing is held.

**A gate that times out must fail, never default.** Argo's suspend node, on expiry,
overrides the output with its default and marks the node *succeeded* — a human
approval that nobody gave, recorded as given. We will not copy that. Our human nodes
have no timeout, and if one is ever added it fails closed.

### What this deletes

Revisions 2–4 invented attempt epochs, round generations, substep state machines,
head vectors, and an `INCONSISTENT` state. All of it was the old code's shape
leaking into the design.

| Was | Is |
|---|---|
| attempt epochs | instances |
| round generations | instances |
| substeps, partial fan-out, "first incomplete substep" | small nodes — one per piece × round × lens |
| `INCONSISTENT` | doesn't arise; one store, one rule |
| two cache economies | honest input declarations |

Make the nodes small and the state machine disappears. A node is answered or it
isn't.

---

## 2. The graph

Per article, per round:

```
write → gates → worth, mechanics → evidence, shape → teaching?, craft → decide
```

Barriers are edges, not machinery: `evidence` takes `worth`'s output as an input, so
it cannot run first. A blocking verdict makes later lenses not-applicable for that
round. `decide` emits pass, another round, or escalate.

Per edition:

```
every article settled → editorial → judge.edition → render
```

The editorial is the only piece that reads its siblings (`_peers` returns `()` for
everything else — verified). So regular articles are genuinely independent, and the
editorial is a join.

Art runs as its own instance, in parallel, at its own pace:

```
art brief → variants → [human picks] → registered ─┐
                                                    ├→ render → [human reads PDF]
text instances ─────────────────────────────────────┘
```

Two human nodes. Everything between capture and the PDF iterates alone.

---

## 3. Instances

Addressed by `(edition, kind, subject)` where kind is `text` or `art`.

- **Per article.** Run one piece to test it, or fifty in parallel. Independent
  because articles share no inputs.
- **Per edition.** Two editions at once. State is already under
  `editions/<id>/`, so this mostly works. Two things spoil it and must be fixed:
  `pin.py` takes a *global* exclusive lock, and `release-state.yaml` is a single
  cross-edition ledger. Narrow the lock; the ledger is genuinely shared and should
  be the only thing that serializes.
- **Cross-instance edges.** Art's output is an input to render. Today `consumes`
  only names siblings, so this is the one piece of new expressiveness needed.

Instancing is addressing, not identity. It must invalidate nothing.

---

## 4. Caching

One rule: a node's answer holds while its declared inputs hash the same.

**The key, borrowed from Hamilton, which specifies it best:**

```
(node name, source hash excluding comments and docstrings, transitive input digests)
```

Two things make this the right shape. Excluding comments and docstrings means
reformatting a prompt costs nothing while rewriting one correctly invalidates — the
distinction earlier revisions kept fumbling. And the key *is* the provenance record:
it answers "which prompt revision, and which source bytes" by construction. One
artifact, both jobs. No separate audit store.

**Declare cache inputs by subtraction, an idiom worth taking from Prefect:** a
policy composed as `source + inputs - manuscript` says plainly that art depends on
everything except the text. Prefect stores these as plain files whose *filenames are
the cache keys*, which is the whole mechanism and is worth copying directly.

Images survive text revisions because their inputs *honestly exclude the
manuscript* — keyed on the art brief, direction, and article identity. No special
pleading, no second mechanism.

The trap to avoid has a name. Kedro skips a step when its output *file exists*,
without hashing inputs — so a changed image prompt with a stale PNG gets silently
skipped. Existence is not sufficient. Existence plus matching input digests is.

Assets go in a content-addressed store so rejected variants stay cheap to keep,
which is what makes human variant-picking pleasant. Note git already stores blobs
by content, so this buys addressing and dedup, not smaller history. Repository
growth needs LFS or a retention policy — an open question.

---

## 5. Build or adopt

Surveyed Python, JS and Rust (2026-08-02). All three say the same thing: **own the
graph.**

**Why nothing fits.** Every product bundles the graph with a runner that insists on
making the model call, plus a database, plus a UI. We want the graph, not the
bundle. And the two things we most need, no engine in any language supplies:
per-node caching keyed on declared inputs, and a provenance archive. Restate
garbage-collects its journal when an invocation completes. Temporal's archival is
experimental and its filesystem target's APIs don't work. So provenance and caching
are ours regardless of what we adopt — which is most of the work.

**Language is settled.** The best answers to our hardest constraint are HTTP
endpoints, not SDK calls, so the authoring language is irrelevant to it. Every
candidate worth having ships Python, usually with more adoption than its JS twin.
A Python-only renderer pins the final step. No boundary is justified.

**The pattern already has a name.** Luigi's `ExternalTask` is a task with an output
and no run method: complete if and only if its target exists. A human or an agent
writes the file and the next build proceeds. Nothing alive, no worker held, no
timeout. Luigi reports what is pending and exits; you re-invoke it. That is exactly
our `reply.md` protocol, and it confirms the suspend/resume machinery every engine
sells is machinery we don't need.

**Worth reading, not depending on:** `graph-flow`'s pause enum (three contributors,
one of them an AI); Windmill's per-step cache; Sayiir's checkpoint-not-replay
stance (twelve PyPI downloads a week).

### XState as the host — assessed

The proposal: express the machine in XState, own it in TypeScript, shell out to
Python, Rust, `codex` or `claude` per node.

**What it gets right.** A loop is a transition — the thing four revisions failed to
express. Parallel states give the lens fan-out. Actors give per-article and
per-edition instances with isolation. `getPersistedSnapshot()` returns plain JSON we
own and can commit; restoring does **not** re-execute actions, so it is
checkpoint-not-replay by construction. Zero infrastructure, MIT, ~5M installs a week.
Nothing in it wants to make the model call, so a waiting state advanced only by
`send()` is exactly our inverted call.

**Two sharp edges, both real.**

*Invoked promise actors re-execute on restore.* So an expensive node must never be an
`invoke`. Model generative work as a state that waits for an external event, with the
subprocess launched outside the machine. Get this wrong and every restore regenerates
every image.

*Hashing must not be reimplemented.* If TypeScript computes cache keys it must hash
the same bytes identically to `pin.py`, whose own contract is that pins go through one
tool and "never through a second hashing implementation." Two hashers of one contract
is a bug class this codebase has already been bitten by. **Decision: TypeScript shells
out to Python for every digest.** Layer 2 stays Python-owned.

**What it does not give.** Layer 2 entirely — no input-keyed validity, no staleness.
That is ours in any host, so it is not an argument against XState.

**On the language boundary.** Nodes already shell out to `codex` and `claude`. A
Python script is not a new kind of node, so the orchestrator need not share a language
with the work. Earlier revisions said no boundary was justified; that answered a
different question — whether to adopt a JS *engine* for its features. Using a small
library as scaffolding while node bodies stay where they are is a different question,
and the answer can be yes.

### The view

**One structural finding decides how to build it.** Tools that *infer* topology from
emitted traces — Langfuse, Phoenix, Laminar, AgentOps, Inngest, Trigger.dev — can
never show a pending node, because a node that has not run has emitted nothing to
draw. Tools that *declare* topology — Argo, Kestra, Node-RED, ComfyUI — get pending
for free and simply colour it in. **No single source gives both unrolled loop
iterations and pending nodes.**

So the view needs two inputs: a **declared topology** for the skeleton and pending
state, plus a **run log** for iteration instances. XState supplies both from one
place — the machine definition is the topology, the snapshot series is the log. That
is a genuine argument for it.

**Adopt for the view only.** React Flow (`@xyflow/react`) with elkjs or dagre for
layout. Nothing in Python is close. A read-only JS sidecar over our own state, plus
a small approval surface that lists parked nodes with a diff and an approve button.
`langchain-ai/agent-inbox` is the reference shape. The seam: **Python owns execution
and artifacts; JS owns looking at them and approving them.** The browser was always
a separate process, so that boundary costs nothing.

**No engine's UI is the answer, and the reason is structural.** Temporal and Restate
were both surveyed at source level. Neither has a node-and-edge graph view in any
version — Temporal's frontend has no graph-layout library among its dependencies at
all. Neither has any concept of a loop iteration: both render a flat, index-ordered
event list, so "why did round 2 open" means scrolling to the second entry of a type
and reading the previous one's payload. Neither renders images — Temporal strips them
from markdown deliberately, Restate shows payloads as text truncated at 1000
characters. Neither lets you approve from the UI. Both default to discarding history
within days. Restate's own UI repository carries **no licence file**, so embedding it
is not legally available.

They fail identically because **an event log is not a graph.** Their UIs reconstruct
structure from a linear history and mostly can't. Our state is already nodes with
declared inputs and outputs, so a view over it is a direct rendering, not a
reconstruction. That is why building it is cheap and why theirs can't be borrowed.

Worth stealing anyway: Temporal's indexed search attributes for finding one run among
thousands, and Restate's approach of making the UI a thin client over a query API
rather than a privileged component.

**Revisit later, on evidence:** if durability genuinely hurts, Restate's Python SDK
gives awakeables — a node parks durably and anyone resolves it with one `curl`. It
is the cleanest inverted call anyone has built. It also means a daemon and a BUSL
licence, and it does not solve caching or provenance. Not now.

**The strongest adopt case, and why it still loses.** Argo Workflows has the best
external-answer primitive of anything surveyed, real provenance in three tiers, and
CNCF backing. But its memoization key is hand-built and stored in a Kubernetes
ConfigMap capped at 1MB, and cross-instance dependencies are a naming convention it
does not actually track. Those are precisely our two hardest requirements. Flyte 2
and Windmill cover the same two only partially. So adopting the best option means
taking on Kubernetes **and still writing the caching and the cross-instance edges
ourselves.** That is the whole adopt case collapsing: we would buy infrastructure and
keep the work.

**The dissent, recorded.** The Python survey recommended adopting Prefect 3 as the
host: it is the only tool that gives cycles, checkpoint-not-replay, and input-keyed
caching together, for one process over a SQLite file. Its argument against building
is that durable suspend/resume is a tar pit — a process dies mid-pause and you resume
twice or lose the answer.

That argument is sound about suspend/resume, and irrelevant here, because we do not
suspend. A waiting node is an absent output, not a paused process, so there is no
in-flight state to corrupt and no double-resume to guard against. Prefect's own
objection points the same way: its pause is **flow-level only** — `suspend` on a task
raises — so every out-of-band node would have to become a subflow, plus a registered
deployment. We would restructure the graph around a mechanism we don't need.

Worth knowing if that judgement turns out wrong: Prefect acquired Dagster Labs three
weeks ago, so both products are mid-merger.

**Dead ends, recorded:** Ray Workflows was *removed* from Ray, not deprecated, and
the maintainers say they won't replace it. Temporal forbids file I/O in workflow
code. Cloudflare Workflows can't host a Python renderer. Metaflow has no
human-in-the-loop primitive at all. Covalent is abandoned — its documentation site
is gone and it carries an unpatched pre-auth RCE in the dispatcher you are required
to run locally. n8n-shaped platforms are excluded by choice.

---

## 6. Phases

**Phase 1 — the engine.** Nodes, edges, instances, the done-rule. Small nodes from
the start. Prove it by running one article's graph, then fifty in parallel, then two
editions at once. Instancing must invalidate no stored answer.

**Phase 2 — art as its own instance.** Honest input declarations, the content store,
the cross-instance edge into render, the human variant node. Prove it by revising
text and generating zero images, and by changing the art brief and generating
exactly one.

**Phase 3 — render terminal.** `fit`, `build`, `render`, `package` as nodes.

One prerequisite: `require_complete_production_graph` refuses a build until every
node is accepting, so making `build` a node would make it gate itself. Readiness
must become target-relative — "complete up to here" — before this phase.

**Phase 4 — the view.** React Flow over a FastAPI endpoint with SSE for live updates,
layout by dagre or ELK (React Flow's free layouting guide has working code for both;
only the Pro *examples* are gated). Measured estimate: **3–6 developer-days**. A
Graphviz version is 1.5–3 days, but its layouts are unstable — a colour-only change
keeps positions byte-identical while adding one node moved five of six, which makes it
poor for watching something live.

Steal four things rather than inventing them:

- **Argo's inline artifact panel** — click a node, see the PNG, mime type chosen from
  the file extension. The closest existing thing to art variants on a node.
- **ComfyUI's lazy artifact pattern** — emit `{node_id, artifact_url}` and let the
  browser fetch. Never put bytes in the log. This is why its thumbnails are cheap and
  everyone else's are absent.
- **Node-RED's per-node status triple** — colour, shape, short text. Its 20-character
  limit is too tight for us, but the primitive is right.
- **Temporal's indexed search attributes** — for picking one instance out of thousands.

**Porting the live magazine pipeline onto the engine is the step after this
refactor**, not part of it.

---

## 7. Open questions

1. **Escalation.** A piece that can't pass in three rounds, with no human gate
   before the PDF: raise the budget, ship it with findings attached to the PDF
   review, or drop it?
2. **Release.** Its own gate, or folded into reading the PDF?
3. **Asset retention.** LFS, external store, or pruning?
4. **Instance cap.** How many automatic rounds before a person must intervene?

Not open, though I previously wrote them as if they were: `prompts/README.md`
already rules that issue findings route to named pieces and that `editor_decision`
findings need a human. The code disagrees with the policy. That's a bug, not a
choice.

---

## 8. History

**Three adversarial review rounds** (`codex exec`, model `gpt-5.6-sol`, effort
`max`, read-only) against revisions 1–3. Blocking findings 12 → 13 → 4.

- Round 1 killed a conditional back-edge: `consumes` is a dependency relation, so a
  back-edge makes the writer depend on the judgment that depends on it.
- Round 2 killed unrolling every round as nodes: `ProductionGraph.complete` is
  `all(node.accepting)`, and a failed verdict is non-accepting, so a passing round 2
  could never complete.
- Round 3 endorsed starting work but found four state-machine holes.

**Then four fresh-context surveys** of the Python, JS and Rust ecosystems and of
graph visualization.

**What actually resolved it** was neither: dropping the assumption that the existing
files, bench records, ledger and checkpoint sequence were requirements. They are
accretion. Once they stopped constraining the design, the four state-machine holes
round 3 found stopped existing, because the machinery they lived in was unnecessary.

---

## 9. Bugs worth fixing regardless

1. **Two settledness predicates disagree.** `is_settled` checks input fingerprint
   and manuscript bytes; the graph's `_settled_state` checks only status and bytes —
   `inputs_sha256` appears nowhere in `produce_graph.py`. The resolver can call a
   piece settled after its sources drifted.
2. **Peer order is in no identity.** The writer brief renders the edition's pieces
   *in running order*, but `_text_digests` collapses them to an order-insensitive
   map. Reordering unchanged articles reuses a stale editorial draft.
3. **`writer_identity` omits rendered inputs** — opener line budget,
   `edition_title`, `opener_intro_safe_characters`.
4. **`_judge_issue` never persists its input identity**, so nothing proves which
   pieces a verdict judged.
5. **`_EDITION_IDENTITY_FILES` is stale** — lists retired `line` and `learning`
   records, omits `worth`, `shape`, `teaching`, `craft`, `mechanics`. Renaming an
   edition leaves `edition_id` unrewritten in five records whose loaders reject a
   mismatch.
6. **Issue findings contradict `prompts/README.md`**, as above.

---

## 10. Sources

| Doc | Why |
|---|---|
| [evaluator-optimizer-anthropic.md](../docs/evaluator-optimizer-anthropic.md) | The generate/judge/revise loop and its termination |
| [building-effective-agents-anthropic.md](../docs/building-effective-agents-anthropic.md) | Where that sits among workflow patterns |
| [evaluator-reflect-refine-aws.md](../docs/evaluator-reflect-refine-aws.md) | The same pattern as vendor guidance |
| [langgraph-interrupts.md](../docs/langgraph-interrupts.md) | Human interrupts; interrupt only on irreversible actions |
| [graph-flow-readme.md](../docs/graph-flow-readme.md) | Cleanest published pause/route enum |
| [restate-what-is-durable-execution.md](../docs/restate-what-is-durable-execution.md) | Journaled steps, resume without re-running |
| [restate-key-concepts.md](../docs/restate-key-concepts.md) | Awakeables, the later escape hatch |
| [comfyui-execution-caching.md](../docs/comfyui-execution-caching.md) | Node cache keyed on declared inputs |
| [rust-agent-ecosystem-2026.md](../docs/rust-agent-ecosystem-2026.md) | Rust graph layer still thin |
| [temporal-rust-sdk-public-preview.md](../docs/temporal-rust-sdk-public-preview.md) | Rust SDK maturity |
