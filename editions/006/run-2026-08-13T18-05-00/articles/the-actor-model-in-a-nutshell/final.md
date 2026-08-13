---
source_ids:
- the-actor-model-in-10-minutes-47394faa
- how-the-actor-model-meets-the-needs-of-modern-di-ebf5a52d
- introduction-to-the-actor-model-using-real-actor-2d2aad66
content_mode: in_a_nutshell
label: IN A NUTSHELL
---

**Thirty seconds.** Cores multiplied; clock speeds did not. Threads sharing memory gave us decades of untraceable bugs. The actor model takes another road. An actor is the primitive unit of computation. It keeps private state that no other actor can change directly, and it communicates only by sending messages. Each actor handles one message at a time, so its invariants hold without locks. When an actor fails, its parent decides what happens. When it runs on another machine, the only thing that changes is the trip the message takes.

## A ticket counter

Take a hypothetical counter that sells seats for one show. Its private state is the number of seats left, say one hundred. You cannot reach over and edit that number. You write a note, "sell me two", and drop it in the counter's slot.

The slot is a mailbox.

## The mailbox

Messages are sent asynchronously. Sending one does not transfer your thread of execution to the counter, so you do not block; you walk away and do other work. The counter reads notes one at a time. If ten arrive at once, nine wait in the queue.

That serialization is the trick. Since at most one message is processed per actor, the actor's invariants are kept without synchronization, and no locks are used anywhere. Two buyers cannot both take the hundredth seat.

Messages have no return value. By sending one you delegate work; the receiving actor sends the result back as a reply.

If you want three sales at once, you need three counters. One actor is no actor. They come in systems, and each needs an address so the others can write to it: a building of identical counters, each blind to the rest, reachable only by name. Millions of them can be scheduled efficiently on a dozen threads.

## Three things an actor can do

On receiving a message, an actor can create more actors, send messages to other actors, or designate what to do with the next message.

The third is how state mutates. The counter holding one hundred seats does not overwrite that number when it sells two. It designates that for the next note it receives, the state will be ninety-eight.

## Let it crash

Two kinds of failure. The first is a bad request, a show that does not exist. The service is intact; only the task was wrong, so the counter replies with a message presenting the error. Errors are part of the domain and become ordinary messages.

The second is an internal fault. Erlang introduced the "let it crash" philosophy: do not program defensively against every possible failure point, because you cannot think of them all. Let the code crash, and put it under a supervisor whose only responsibility is knowing what to do about it. Akka enforces that actors form a tree, so an actor's parent supervises it and may restart it or stop it; stopping a parent recursively stops its children. The most common strategy is restarting the actor with its initial state. Restarts are not visible from outside, and collaborating actors can keep sending messages while the target restarts.

## Somewhere else

If an actor is a mailbox, a private state and a rule for replying, its machine is not your concern. State is local, and changes travel as messages, which matches how memory actually works, and maps exactly onto remote communication where changes cross the network as packets. The counter can stand in another building. This lets us build systems across several computers, and helps us recover when one of them fails.

## Where to find it

Libraries exist for many languages: Actix, Bastion and Acteur for Rust, Akka for Java and Scala, Akka.NET, Thespian for Python, Celluloid for Ruby. Erlang was designed around the model to support highly available, concurrent, distributed systems, and Elixir is built on Erlang with language-level support for sending and receiving messages. Simple tasks in Elixir, like holding global state, can frustrate a newcomer; the appeal shows up on harder problems, such as a web server with two million concurrent websocket connections.
