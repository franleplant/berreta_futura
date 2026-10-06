---
source_ids:
- the-actor-model-in-10-minutes-47394faa
- how-the-actor-model-meets-the-needs-of-modern-di-ebf5a52d
- introduction-to-the-actor-model-using-real-actor-2d2aad66
content_mode: in_a_nutshell
label: IN A NUTSHELL
---

Your CPU is not getting faster. It is getting more cores. To use them, code must run concurrently, and decades of untraceable bugs have shown that threads are not the way to go. The actor model is one alternative. An actor is a small unit of computation with a private state and a mailbox. It shares no memory. Others reach it only through messages, and it handles those one at a time, so its state needs no locks. When an actor crashes, a supervisor decides what to do. And since only messages pass between actors, it does not matter which machine an actor runs on.

Take a hypothetical web server that counts page views. Thousands of requests arrive together, each wanting to add one to the same number. Keep that counter in mind.

## Actors

An actor is the primitive unit of computation. It receives a message and does some computation based on it. An object receiving a method call is similar. The difference is that actors are completely isolated and never share memory. An actor's private state can never be changed directly by another actor.

Our counter is an actor. Its state is a number, starting at 0. No request handler can touch that number. A handler can only send the counter a message: `increment`.

Actors come in systems. Everything is an actor, and each has an address so others can send to it. One ant is no ant.

## Mailboxes

Messages are asynchronous. The sender does not block; it sends and goes on. The message waits in the receiver's mailbox, a queue, until the actor reaches it.

An actor processes its messages sequentially. Send three messages to the same actor and it runs them one at a time. To run three at once, you need three actors. In Akka, an arriving message goes to the end of the queue, a hidden scheduler runs the actor, the actor takes the message from the front, changes its state, sends messages, and is unscheduled.

So a thousand `increment` messages line up in the counter's mailbox, and the counter takes them one by one. Two never touch the number at the same time. Since at most one message is processed per actor, its invariants hold without synchronization. Different actors still run concurrently, so a system processes as many messages at once as the hardware supports. Akka says millions of actors can be scheduled on a dozen threads.

## What an actor does

On receiving a message, an actor can:

- create more actors;
- send messages to other actors, or to itself;
- designate what to do with the next message.

The third is how actors change state. When the counter at 41 receives `increment`, it designates 42 as the state the next message will find.

Messages have no return value. A handler that wants the current count sends `get`, and the counter answers with a reply message. Waiting for a return value would mean blocking, or running the other actor's work on the same thread.

## Failure

Akka separates two kinds of error. When a task is bad, the service is intact: the actor replies with a message describing the error. Errors become ordinary messages. When the actor itself has an internal fault, supervision takes over.

Erlang introduced "let it crash." You cannot think of every failure point, so you do not program defensively against them all. You let the code crash, and a supervisor, itself an actor, knows what to do. In Akka, an actor that creates another becomes its parent and supervisor. It can restart the child on some failures and stop it on others. Stopping a parent stops its children. The most common strategy is to restart the actor with its initial state. Restarts are not visible from outside: other actors keep sending while the target restarts.

If our counter crashes, its supervisor restarts it. Under that common strategy, it starts again from 0, and the handlers keep sending `increment` throughout.

## Distribution

An actor is code, a mailbox, and private state that responds to messages. Which machine it runs on does not matter, as long as the message gets there. Our counter could live on another node, and the handlers would send the same `increment`. This lets a system use many computers and helps it recover if one fails.

## Where it runs

The most famous language built on the model is probably Erlang. Elixir, built on Erlang, has language-level support for sending and receiving messages. Libraries include Akka for the JVM, Akka.NET, Actix for Rust, Thespian for Python, and Celluloid for Ruby. A Phoenix web server with 2 million concurrent WebSocket connections is the kind of problem where Elixir and the actor model suddenly seem very appealing.
