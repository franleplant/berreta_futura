---
source_id: software-factories-light-and-dark-ef463732
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

A software factory is harnessed loops at scale. Run the loop with humans in it—a light factory—and you trade judgment and concentration against speed and breakage. Ignore the humans—a dark factory—and agents can scope, build, and ship code without anyone reading the details. If people stop reading, however, they stop understanding the software. The hardest job becomes deciding which checks to build and how much autonomy to delegate.

## Loop, harness, factory

A loop is one agent doing one job repeatedly: gather context, act, check the result, and continue until a condition is met. A harness supplies the walls around it—the sandbox, tools, durable memory, and gates that define done. A factory is many harnessed loops drawing from a queue and flowing through a review gate into production. It is not a bigger agent; it is an org chart made of loops.

The factory closes its own circuit. Intent and production signals feed the queue; the harness builds; tests, static analysis, and scanning check the work; approval permits deployment; monitoring turns production back into signals. Almost every box can run cheaply at scale. The stubbornly expensive box is the review gate: judgment.

## The narrow neck

A dark factory removes that gate. Its apparent throughput rises dramatically because code ships after machine verification alone. Yet it also accumulates comprehension debt: the gap between how much code exists and how much any person understands. In a mature system, the reckoning is likely to be quiet and late, after months of green tests and unread changes.

Generation is a wide mouth; verification is the narrow neck. Back pressure means giving a loop only as much autonomy as can be cheaply and reliably verified. A better model does not automatically solve the problem, because architectural quality reveals itself over months and years rather than in the crisp seconds of a test result.

## Turning the lights on where judgment lives

A lit factory keeps agents doing most of the building but moves human judgment upstream into product, design, and architecture as well as review. An hour spent reviewing a two-hundred-line plan can prevent a painful review of two thousand generated lines. Types, test seams, legible boundaries, short call stacks, and dependency injection become a hard-to-fake safety net outside the model.

Some small loops can earn the dark: the check is cheap, frequent, immediate, stable, and difficult to game. A nightly job that fixes one lint violation and opens one small pull request may qualify. Authentication, billing, public contracts, and long-lived architectural decisions do not. All dark produces a system no one can repair; all lit produces a review bottleneck. The skilled work is placing each switch.

The person never left the factory; the person moved to the outer loop. Agents can investigate, implement, test, and report. Engineers still decide whether the approach is right, inspect the evidence at the boundary, approve the change, and carry the consequences of being wrong. Robots can operate in the dark. Humans need to see what they are responsible for.
