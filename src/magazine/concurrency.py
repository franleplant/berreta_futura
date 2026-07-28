"""The one place that decides how much of the machine a build may use.

The stages worth parallelising here are subprocess-bound: they hand a page to
Poppler or another child and then block on it.  **Threads, not processes, are
the right tool for that shape.**  The interpreter releases the GIL for the
whole wait, so a thread costs a stack rather than an interpreter; nothing has
to be picklable, which matters because the work items close over live layout
objects; and no worker is forked, which matters more, because this process has
already loaded native text-shaping libraries whose state does not survive a
fork intact.  A process pool would buy nothing back for that.

Parallelism is nonetheless a hazard here, because the build is byte-for-byte
reproducible and recorded review decisions bind the SHA-256 hashes of the PDFs
a human actually inspected.  Anything that let thread scheduling reach the
output, or even the diagnostics, would put those bindings at risk.  So
``ordered_map`` is deliberately narrower than the executor it wraps, and three
rules make the fan-out unobservable:

1. **Results come back in input order**, never completion order, so a caller
   can no more tell how the work was scheduled than it can tell how a serial
   loop was.
2. **When several items fail, the lowest-index failure is the one raised.**
   Reporting whichever thread happened to fail first would make the error
   message -- and therefore a build log a human reads to decide what to fix --
   depend on scheduling.  Losing a sibling's traceback is the price; the
   ordering is worth more than the second traceback.
3. **Every item runs, whatever any other item does, and the failure is raised
   only once they all have.**  Stopping on the first failure would make the set
   of files left on disk depend on how far the queue had drained when that
   failure landed, and a sibling caught mid-write would leave a truncated one.

Passing ``workers=1`` is the debuggable counterpart: it builds no pool at all
and runs the items in order on the calling thread, so an exception arrives with
the stack that actually raised it rather than one restitched from a queue.  It
is an exact reproduction of a parallel run and not merely a similar one -- the
same items execute, so the same side effects land, and the same exception
escapes -- which is what makes it usable for diagnosing a 55-subprocess
fan-out that failed: the serial rerun reproduces that failure instead of a
different one.  This is why the serial path also finishes every item before
raising.  It forgoes the early exit a comprehension would give it, because
exiting early would write fewer files than the run under diagnosis did.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, wait
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")


MAX_WORKERS: int = 8
"""Ceiling on threads per fan-out, whatever the core count.

The stages this serves are bound by child processes that are themselves
memory-hungry rasterisers, so the useful width is set by what the machine can
hold at once rather than by how many cores it has to spare.  The cap also
keeps a build on a large host from behaving unlike a build on a laptop in any
way but wall clock.
"""


def worker_count(items: int, workers: int | None = None) -> int:
    """Return how many threads to run ``items`` on; never fewer than one.

    A caller's explicit ``workers`` is honoured but clamped to the work that
    exists, because a pool wider than its queue only costs threads.  ``None``
    means "decide for me" and yields the narrowest of the work, the machine
    and ``MAX_WORKERS``.
    """

    if workers is not None:
        return max(1, min(workers, items))
    return max(1, min(items, os.cpu_count() or 1, MAX_WORKERS))


def ordered_map(
    function: Callable[[T], R],
    items: Sequence[T],
    *,
    workers: int | None = None,
) -> list[R]:
    """Apply ``function`` to every item on threads and return the results.

    One contract, obeyed identically however wide the fan-out is: every item
    runs whatever any other item does, successful results come back in input
    order, and if any item raised then the exception that escapes is the one
    from the lowest-index item that raised, unwrapped and un-retyped, raised
    only once every item has finished.  Note what this rules out, since it is
    the tempting shortcut: this is *not* the comprehension it resembles, which
    would abandon the remaining items at the first raise.

    ``workers=1`` obeys that contract without constructing a pool, so it is a
    faithful rerun of a parallel failure rather than an approximation of one.
    """

    count = worker_count(len(items), workers)
    if count <= 1 or len(items) < 2:
        # With nothing to overlap, a pool would only move the work off the
        # caller's stack and carry the raising frame away with it.  The loop
        # still runs to the end and raises afterwards, because a fallback that
        # stopped early would reproduce a different build than the one it was
        # called to diagnose.
        results: list[R] = []
        failures: list[Exception] = []
        for item in items:
            try:
                results.append(function(item))
            except Exception as error:
                # Held rather than handled, and re-raised below once the rest of
                # the items have had their turn.  ``BaseException`` is
                # deliberately outside this: a Ctrl-C is an instruction to
                # abandon the build, not one item's failure, and catching it
                # here would grind on through the remaining items instead.
                failures.append(error)
        if failures:
            raise failures[0]
        return results

    with ThreadPoolExecutor(max_workers=count, thread_name_prefix="magazine") as pool:
        futures = [pool.submit(function, item) for item in items]
        # ``wait`` earns its place by refusing to return early: whatever has
        # already failed, every item -- including any still sitting in the queue
        # when that failure became visible -- has run by the time this returns.
        # It is not what makes the error deterministic; the loop below is.
        wait(futures)
        # Walking ``futures`` in submission order, rather than as they complete,
        # is what makes both the order and the choice of error independent of
        # the schedule: the first exception found this way is the lowest-index
        # one no matter which thread actually failed first.
        for future in futures:
            error = future.exception()
            if error is not None:
                raise error
        return [future.result() for future in futures]
