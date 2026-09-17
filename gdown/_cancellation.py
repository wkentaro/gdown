import io
import socket
import ssl
import threading
import time
from typing import TYPE_CHECKING

import requests
from requests.adapters import HTTPAdapter
from urllib3 import PoolManager
from urllib3.util import wait_for_read
from urllib3.util import wait_for_write

from .exceptions import DownloadCancelled

if TYPE_CHECKING:
    from typing_extensions import Buffer


def _check_cancelled(*, cancel: threading.Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise DownloadCancelled("Download cancelled")


def _wait_or_cancel(*, seconds: float, cancel: threading.Event | None) -> None:
    if cancel is None:
        time.sleep(seconds)
    else:
        cancel.wait(seconds)
        _check_cancelled(cancel=cancel)


class _CancellableReader(io.RawIOBase):
    def __init__(
        self, *, raw: io.RawIOBase, sock: socket.socket, cancel: threading.Event
    ) -> None:
        self._raw = raw
        self._sock = sock
        self._cancel = cancel

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: "Buffer", /) -> int:
        timeout = self._sock.gettimeout()
        deadline = None if timeout is None else time.monotonic() + timeout
        # A socket timeout poisons buffered reads. Poll readiness instead, keeping
        # the original deadline and any partial TLS record in the same read.
        self._sock.settimeout(0)
        try:
            while True:
                _check_cancelled(cancel=self._cancel)
                writing = False
                try:
                    count = self._raw.readinto(buffer)
                    if count is not None:
                        return count
                except ssl.SSLWantReadError:
                    pass
                except ssl.SSLWantWriteError:
                    writing = True
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    raise TimeoutError("timed out")
                # A bare select rejects descriptors past its fixed set size.
                wait = wait_for_write if writing else wait_for_read
                wait(self._sock, 0.05 if remaining is None else min(0.05, remaining))
        finally:
            self._sock.settimeout(timeout)

    def close(self) -> None:
        try:
            self._raw.close()
        finally:
            super().close()


class _CancellableAdapter(HTTPAdapter):
    def __init__(self, *, cancel: threading.Event) -> None:
        super().__init__()
        self._cancel = cancel
        self._configure_pools(manager=self.poolmanager)

    def _configure_pools(self, *, manager: PoolManager) -> None:
        # Copy the mapping so other sessions keep their ordinary connections.
        manager.pool_classes_by_scheme = manager.pool_classes_by_scheme.copy()
        cancel = self._cancel
        for scheme, pool in manager.pool_classes_by_scheme.items():

            class Response(pool.ConnectionCls.response_class):
                fp: io.BufferedReader

                def __init__(
                    self,
                    sock: socket.socket,
                    debuglevel: int = 0,
                    method: str | None = None,
                    url: str | None = None,
                ) -> None:
                    super().__init__(
                        sock, debuglevel=debuglevel, method=method, url=url
                    )
                    self.fp = io.BufferedReader(
                        _CancellableReader(
                            raw=self.fp.detach(), sock=sock, cancel=cancel
                        )
                    )

            class Connection(pool.ConnectionCls):
                response_class = Response

            class Pool(pool):
                ConnectionCls = Connection

            # The upstream mapping is inferred as exact classes, not subclasses.
            manager.pool_classes_by_scheme[scheme] = Pool  # ty: ignore[invalid-assignment]

    def proxy_manager_for(self, proxy: str, **proxy_kwargs: object) -> PoolManager:  # noqa: GR005 -- preserve the upstream calling convention
        existed = proxy in self.proxy_manager
        manager = super().proxy_manager_for(proxy, **proxy_kwargs)
        if not existed:
            # Derive from each manager's original classes to retain SOCKS support.
            self._configure_pools(manager=manager)
        return manager


def _configure_cancellation(
    *, session: requests.Session, cancel: threading.Event | None
) -> None:
    if cancel is not None:
        adapter = _CancellableAdapter(cancel=cancel)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
