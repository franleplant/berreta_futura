---
label: EDITORIAL
title: The Lock You Cannot See
byline: The Editors
---

The promise was no locks anywhere. One actor, one message at a time, invariants held without synchronization.

Then state met disk. Storage is I/O, every `await` is a door, and in a Durable Object two requests walked through and handed out the same number. The fix was to shut the doors: while a storage operation runs, no other event is delivered. It is called an input gate. It is a mutex with better manners and no name at the call site.

Worth it. Also a debt. A lock you cannot see is a lock you cannot reason about, and the escape hatch is one word: `allowConcurrency: true`. It will travel by copy and paste, out of a benchmark and into code that needed the gate.

So the next bad night will not be the race that got fixed. It will be one event firing two calls with no await between them: deterministic, trivial to reproduce, shipped anyway, because nobody looks for a lock they were told they did not have.
