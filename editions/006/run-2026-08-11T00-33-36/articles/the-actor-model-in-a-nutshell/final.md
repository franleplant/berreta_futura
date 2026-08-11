---
source_ids:
- the-actor-model-in-10-minutes-47394faa
- how-the-actor-model-meets-the-needs-of-modern-di-ebf5a52d
- introduction-to-the-actor-model-using-real-actor-2d2aad66
content_mode: in_a_nutshell
label: IN A NUTSHELL
---

Threads are hard because they share memory, and shared memory is where the bugs breed. The actor model deletes the sharing. An actor is a small piece of code with a private state and an address. It never reaches into another actor. It sends a message instead. Messages wait in a mailbox and are handled one at a time, so no lock is needed and nothing blocks. On receiving a message an actor may do three things: create actors, send messages, and decide what its state will be for the next message. That is the whole vocabulary. When an actor breaks, its parent decides what happens next, usually a restart. And since the only contract is a message and an address, an actor on another machine is no different from one in this process.

## One clerk

Picture a clerk at a window. He keeps a tally on a slip of paper in his pocket. Nobody else can reach into that pocket. Requests arrive on cards, and the cards go on a spike beside him. He takes one card, does the work, writes the new tally, takes the next card.

The spike is the mailbox. The pocket is the state. The clerk is the actor.

## Why the queue is the point

Because the clerk handles one card at a time, the tally is never caught half written. There is no lock, because there is nothing to lock. The invariant holds by the shape of the arrangement, not by discipline.

Send him three cards and he does three jobs in order. If you want three at once, open three windows. Concurrency comes from more clerks, never from more hands in one pocket.

The sender does not wait. He drops the card and walks on. A message carries no return value, so if he wants an answer he gets it later, as another card, at his own window.

## Changing state without mutating it

The clerk's tally reads 0. A card says: add 1. He does not scratch out the 0 while working. He finishes, and declares that for the next card the tally will be 1. State moves forward one message at a time. This is the difference between mutation and succession, and it is why nothing needs guarding.

## Let it crash

You cannot foresee every way a clerk can fail. So do not try. Give him a supervisor, whose only job is to notice the failure and act: restart him at a clean tally, or shut the window for good.

Clerks are hired by clerks, so they form a tree. A parent that stops takes its children with it. Failure is not an exception threaded back up a call stack. It is a fact reported to someone whose business is facts of that kind. Systems built this way heal themselves.

## Address, not place

An address is not a location. It is a name the system promises to honor. Whether the window stands in this hall or in a city on another continent changes the route of the card and nothing else. Write the code once, spread it across machines, lose a machine, keep going.

## Where it lives

Erlang was built on this, and Elixir on Erlang, with processes and supervision in the language itself. Akka brings it to the JVM, Akka.NET to .NET, Actix to Rust, Celluloid to Ruby, Thespian to Python. The libraries help. The language-level version helps more.

Ten minutes of clerks, and the whole trembling machinery of locks becomes optional.
