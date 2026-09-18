"""Separate caller cancellation from backend task and executor-future results."""

from __future__ import annotations

import asyncio
import contextlib
import time
from concurrent.futures import Future as ConcurrentFuture
from dataclasses import dataclass
from threading import Lock
from typing import TYPE_CHECKING, Final, Generic, NoReturn, TypeVar, cast

from ._api import _append_exception_context, _raise_chained_errors

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

_T = TypeVar("_T")


class _AsyncTransitionUnavailableError(Exception):
    pass


@dataclass(frozen=True)
class _BackendOutcome(Generic[_T]):
    value: _T | None = None
    error: BaseException | None = None


class _AsyncTransitionGate:
    def __init__(self) -> None:
        self._tail_lock: Final[Lock] = Lock()
        self._tail: ConcurrentFuture[None] | None = None

    @contextlib.asynccontextmanager
    async def hold(self) -> AsyncIterator[None]:
        ticket: ConcurrentFuture[None] = ConcurrentFuture()
        with self._tail_lock:
            predecessor = self._tail
            self._tail = ticket
        if predecessor is not None:
            try:
                await _wait_until_done(asyncio.wrap_future(predecessor))
            except asyncio.CancelledError:
                predecessor.add_done_callback(lambda _predecessor: self._leave(ticket))
                raise
        try:
            yield
        finally:
            self._leave(ticket)

    @contextlib.asynccontextmanager
    async def hold_for_acquire(
        self,
        *,
        blocking: bool,
        cancel_check: Callable[[], bool] | None,
        deadline: float | None,
        poll_interval: float,
    ) -> AsyncIterator[None]:
        ticket: ConcurrentFuture[None] = ConcurrentFuture()
        with self._tail_lock:
            predecessor = self._tail
            self._tail = ticket
        if predecessor is not None and not predecessor.done():
            try:
                await self._wait_for_predecessor(
                    predecessor,
                    blocking=blocking,
                    cancel_check=cancel_check,
                    deadline=deadline,
                    poll_interval=poll_interval,
                )
            except BaseException:
                predecessor.add_done_callback(lambda _predecessor: self._leave(ticket))
                raise
        try:
            yield
        finally:
            self._leave(ticket)

    @staticmethod
    async def _wait_for_predecessor(
        predecessor: ConcurrentFuture[None],
        *,
        blocking: bool,
        cancel_check: Callable[[], bool] | None,
        deadline: float | None,
        poll_interval: float,
    ) -> None:
        if not blocking:
            raise _AsyncTransitionUnavailableError
        waiter = asyncio.wrap_future(predecessor)
        while not predecessor.done():
            if cancel_check is not None and cancel_check():
                raise _AsyncTransitionUnavailableError
            if deadline is not None:
                if (remaining := deadline - time.perf_counter()) <= 0:
                    raise _AsyncTransitionUnavailableError
                wait_interval = min(poll_interval, remaining) if cancel_check is not None else remaining
            else:
                wait_interval = poll_interval if cancel_check is not None else None
            await asyncio.wait((waiter,), timeout=wait_interval)

    def _leave(self, ticket: ConcurrentFuture[None]) -> None:
        with self._tail_lock:
            if self._tail is ticket:
                self._tail = None
        ticket.set_result(None)


async def _drain_future(future: asyncio.Future[_BackendOutcome[_T]]) -> _T:
    while not future.done():
        with contextlib.suppress(asyncio.CancelledError):
            await _wait_until_done(future)
    return _future_result(future)


async def _wait_until_done(future: asyncio.Future[_T]) -> None:
    if not future.done():
        await asyncio.wait((future,))


def _future_result(future: asyncio.Future[_BackendOutcome[_T]]) -> _T:
    outcome = future.result()
    if (error := outcome.error) is None:
        return cast("_T", outcome.value)
    context = error.__context__
    try:
        raise error  # ruff:ignore[raise-within-try]  # the handler restores context changed across the async boundary
    except BaseException:
        error.__context__ = context
        raise


def _capture_call(func: Callable[[], _T]) -> _BackendOutcome[_T]:
    try:
        return _BackendOutcome(value=func())
    except BaseException as error:  # ruff:ignore[blind-except]  # backend control-flow exceptions are operation results
        return _BackendOutcome(error=error)


def _raise_cancelled_error(cancellation: asyncio.CancelledError, error: BaseException) -> NoReturn:
    # A reconciliation step failed while unwinding a cancellation, so keep both exception chains. Splice the error's
    # existing context onto the cancellation, then make the cancellation the error's context, so both the failure and
    # the cancellation that triggered it survive. Shared by the async wrappers so cancellations report the same way.
    if (context := error.__context__) is not None and context is not cancellation:
        if (cancellation_context := cancellation.__context__) is not None:
            _append_exception_context(context, cancellation_context)
        cancellation.__context__ = context
    error.__context__ = cancellation
    _raise_chained_errors(error)


async def _capture_awaitable(awaitable: Awaitable[_T]) -> _BackendOutcome[_T]:
    try:
        return _BackendOutcome(value=await awaitable)
    except BaseException as error:  # ruff:ignore[blind-except]  # backend cancellation must remain distinct from caller cancellation
        return _BackendOutcome(error=error)


__all__ = [
    "_AsyncTransitionGate",
    "_AsyncTransitionUnavailableError",
    "_BackendOutcome",
    "_capture_awaitable",
    "_capture_call",
    "_drain_future",
    "_future_result",
    "_raise_cancelled_error",
    "_wait_until_done",
]
