# Agent State Machines: Building Deterministic Scaffolding for Agents
By Josh Rosen

If you're not using some type of agent state machine, you're completely at the mercy of the nondeterministic nature of models. Are you really okay with models deciding what actions to take and when their work is complete?

This question is the driving force behind agent state machines, which define explicit execution states, the events that move an agent between them, and the rules governing those transitions.

State machines have been used in software for decades, but they are finding new applications in agent infrastructure. Lately, they're being used to control an agent's internal execution loop, manage workflows, and supervise work delegated across multiple agent sessions.

Existing frameworks, such as [LangGraph](https://docs.langchain.com/oss/python/langgraph/overview) and [XState](https://stately.ai/docs/xstate), already provide many of the primitives for managing state and controlling execution. Yet homegrown implementations are becoming increasingly common, often with surprisingly different architectures and relatively little code.

So what are developers actually building when they talk about state machines for agents? How do these implementations interact with existing agent harnesses, and why are developers building their own?

## Why Agents Need State Machines

Most agents are built around a relatively simple execution loop. The model receives a prompt, decides whether to call a tool, processes the result, and repeats until it decides the task is finished. This is, after all, the magic of agents, and it works well when the agent can complete its work within a single session.

Simple looping is fine until an agent must follow a particular process, handle external events, or continue working across multiple sessions. An agent might need approval before taking an action, recover from a failed tool call, or perform validation before reporting completion. Encoding these requirements entirely in prompts or skills leaves the model responsible for following operational rules that could instead be enforced by software.

A state machine moves those rules outside the model. The model can request an action or propose a transition, but the surrounding software determines whether it is permitted.

## State Machines Inside the Agent Loop

One class of implementations controls the agent's internal execution loop. Instead of allowing the model to continuously call tools until it stops, developers explicitly represent states such as reasoning, executing tools, waiting for approval, handling errors, and completing the run.

In a sense, this externalizes and governs the behavior already present in an agent harness. The harness manages model requests, executes tools, handles their results, and determines when execution should continue. Making the state machine a first-class construct converts these behaviors into defined states and transitions.

[Stately Agent](https://github.com/statelyai/agent) takes this approach using XState. Developers define states, permitted events, and transition guards in TypeScript. The application starts the machine using runAgent(), supplying executors that connect to the model provider through an SDK. When a state requests a model decision, the executor calls the model and returns a proposed event. XState validates the event and applies the transition.

For example, a customer service agent might enter a drafting state, invoke a model to generate a response, and move into an approval state. A human approval event advances it to sending, while rejection returns it to drafting. The model writes the response, but the application controls which transitions are permitted.

This approach can replace some of the control logic inside a conventional agent harness or operate as a separate execution layer around it.

## State Machines for Agent Workflows

Another class uses state machines to guide agents through a workflow by controlling a sequence of activities. Here the state machine operates above individual model calls, determining which stage of a workflow should execute next.

Consider an agent responsible for researching a company, preparing a report, and obtaining approval before publication. Each stage of the workflow can invoke an LLM, execute conventional code, or delegate work to another agent. Review might return the report to drafting, while certain outcomes could require human intervention.

These systems are commonly implemented as execution graphs. Developers define nodes that perform operations, shared state that carries information between them, and transitions that determine which nodes execute next.

[LangGraph](https://docs.langchain.com/oss/python/langgraph/overview) implements this through its StateGraph API. Developers register functions as nodes, connect them with conditional edges, and invoke the compiled graph using graph.invoke() or graph.stream().

[Mastra](https://mastra.ai/docs/workflows/overview) provides a TypeScript alternative using createStep() and createWorkflow() to compose executable steps.

[n8n](https://docs.n8n.io/advanced-ai/) offers a visual approach, connecting agent nodes, conditional branches, and conventional application integrations into executable workflows.

The workflow runtime typically initiates execution, either through an application API call or an external trigger. Developers can also expose an entire workflow as a tool, allowing an agent to invoke it while the workflow runtime controls its internal steps.

LangGraph also supports durable execution through [checkpointing](https://docs.langchain.com/oss/python/langgraph/persistence), which saves the state of the execution graph as it progresses. This allows an interrupted workflow to resume from a saved state, supports human intervention, and provides a history of execution.

## State Machines for Supervising Agents

A third class operates outside the agent entirely. Instead of controlling model calls or prescribing a workflow, these state machines manage the lifecycle of work delegated to independent agents.

[OpenAI's Symphony](https://github.com/openai/symphony/blob/main/SPEC.md) provides a concrete example. Symphony monitors an issue tracker and dispatches Codex sessions to work on eligible tasks. It runs Codex through its app-server interface, allowing each agent to operate independently while Symphony monitors execution and handles retries. The state machine governs which work can run and what happens when an agent finishes.

A related approach appears in [Pi Missions](https://github.com/0xkuze/pi-missions), which integrates directly into the Pi harness through its extension API. The extension exposes tools that the supervising agent can call to dispatch workers, validate results, and advance the mission. Each worker runs in a fresh Pi process, while the extension maintains the mission state and enforces transitions.

Whereas Symphony operates as an external supervisor, Pi Missions embeds the orchestration tools inside the supervising agent's harness. Neither needs to control the internal execution of individual workers. Instead, the state machine governs work across multiple agent runs, allowing the agents to decide how to accomplish their assigned tasks.

## State Machines for the Work Itself

Another approach is to model the state of the work independently of how agents execute it. Rather than controlling an agent loop or scheduling a workflow, the system defines a state machine of work where work isn't accepted until dependent work is completed.

[ThruWire](https://thruwire.ai/) takes this approach through a graph of AI checkpoints. Each checkpoint defines a requirement that must be satisfied, with evidence supporting its completion. Dependencies between checkpoints establish which conditions must be met before others can be accepted. Agents are free to determine how to accomplish the work, while the system evaluates whether the resulting evidence satisfies the requirements.

Note that these checkpoints are fundamentally different from execution checkpoints in systems like LangGraph. LangGraph saves execution state so an interrupted process can resume. ThruWire maintains the state of the work itself, including its requirements, dependencies, and validation evidence.

## Why Developers Keep Building Their Own

Given the available infrastructure, why are developers still implementing their own state machines?

The first reason is simplicity. A developer who only needs to track five bespoke task states and dispatch a coding agent may not need a general-purpose graph runtime. A collection of transition functions and a polling loop might be sufficient.

The second is that many applications already have an agent execution environment. Developers building around Claude Code, Codex, or Pi can preserve the existing harness and manage task lifecycles externally. Symphony communicates with Codex through its app-server protocol, while Pi Missions integrates through Pi's extension system. Neither requires replacing the underlying harness.

A third reason is integration with existing infrastructure. Teams may already have databases, queues, schedulers, and application-specific state machines. Adding agent execution to these systems can be easier than adopting a separate runtime, particularly when rules for task ownership, concurrency, and recovery already exist.

Of course, there is a tradeoff. Developers who start with simple state machines can eventually find themselves implementing checkpointing, distributed locking, scheduling, observability, and crash recovery. At that point, they may have rebuilt much of the infrastructure they initially avoided.

## How Developers Are Building Their Own

Building a custom state machine doesn't necessarily require much code. Developers can represent state in a JSON file or database and implement transitions as functions that validate events and update the state. The complexity comes from integrating those transitions with agent execution and ensuring they are enforced consistently.

The main implementation choice is how the state machine interacts with the agent harness. An external orchestrator might launch agents through an SDK or subprocess, while a harness extension can expose tools that agents call to request transitions. Alternatively, developers can implement an MCP server with tools like claim_task and complete_task, allowing agents using different harnesses to interact with the same state machine.

In each case, the state machine maintains the authoritative state and enforces the transition rules. An agent might report completion through a tool call or return a result to its orchestrator, which then validates the request and updates the state. The state is typically persisted in files or a database so it can be accessed across agent runs.

More sophisticated implementations also need to handle recovery and interrupted executions. Persisting state alone does not make execution durable, so developers may use frameworks such as [Temporal](https://temporal.io/), [Restate](https://restate.dev/), or [DBOS](https://www.dbos.dev/) to provide durable execution around their state machines.

## Deterministic Scaffolding

What's interesting about these implementations is that developers are applying state machines at different levels of agent infrastructure. There isn't necessarily one state machine that needs to control the entire system.

These different layers of control can also work together. An agent's internal execution loop might be governed by one state machine, while another supervises its work across multiple sessions. A separate system might then determine whether that work satisfies its requirements.

As agents take on longer-running and more consequential work, I expect these deterministic layers to become a standard part of agent infrastructure.
