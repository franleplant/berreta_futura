---
source_id: src-joshi-dsls-reliable-use-llms
content_mode: faithful_synthesis
source_body_sha256: 1effc901980761de45a8ff4b1a359558003ab561e8f6fba92b48bfbfbc61de27
rights_status: private_reference
---

LLMs can generate code at extraordinary speed, but speed does not guarantee that the result expresses the intended design. Unmesh Joshi argues that abstractions and domain-specific languages provide a constrained harness: they help people discover a design with an LLM, then give the model a narrow, testable vocabulary through which to use that design reliably.

## A specification is a starting hypothesis

Large systems contain many small decisions that cannot all be settled in an upfront specification. Constraints, tradeoffs, and edge cases appear during implementation. A useful specification is therefore a hypothesis to revise, not a finished blueprint. The productive loop is small and iterative: refine the intent, generate a reviewable change, inspect what it reveals, and feed that learning into the next round.

Reviewing generated code is not equivalent to writing it. Review can confirm that a chunk resembles the stated intent, yet still avoid the decisions that expose a design: where a responsibility belongs, which boundary should be public, or how an extension should fit. Programming languages and paradigms also shape what designers notice. Functional and object-oriented implementations surface different concepts and pressures.

Joshi gives the LLM two roles. During design, it is a brainstorming partner used to explore vocabulary and possible abstractions. Once that vocabulary is established, it becomes a natural-language interface to a constrained system.

## Why constrained languages help

Domain-driven design builds a shared model and a ubiquitous language that a team can use in both code and conversation. A DSL adds a deliberately limited syntax for expressing the model's concepts and operations. Familiar examples include SQL, Mermaid, PlantUML, Graphviz, and Kubernetes YAML. They are effective with LLMs precisely because they reduce the number of valid ways to express an intent.

A general-purpose language such as Java permits many architectures and idioms. A small DSL removes much of that variation, so a few in-context examples can often communicate its complete surface. For an agent operating in a generate-and-check loop, the language usually brings another crucial component: a deterministic validator such as a parser, schema, type checker, or compiler. The agent can propose a candidate, receive a domain-level error, and repair it without asking a person to interpret a stack trace from a large generated system.

The claim has limits. The language must remain small enough to demonstrate with a few examples, and its semantic model must embody sound design decisions. Designing and maintaining a DSL has a real upfront cost. The payoff is strongest for a well-factored, genuinely constrained domain backed by deterministic validation.

## From diagrams to a semantic model

Joshi first describes a presentation tool for teaching distributed systems. He needed to turn PlantUML sequence diagrams into step-by-step PowerPoint slides. A compact YAML format names a diagram, a title, and the steps to reveal. With the tool and a few examples in context, an LLM can translate an English request into the exact YAML the generator accepts.

This example already contains the two roles. The LLM helps design the step markers and slide vocabulary; after the format exists, it converts natural language into a valid specification. The YAML is not useful because models are generally good at producing indentation. It is useful because a program defines exactly what the fields mean and rejects everything outside that contract.

More complex domains require a semantic model distinct from their surface syntax. Distributed systems are a demanding example because threads, clocks, network delays, storage, retries, and failure interleavings create an enormous design and verification space. Asking a model to generate an entire system leaves all those decisions open in every prompt.

Joshi's [Tickloom](https://github.com/unmeshjoshi/tickloom) framework closes much of that space. Nodes run a single-threaded tick loop. Each tick advances a logical clock and processes work in a fixed order. Messages are records. A `Replica` abstraction already understands peers, broadcasts, and quorums. `Process`, `Network`, `Storage`, and `Clock` define the main seams. With threading, time, and delivery fixed, a prompt can focus on protocol logic instead of inventing infrastructure.

For example, a request for a last-writer-wins quorum store can name Tickloom concepts such as `Replica`, `quorumRequest`, `countResponseIf`, `MessageType`, and `Handler`. Those names refer to concrete types and behavior in the codebase. The semantic model becomes executable context: the LLM fills in a bounded protocol against a substrate the team already understands.

## A DSL for failure scenarios

Implementing a distributed algorithm is only half the problem. Bugs emerge in particular event orderings: a partition heals at the wrong moment, clocks drift, or a read quorum overlaps a write quorum in an unexpected way. A direct test must coordinate futures and manual tick loops, obscuring the scenario's intent.

Tickloom therefore adds an internal scenario DSL. Its vocabulary describes servers, clients, writes, reads, partitions, time changes, ticks, and assertions. The declarative surface compiles to a pure intermediate representation made of steps; a separate interpreter executes those steps against a cluster. Construction, representation, and execution remain separate.

Once this language exists, a natural-language failure description maps closely to valid scenario code. The space of possible outputs is far smaller than the space of arbitrary Java programs. The host compiler checks the syntax, the scenario builder checks the domain rules, and the deterministic simulation checks the resulting behavior. Error messages remain at the level of the scenario, which makes repair useful to both the model and the human reviewer.

The deeper point is that a custom syntax is not always necessary. Clean abstractions already form a vocabulary that can ground a model. A DSL is the more constrained end of that spectrum. Teams should first ask whether named types, narrow interfaces, examples, and validators provide enough structure before paying the cost of a new language.

## Two phases, one source of truth

In the first phase, the LLM helps shape an abstraction or DSL. This work remains iterative because implementation reveals missing concepts and awkward boundaries. The model can suggest alternatives and accelerate experiments, but people still choose the semantic model and accept responsibility for it.

In the second phase, the established language becomes the stable interface. The model translates intent into its vocabulary; deterministic tooling parses, validates, compiles, and tests the result. Reliability comes less from a better prompt than from reducing the degrees of freedom and making incorrect outputs cheaply detectable.

This changes what counts as the source of truth. A prose prompt is ambiguous, difficult to compose, and weak as a durable software artifact. A DSL records domain decisions in a form that can be versioned, validated, diffed, and executed. Prompts become convenient requests against that model rather than the model itself. In an LLM-heavy workflow, the lasting asset is the carefully designed abstraction and its validator: the part of the system that says what outputs are possible, what they mean, and how anyone can know they are correct.
