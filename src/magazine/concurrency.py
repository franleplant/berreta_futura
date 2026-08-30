from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, wait
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")


MAX_WORKERS: int = 8


def worker_count(items: int, workers: int | None = None) -> int:

    if workers is not None:
        return max(1, min(workers, items))
    return max(1, min(items, os.cpu_count() or 1, MAX_WORKERS))


def ordered_map(
    function: Callable[[T], R],
    items: Sequence[T],
    *,
    workers: int | None = None,
) -> list[R]:

    count = worker_count(len(items), workers)
    if count <= 1 or len(items) < 2:
        results: list[R] = []
        failures: list[Exception] = []
        for item in items:
            try:
                results.append(function(item))
            except Exception as error:
                failures.append(error)
        if failures:
            raise failures[0]
        return results

    with ThreadPoolExecutor(max_workers=count, thread_name_prefix="magazine") as pool:
        futures = [pool.submit(function, item) for item in items]

        wait(futures)

        for future in futures:
            error = future.exception()
            if error is not None:
                raise error
        return [future.result() for future in futures]
