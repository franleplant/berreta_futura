---
source_ids:
- the-actor-model-in-10-minutes-47394faa
- how-the-actor-model-meets-the-needs-of-modern-di-ebf5a52d
- introduction-to-the-actor-model-using-real-actor-2d2aad66
content_mode: in_a_nutshell
label: IN A NUTSHELL
---

An actor is the primitive unit of computation. It receives a message and computes. It holds private state that no other actor can change directly, and it shares no memory. Messages wait in its mailbox and it handles them one at a time, so its invariants hold without locks. On each message it can create actors, send messages, and designate what to do with the next message, which is how its state changes. Every actor has an address, so it makes little difference whether the one you write to runs on this machine or another.

### The box office

Suppose a box office with one seller. The seller is an actor. Its private state is the number of seats left for tonight. You do not call a method and wait. You send `buy(2)` and carry on. The seller answers later with a message of its own: sold, or sold out. Messages have no return value. You delegate the work; the result comes back as another message.

One actor is no actor. A box office is a system of them, each with an address so the others can write to it.

### One at a time

The seller's tray is its mailbox. Requests pile up there while it is busy, and it takes them from the front, one at a time. That is the whole defense against races: since at most one message is being processed, nothing needs a lock. Send the seller three requests and it does them in turn. To sell three at once you need three sellers, one per section of the house.

Different actors do run concurrently. A hidden scheduler drives them, and millions of actors can be scheduled on a dozen threads.

### What the seller does with a message

Three things, and only three: create more actors, send messages, designate what to do with the next message. The third is the interesting one. Selling two seats does not mutate a counter in place. The seller declares what its state will be when the next message arrives, two seats lower.

### Letting it crash

There are two kinds of trouble. If the request is bad, say a show that does not exist, the service itself is intact and the error is ordinary. The seller replies with a message saying so. Errors are part of the domain.

If the seller faults internally, that is someone else's job. Erlang's counsel is to let it crash rather than to anticipate every failure point, and to keep the crashing code under a supervisor whose only responsibility is knowing what to do about it. Akka arranges this as a tree: the actor that creates another becomes its parent, and the parent decides whether to restart the child or stop it. Restarts are not visible from outside, and collaborating actors keep sending messages while the target restarts. The most common Erlang strategy is to restart the actor with its initial state.

### An address is enough

If an actor is only a mailbox, some state, and answers to messages, who cares which machine it runs on? Get the message there and you are fine. The same model that keeps state local to a core maps onto state kept in the RAM of separate machines, with changes traveling as packets. Systems built this way can use several computers and recover when one fails.

### Where to find it

Erlang and Elixir are built on the model, and Elixir has language-level support for sending and receiving messages. Akka brings it to the JVM, Akka.NET to .NET, Actix, Bastion and Acteur to Rust, Thespian to Python, Celluloid to Ruby. Elixir can be awkward for what other languages make simple, such as storing some global state. It starts looking appealing when the problem is concurrency.
