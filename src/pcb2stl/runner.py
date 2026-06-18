from __future__ import annotations

import asyncio
import multiprocessing as mp
from typing import Callable

from pebble import ProcessPool

from . import config


class OverloadError(Exception):
    """Too many conversions already in flight; the caller should back off."""


class ConversionTimeout(Exception):
    """A conversion exceeded the hard wall-clock limit and was killed."""


_pool: ProcessPool | None = None
_inflight = 0


def start_pool() -> None:
    global _pool
    if config.INLINE:
        return
    if _pool is None:
        _pool = ProcessPool(max_workers=config.POOL_WORKERS, context=mp.get_context("spawn"))


def stop_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.stop()
        _pool.join()
        _pool = None


async def offload(fn: Callable, *args):
    """Run a CPU-bound conversion off the event loop, in a killable worker process,
    with a hard timeout and simple concurrency backpressure."""
    global _inflight
    if config.INLINE:
        return fn(*args)
    if _inflight >= config.MAX_CONCURRENT:
        raise OverloadError()
    start_pool()
    _inflight += 1
    try:
        future = _pool.schedule(fn, args=args, timeout=config.CONVERT_TIMEOUT_S)
        return await asyncio.wrap_future(future)
    except TimeoutError as exc:
        raise ConversionTimeout() from exc
    finally:
        _inflight -= 1
