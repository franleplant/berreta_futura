# Introduction to the Actor Model, Using “Real” Actors

By John Palgut · Grio Blog · March 4, 2021

![](media/001.png)

When you hear the phrase “Actor Model,” your mind may have gone to Hollywood, but the Actor Model is actually a programming model designed to make performing concurrent operations simpler.

## The Actor Model is About Concurrency

The Actor Model is a programming model for dealing with concurrency, which is doing more than one thing at a time. Most programming languages behave sequentially; you can only do one thing at a time, in a specific order. While this model works in many situations, there are specific scenarios where concurrency is essential. For example, web servers often handle many requests at a single time. If your web server could only handle a single request at a time, only one person would be able to use the website at any given time. That would make it incredibly challenging to increase traffic on your site.

[via GIPHY](https://giphy.com/gifs/star-trek-data-QQKhpfeRQqz6M)

However, it’s not as simple as adding concurrency to your application. As most software developers can attest, concurrency is very tricky in most programming languages. The Actor Model was developed to help simplify concurrency.

## What Makes an Actor?

To understand the Actor Model, we must first define an actor by examining their defining features:

### Actors are Primitives:

![](media/002.jpg)

When we say primitive, we don’t mean they are cavemen. Primitive means that actors are the smallest, essential piece of the actor model. They are the Lego brick that you use to build your Lego tower.

### Actors Have Mailboxes:

![](media/003.jpg)

As discussed below, actors are capable of sending and receiving messages with other actors. If an actor is busy performing a task when they receive a new message, the message is stored in the actor’s mailbox until they have the time to process the message.

### Actors Have Local State:

![](media/004.jpg)

Local state refers to an actor’s view of the world. Just like Keanu’s sad disposition in this photo, an actor’s local state is entirely their own and can change based on the messages they receive. While actors can share their state with others, they must choose to do so.

## What Can an Actor Do?

In the Actor Model, there are three specific things that actors can do to help them interact with the world:

![](media/001.png)

### Actors Can Create New Actors:

![](media/005.jpg)

The first thing an actor can do is create new actors. This process is similar to Agent Smith cloning himself in the Matrix. When an actor makes a new actor, it can either create a copy of itself or a different actor.

Actors frequently work in a hierarchy, with one actor supervising multiple workers. In this scenario, if a worker crashes, the supervisor can make a new worker that will continue where the old worker left off. Similarly, if multiple workers are created, the supervisor can clone itself to create additional supervisors to perform oversight.

### Actors Can Send a Message to An Actor:

![](media/006.jpg)

Actors can send messages to both other actors and themselves. As discussed above, if actors are busy doing something, messages will sit in their mailboxes until they have time to process the message.

A common pattern of implementing a loop with the actor model is for an actor to send a message to itself. When the actor receives their message, it does some work, and then sends another message to themselves continuing the loop.

### Actors Can Change Their State:

![](media/007.jpg)

When an actor receives a message, they can choose to change their local state. Luke Skywalker presents a perfect example of this state change. When Luke is initially introduced in Star Wars Episode 4, Luke’s state doesn’t know anything about his father (local state). However, when Obi-Wan Kenobi tells Luke about his friendship with Luke’s father (Luke receives a message), Luke decides that “my father was a good guy” (local state change).

In Episode 5, when Luke meets Darth Vader (spoilers ahead), he tells Darth Vader that he killed his father(sends a message). Darth Vader responds by saying, “I am your father.”(another message). When Luke receives this message, it causes Luke to once again update his state to “my father is a bad guy.”

Though this example simplifies both the Star Wars plotline and the Actor Model, it nonetheless depicts how actors receive and process messages as well as update their local state.

## How Does This Help with Concurrency?

Now that we know what actors can do, we can understand how the Actor Model simplifies concurrency. Actors are isolated in the Actor Model, meaning each actor only has to worry about their own state and actions. Actors are often written so they have a single purpose or task they are responsible for. This allows you to break down large concurrency problems into smaller, more focused parts. Rather than thinking about all the things that may be happening at a given time, you can write code that handles these smaller, more focused, problems. Once you have the small problems solved, you can combine them to solve the whole of the larger problem.

[via GIPHY](https://giphy.com/gifs/mrw-confused-travolta-confusedtravolta-54rv8mQZtZgyY)

## Actor Model Libraries

Oftentimes when looking to add a feature to your codebase, you do so by adding a library. There are several Actor Model libraries for a variety of languages. Some of the popular libraries include:

- [Rust](https://www.rust-lang.org/): [Actix](https://actix.rs/), [Bastion](https://github.com/bastion-rs/bastion), [Acteur](https://docs.rs/acteur/0.12.2/acteur/)
- [Java](https://www.java.com/en/)/[Scala](https://www.scala-lang.org/): [Akka Framework](https://akka.io/)
- [.NET](https://dotnet.microsoft.com/languages): [Akka.NET](https://getakka.net/)
- [Python](https://www.python.org/): [Thespian](https://thespianpy.com/doc/)
- [Ruby](https://www.ruby-lang.org/en/): [Celluloid](https://github.com/celluloid/celluloid)

## Elixir is Built Around the Actor Model

With the actor model, having a library will oftentimes only get you so far. Especially if a language was not designed with concurrency in mind. It would be even better if there was a language designed around the model so that you had language-level support.

The answer: [Elixir](https://elixir-lang.org/).

![](media/008.jpg)

Elixir is built on top of [Erlang](https://www.erlang.org/), which was designed around the Actor Model in order to support building highly available, concurrent, distributed systems. It has language-level support for sending and receiving messages from various actors.

Elixir can oftentimes be challenging to new programmers looking to perform tasks that would be simple in other languages, such as storing some global state. However, when you have more complicated problems that involve concurrencies, such as [a web server with 2 million concurrent web socket connections](https://www.phoenixframework.org/blog/the-road-to-2-million-websocket-connections), Elixir and the Actor Model suddenly seem very appealing. Elixir provides a streamlined platform for concurrent processes that are typically very complicated, and in some cases not possible, in other languages.

Overall, I would highly recommend you check out Elixir and the Actor Model the next time you’re faced with a challenge that requires concurrency.
