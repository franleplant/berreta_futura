"""The fan-out seam: parallel work whose results a caller cannot date.

Every test here is a determinism claim, not a speed claim, because the value
``ordered_map`` adds over a bare ``ThreadPoolExecutor`` is that a build's
output and its error messages stay independent of thread scheduling -- the
property recorded review decisions rest on, since they bind the hashes of the
PDFs a human inspected.  So nothing below is timed: overlap is proved by a
rendezvous that cannot clear unless items really run together, and reversed
completion is *forced* with events rather than coaxed with sleeps.  A test that
raced would be worse than no test, because it would pass on the run that
mattered.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from magazine import concurrency
from magazine.concurrency import MAX_WORKERS, ordered_map, worker_count

_RENDEZVOUS_TIMEOUT = 5.0
"""Seconds any test will wait for a peer item before failing.

Generous enough that a loaded machine cannot trip it, bounded so a broken
implementation fails the suite instead of hanging it.
"""


def _no_pool(*args: object, **kwargs: object) -> None:
    """Stand in for ``ThreadPoolExecutor`` where building one is the bug."""

    raise AssertionError("the serial path must not construct a thread pool")


def test_results_keep_input_order_when_completion_order_is_reversed():
    """Input order survives a completion order deliberately inverted."""

    size = 6
    finished = [threading.Event() for _ in range(size)]
    completions: list[int] = []
    lock = threading.Lock()

    def blocked_on_its_successor(index: int) -> str:
        # Each item waits for the item *after* it, so the last one submitted is
        # the first to finish and the first is the last.  The chain is a fact
        # about the schedule, not a bet on one: no wall-clock ordering is
        # involved, and a run that returned completion order would come back
        # exactly reversed.
        if index + 1 < size:
            assert finished[index + 1].wait(_RENDEZVOUS_TIMEOUT), "successor stalled"
        with lock:
            completions.append(index)
        finished[index].set()
        return f"item-{index}"

    results = ordered_map(blocked_on_its_successor, list(range(size)), workers=size)

    assert results == [f"item-{index}" for index in range(size)]
    assert completions == list(reversed(range(size)))


def test_the_lowest_index_failure_is_the_one_that_escapes():
    """A later item failing first does not get to own the error message.

    Two workers to six items, not six to six, because the real build feeds 55
    items through eight and the interesting state is the one an equal count
    cannot produce: items still sitting in the queue when a failure is already
    visible.  Those are the only items there is ever anything to cancel, so an
    equal count tests the no-cancellation rule vacuously.  Do not widen this
    call to one worker per item to make it read more simply; the width is the
    subject of the test.
    """

    early = RuntimeError("item 1")
    late = KeyError("item 3")
    late_failed = threading.Event()
    calls: list[int] = []
    lock = threading.Lock()

    def fail_at_one_and_three(index: int) -> int:
        if index == 1:
            # Parking item 1 here does double duty.  It guarantees the
            # high-index failure happens first, the only arrangement that can
            # tell "lowest index wins" apart from "first failure wins"; and it
            # holds one of the only two workers until then, so the other has to
            # reach item 3 by taking 2 first, and items 4 and 5 are still behind
            # item 3 in the queue at the moment it fails.
            assert late_failed.wait(_RENDEZVOUS_TIMEOUT), "item 3 never failed"
        with lock:
            calls.append(index)
        if index == 3:
            late_failed.set()
            raise late
        if index == 1:
            raise early
        return index

    # KeyError is no kind of RuntimeError, so the matched type alone rules out
    # the late failure, and identity rules out any re-wrapping on the way out.
    with pytest.raises(RuntimeError) as caught:
        ordered_map(fail_at_one_and_three, list(range(6)), workers=2)

    assert caught.value is early
    # Item 0 appends before finishing and item 1 appends only after item 3 has,
    # so the first three calls can only be these three, in this order.  That
    # makes the shape a fact rather than a hope: items 4 and 5 had not been
    # entered when the first failure landed, so they were still queued.
    assert calls[:3] == [0, 2, 3]
    # And they ran anyway.  Nothing is cancelled and nothing is dropped, because
    # a fan-out that stopped partway would leave a set of files on disk that
    # depended on how far the queue had drained.
    assert sorted(calls) == list(range(6))


def test_a_single_worker_runs_every_item_on_the_calling_thread(monkeypatch):
    """``workers=1`` is a serial loop here, not a one-thread pool."""

    monkeypatch.setattr(concurrency, "ThreadPoolExecutor", _no_pool)

    threads = ordered_map(lambda _: threading.get_ident(), list(range(4)), workers=1)

    assert threads == [threading.get_ident()] * 4


def test_a_single_worker_propagates_the_items_own_exception(monkeypatch):
    """The debuggable fallback adds nothing between the raise and the caller."""

    monkeypatch.setattr(concurrency, "ThreadPoolExecutor", _no_pool)
    failure = ValueError("item 2")

    def fail_at_two(index: int) -> int:
        if index == 2:
            raise failure
        return index

    with pytest.raises(ValueError) as caught:
        ordered_map(fail_at_two, list(range(4)), workers=1)

    assert caught.value is failure


def test_a_single_worker_keeps_going_after_an_item_fails(monkeypatch):
    """The serial path owes the same side effects as the parallel one.

    This is the test that stops the serial path being written back as a list
    comprehension.  A comprehension would call items 0 and 1 and stop, so the
    rerun a human reaches for after a parallel failure would write fewer files
    than the run they are trying to reproduce.
    """

    monkeypatch.setattr(concurrency, "ThreadPoolExecutor", _no_pool)
    early = RuntimeError("item 1")
    late = KeyError("item 2")
    calls: list[int] = []

    def fail_at_one_and_two(index: int) -> int:
        calls.append(index)
        if index == 1:
            raise early
        if index == 2:
            raise late
        return index

    # Serially the *lowest*-index failure is also the first one, so the matched
    # type only proves the later KeyError did not overwrite it; identity is what
    # proves the item's own exception object came out unwrapped.
    with pytest.raises(RuntimeError) as caught:
        ordered_map(fail_at_one_and_two, list(range(4)), workers=1)

    assert caught.value is early
    assert calls == [0, 1, 2, 3]


def test_a_lone_item_needs_no_pool_even_without_a_worker_count(monkeypatch):
    """One item cannot overlap with anything, so it stays on this thread."""

    monkeypatch.setattr(concurrency, "ThreadPoolExecutor", _no_pool)

    assert ordered_map(lambda _: threading.get_ident(), ["only"]) == [
        threading.get_ident()
    ]


def test_several_workers_really_run_at_the_same_time():
    """The point of the module: the items are genuinely in flight together."""

    size = 4
    rendezvous = threading.Barrier(size)

    def meet_the_others(index: int) -> int:
        # No item can pass this line until all four have reached it, so a
        # serialised implementation breaks the barrier and fails the test
        # rather than passing more slowly.
        rendezvous.wait(_RENDEZVOUS_TIMEOUT)
        return index

    assert ordered_map(meet_the_others, list(range(size)), workers=size) == list(
        range(size)
    )


def test_an_empty_sequence_returns_empty_without_calling_the_function(monkeypatch):
    """No work means no function calls and no pool to run them on.

    Refusing the pool here is worth pinning because ``worker_count`` floors at
    one thread, so an implementation that keyed the parallel path off the count
    alone would spin up a pool, and the empty result would hide it.
    """

    monkeypatch.setattr(concurrency, "ThreadPoolExecutor", _no_pool)

    def never_called(item: object) -> object:
        raise AssertionError("nothing was submitted, so nothing may run")

    assert ordered_map(never_called, []) == []


def test_worker_count_clamps_an_explicit_request_to_the_work_that_exists():
    """An explicit width is honoured between one thread and one per item."""

    assert worker_count(3, 2) == 2
    assert worker_count(3, 3) == 3
    # Wider than the queue buys nothing, so the surplus threads are refused.
    assert worker_count(3, 99) == 3
    # Zero and negative are floored rather than rejected: the serial path is a
    # correct answer to "as little parallelism as possible", and refusing here
    # would make a config typo an error a build could not proceed past.
    assert worker_count(3, 0) == 1
    assert worker_count(3, -4) == 1
    assert worker_count(0, 99) == 1
    assert worker_count(0, 0) == 1


def test_worker_count_defaults_to_the_narrowest_of_work_machine_and_cap(monkeypatch):
    """With no request, the machine is consulted but never exceeded."""

    def with_cpus(count: int | None) -> None:
        monkeypatch.setattr(concurrency, "os", SimpleNamespace(cpu_count=lambda: count))

    with_cpus(4)
    assert worker_count(64) == 4
    assert worker_count(2) == 2

    # A large host does not widen a build past the ceiling; a build on 64 cores
    # differs from a build on four in wall clock only.
    with_cpus(64)
    assert worker_count(64) == MAX_WORKERS

    # ``os.cpu_count`` is documented as possibly returning None, and the answer
    # then is one thread rather than a TypeError.
    with_cpus(None)
    assert worker_count(8) == 1
    assert worker_count(0) == 1
