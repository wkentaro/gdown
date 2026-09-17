import contextlib
import gzip
import hashlib
import io
import os
import select
import socket
import socketserver
import ssl
import sys
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlsplit

import filelock
import pytest
import requests

import gdown
from gdown.download import CHUNK_SIZE


class DownloadServer(NamedTuple):
    url: str
    verify: bool | str
    entered: threading.Event
    release: threading.Event
    paths: list[str]


both_schemes = pytest.mark.parametrize(
    "download_server", ["http", "https"], indirect=True
)


@pytest.fixture
def download_server(*, request: pytest.FixtureRequest) -> Iterator[DownloadServer]:
    # Only the socket read path differs under TLS, so only its tests opt in.
    scheme = getattr(request, "param", "http")
    entered = threading.Event()
    release = threading.Event()
    paths: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            paths.append(path)
            if path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "/body")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if path == "/compressed":
                body = gzip.compress(b"x" * (2 * CHUNK_SIZE))
                self.send_response(200)
                self.send_header("Content-Encoding", "gzip")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if path == "/failure":
                entered.set()
                return
            if path == "/reconnect":
                resumed = self.headers.get("Range") is not None
                self.send_response(206 if resumed else 200)
                self.send_header(
                    "Content-Length", str(CHUNK_SIZE if resumed else 2 * CHUNK_SIZE)
                )
                if resumed:
                    self.send_header(
                        "Content-Range",
                        f"bytes {CHUNK_SIZE}-{2 * CHUNK_SIZE - 1}/{2 * CHUNK_SIZE}",
                    )
                self.end_headers()
                if resumed:
                    entered.set()
                    release.wait()
                with contextlib.suppress(OSError):
                    self.wfile.write(b"x" * CHUNK_SIZE)
                return
            if path == "/headers":
                entered.set()
                release.wait()
            self.send_response(200)
            self.send_header("Content-Length", str(2 * CHUNK_SIZE))
            self.end_headers()
            with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                self.wfile.write(b"x" * CHUNK_SIZE)
                self.wfile.flush()
                entered.set()
                if path == "/body":
                    release.wait()
                elif path == "/slow":
                    release.wait(1.2)
                self.wfile.write(b"x" * CHUNK_SIZE)

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        verify: bool | str = True
        if scheme == "https":
            certificates = Path(__file__).parent / "data" / "cancellation"
            verify = str(certificates / "cert.pem")
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(verify, str(certificates / "key.pem"))
            server.socket = context.wrap_socket(server.socket, server_side=True)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            yield DownloadServer(
                f"{scheme}://127.0.0.1:{server.server_port}",
                verify,
                entered,
                release,
                paths,
            )
        finally:
            release.set()
            server.shutdown()
            thread.join()


@pytest.fixture
def executor(*, download_server: DownloadServer) -> Iterator[ThreadPoolExecutor]:
    with ThreadPoolExecutor() as pool:
        yield pool
        # Unblock the server so leaving the pool cannot wait on a stalled worker.
        download_server.release.set()


@both_schemes
@pytest.mark.parametrize("phase", ["headers", "body", "redirect", "reconnect"])
@pytest.mark.parametrize("timeout", [30, None])
def test_cancel_interrupts_network_before_timeout(
    *,
    tmp_path: Path,
    download_server: DownloadServer,
    executor: ThreadPoolExecutor,
    phase: str,
    timeout: int | None,
) -> None:
    output = tmp_path / "model"
    output.write_bytes(b"existing model")
    cancel = threading.Event()
    received = threading.Event()
    future = executor.submit(
        lambda: gdown.download(
            url=f"{download_server.url}/{phase}",
            output=str(output),
            verify=download_server.verify,
            use_cookies=False,
            quiet=True,
            retries=2,
            timeout=timeout,
            cancel=cancel,
            progress=lambda *_: received.set(),
        )
    )
    ready = download_server.entered if phase in {"headers", "reconnect"} else received
    assert ready.wait(5)
    cancel.set()
    assert isinstance(future.exception(timeout=1), gdown.DownloadCancelled)
    assert output.read_bytes() == b"existing model"
    expected_paths = [f"/{phase}"]
    if phase == "redirect":
        expected_paths = ["/redirect", "/body"]
    elif phase == "reconnect":
        expected_paths *= 2
    assert download_server.paths == expected_paths
    if phase != "headers":
        assert next(tmp_path.glob("model*.part")).read_bytes() == b"x" * CHUNK_SIZE


@both_schemes
def test_uncancelled_slow_download_succeeds(
    *, tmp_path: Path, download_server: DownloadServer
) -> None:
    output = tmp_path / "model"
    result = gdown.cached_download(
        url=f"{download_server.url}/slow",
        path=str(output),
        hash=f"sha256:{hashlib.sha256(b'x' * (2 * CHUNK_SIZE)).hexdigest()}",
        verify=download_server.verify,
        use_cookies=False,
        quiet=True,
        timeout=30,
        cancel=threading.Event(),
    )
    assert result == str(output)
    assert output.read_bytes() == b"x" * (2 * CHUNK_SIZE)
    assert download_server.paths == ["/slow"]


def test_cancel_cleans_cache_staging(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    download_server: DownloadServer,
    executor: ThreadPoolExecutor,
) -> None:
    cache = tmp_path / "cache"
    monkeypatch.setattr(sys.modules["gdown.cached_download"], "cache_root", str(cache))
    output = tmp_path / "model"
    output.write_bytes(b"existing model")
    cancel = threading.Event()
    received = threading.Event()
    future = executor.submit(
        lambda: gdown.cached_download(
            url=f"{download_server.url}/body",
            path=str(output),
            hash="sha256:wrong",
            verify=download_server.verify,
            use_cookies=False,
            quiet=True,
            timeout=30,
            cancel=cancel,
            progress=lambda *_: received.set(),
        )
    )
    assert received.wait(5)
    cancel.set()
    assert isinstance(future.exception(timeout=1), gdown.DownloadCancelled)
    assert output.read_bytes() == b"existing model"
    assert list(cache.iterdir()) == []


@pytest.mark.parametrize("cached", [False, True])
def test_preset_cancel_precedes_cache_hit(*, tmp_path: Path, cached: bool) -> None:
    output = tmp_path / "model"
    output.write_bytes(b"existing model")
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(gdown.DownloadCancelled):
        if cached:
            gdown.cached_download(path=str(output), cancel=cancel)
        else:
            gdown.download(
                url="invalid URL", output=str(output), resume=True, cancel=cancel
            )
    assert output.read_bytes() == b"existing model"
    assert cancel.is_set()


@pytest.mark.parametrize("phase", ["failure", "complete"])
def test_cancel_interrupts_retry_and_speed_waits(
    *,
    download_server: DownloadServer,
    executor: ThreadPoolExecutor,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    phase: str,
) -> None:
    # Make the randomized backoff long enough to distinguish interruption.
    monkeypatch.setattr(sys.modules["gdown.download"].random, "uniform", lambda *_: 30)
    cancel = threading.Event()
    received = threading.Event()
    future = executor.submit(
        lambda: gdown.download(
            url=f"{download_server.url}/{phase}",
            output=str(tmp_path / "model"),
            verify=download_server.verify,
            use_cookies=False,
            quiet=True,
            retries=2,
            speed=CHUNK_SIZE / 30,
            cancel=cancel,
            progress=lambda *_: received.set(),
        )
    )
    ready = download_server.entered if phase == "failure" else received
    assert ready.wait(5)
    assert wait([future], timeout=0.1).not_done
    cancel.set()
    assert isinstance(future.exception(timeout=1), gdown.DownloadCancelled)
    assert download_server.paths == [f"/{phase}"]


def test_cancel_keeps_caller_stream_open(*, download_server: DownloadServer) -> None:
    output = io.BytesIO()
    cancel = threading.Event()
    with pytest.raises(gdown.DownloadCancelled):
        gdown.download(
            url=f"{download_server.url}/complete",
            output=output,
            verify=download_server.verify,
            use_cookies=False,
            quiet=True,
            cancel=cancel,
            progress=lambda *_: cancel.set(),
        )
    assert not output.closed
    assert output.getvalue().startswith(b"x" * CHUNK_SIZE)


def test_cancel_interrupts_high_numbered_descriptor(
    *, download_server: DownloadServer, executor: ThreadPoolExecutor
) -> None:
    # Descriptor limits are POSIX-only.
    resource = pytest.importorskip("resource")
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    wanted = 2048
    if hard != resource.RLIM_INFINITY and hard < wanted:
        pytest.skip("descriptor limit is too low")
    resource.setrlimit(resource.RLIMIT_NOFILE, (max(soft, wanted), hard))
    # Push the download socket past the descriptor range a bare select accepts.
    held = [os.open(os.devnull, os.O_RDONLY) for _ in range(1024)]
    try:
        cancel = threading.Event()
        received = threading.Event()
        future = executor.submit(
            lambda: gdown.download(
                url=f"{download_server.url}/body",
                output=io.BytesIO(),
                verify=download_server.verify,
                use_cookies=False,
                quiet=True,
                timeout=30,
                cancel=cancel,
                progress=lambda *_: received.set(),
            )
        )
        assert received.wait(5)
        cancel.set()
        assert isinstance(future.exception(timeout=1), gdown.DownloadCancelled)
    finally:
        for descriptor in held:
            os.close(descriptor)
        resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))


def test_cancellation_is_isolated_between_downloads(
    *,
    download_server: DownloadServer,
    executor: ThreadPoolExecutor,
) -> None:
    cancel = threading.Event()
    received_a = threading.Event()
    received_b = threading.Event()
    output_a = io.BytesIO()
    output_b = io.BytesIO()
    future_a = executor.submit(
        lambda: gdown.download(
            url=f"{download_server.url}/body",
            output=output_a,
            verify=download_server.verify,
            use_cookies=False,
            quiet=True,
            cancel=cancel,
            progress=lambda *_: received_a.set(),
        )
    )
    future_b = executor.submit(
        lambda: gdown.download(
            url=f"{download_server.url}/body",
            output=output_b,
            verify=download_server.verify,
            use_cookies=False,
            quiet=True,
            cancel=threading.Event(),
            progress=lambda *_: received_b.set(),
        )
    )
    assert received_a.wait(5)
    assert received_b.wait(5)
    cancel.set()
    assert isinstance(future_a.exception(timeout=1), gdown.DownloadCancelled)
    assert not future_b.done()
    download_server.release.set()
    future_b.result(timeout=5)
    assert output_b.getvalue() == b"x" * (2 * CHUNK_SIZE)


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("when", ["last_chunk", "publication"])
def test_cancellation_obeys_publication_boundary(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    download_server: DownloadServer,
    cached: bool,
    when: str,
) -> None:
    output = tmp_path / "model"
    cancel = threading.Event()
    move = sys.modules["gdown.download"].shutil.move

    def publish(src: str, dst: str) -> str:  # noqa: GR005 -- preserve the upstream calling convention
        if dst == str(output) and when == "publication":
            cancel.set()
        return move(src, dst)

    monkeypatch.setattr(sys.modules["gdown.download"].shutil, "move", publish)

    def report(received: int, total: int | None) -> None:  # noqa: GR005 -- callback arguments are positional
        if received == total and when == "last_chunk":
            cancel.set()

    with (
        pytest.raises(gdown.DownloadCancelled)
        if when == "last_chunk"
        else contextlib.nullcontext()
    ):
        if cached:
            gdown.cached_download(
                url=f"{download_server.url}/complete",
                path=str(output),
                verify=download_server.verify,
                use_cookies=False,
                quiet=True,
                cancel=cancel,
                progress=report,
            )
        else:
            gdown.download(
                url=f"{download_server.url}/complete",
                output=str(output),
                verify=download_server.verify,
                use_cookies=False,
                quiet=True,
                cancel=cancel,
                progress=report,
            )
    if when == "last_chunk":
        assert not output.exists()
    else:
        assert output.read_bytes() == b"x" * (2 * CHUNK_SIZE)


@pytest.fixture(params=["http", "socks5"])
def proxy_server(
    *, request: pytest.FixtureRequest, download_server: DownloadServer
) -> Iterator[str]:
    target = urlsplit(download_server.url)
    assert target.port is not None
    address = ("127.0.0.1", target.port)

    class Handler(socketserver.StreamRequestHandler):
        def handle(self) -> None:
            self.connection.settimeout(5)
            with socket.create_connection(address, timeout=5) as upstream:
                if request.param == "socks5":
                    assert self.rfile.read(3) == b"\x05\x01\x00"
                    self.wfile.write(b"\x05\x00")
                    assert self.rfile.read(4) == b"\x05\x01\x00\x01"
                    self.rfile.read(6)
                    self.wfile.write(b"\x05\x00\x00\x01\x7f\x00\x00\x01\x00\x00")
                with contextlib.suppress(OSError):
                    while True:
                        readable, _, _ = select.select(
                            [self.connection, upstream], [], [], 5
                        )
                        if not readable:
                            return
                        for source in readable:
                            data = source.recv(65536)
                            if not data:
                                return
                            destination = (
                                upstream
                                if source is self.connection
                                else self.connection
                            )
                            destination.sendall(data)

    with socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler) as proxy:
        thread = threading.Thread(target=proxy.serve_forever)
        thread.start()
        try:
            yield f"{request.param}://127.0.0.1:{proxy.server_address[1]}"
        finally:
            download_server.release.set()
            proxy.shutdown()
            thread.join()


@pytest.mark.parametrize("phase", ["headers", "body"])
def test_cancel_interrupts_proxied_download(
    *,
    download_server: DownloadServer,
    proxy_server: str,
    executor: ThreadPoolExecutor,
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
) -> None:
    for name in ("http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(name.upper(), raising=False)
    cancel = threading.Event()
    received = threading.Event()
    future = executor.submit(
        lambda: gdown.download(
            url=f"{download_server.url}/{phase}",
            output=io.BytesIO(),
            verify=download_server.verify,
            use_cookies=False,
            quiet=True,
            proxy=proxy_server,
            timeout=30,
            cancel=cancel,
            progress=lambda *_: received.set(),
        )
    )
    ready = download_server.entered if phase == "headers" else received
    assert ready.wait(5)
    cancel.set()
    assert isinstance(future.exception(timeout=1), gdown.DownloadCancelled)


@both_schemes
@pytest.mark.parametrize("phase", ["headers", "body"])
@pytest.mark.parametrize("timeout", [0.15, (5, 0.15)])
def test_unset_cancellation_preserves_read_timeout(
    *,
    download_server: DownloadServer,
    executor: ThreadPoolExecutor,
    phase: str,
    timeout: float | tuple[float, float],
) -> None:
    future = executor.submit(
        lambda: gdown.download(
            url=f"{download_server.url}/{phase}",
            output=io.BytesIO(),
            verify=download_server.verify,
            use_cookies=False,
            quiet=True,
            timeout=timeout,
            cancel=threading.Event(),
        )
    )
    error = future.exception(timeout=2)
    assert isinstance(error, requests.exceptions.RequestException)
    assert "timed out" in str(error).lower()


def test_cancel_during_cache_hit_hash_check(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "model"
    output.write_bytes(b"existing model")
    cancel = threading.Event()
    module = sys.modules["gdown.cached_download"]
    compute_hash = module._compute_filehash

    def hash_and_cancel(*, path: str, algorithm: str) -> str:
        result = compute_hash(path=path, algorithm=algorithm)
        cancel.set()
        return result

    monkeypatch.setattr(module, "_compute_filehash", hash_and_cancel)
    with pytest.raises(gdown.DownloadCancelled):
        gdown.cached_download(
            path=str(output),
            hash=f"sha256:{hashlib.sha256(b'existing model').hexdigest()}",
            cancel=cancel,
        )
    assert output.read_bytes() == b"existing model"


def test_cancel_after_cache_lock_acquisition_preserves_destination(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, download_server: DownloadServer
) -> None:
    output = tmp_path / "model"
    output.write_bytes(b"existing model")
    cache = tmp_path / "cache"
    cancel = threading.Event()
    module = sys.modules["gdown.cached_download"]

    class CancellingLock(filelock.FileLock):
        def __enter__(self) -> "CancellingLock":
            super().__enter__()
            cancel.set()
            return self

    monkeypatch.setattr(module, "cache_root", str(cache))
    monkeypatch.setattr(filelock, "FileLock", CancellingLock)
    with pytest.raises(gdown.DownloadCancelled):
        gdown.cached_download(
            url=f"{download_server.url}/complete",
            path=str(output),
            hash=f"sha256:{hashlib.sha256(b'x' * (2 * CHUNK_SIZE)).hexdigest()}",
            use_cookies=False,
            quiet=True,
            cancel=cancel,
        )
    assert output.read_bytes() == b"existing model"
    assert not any(path.is_dir() for path in cache.iterdir())


def test_cancel_stops_buffered_compressed_chunks(
    *, download_server: DownloadServer
) -> None:
    cancel = threading.Event()
    reported: list[int] = []

    def report(received: int, total: int | None) -> None:  # noqa: ARG001, GR005 -- callback arguments are positional
        reported.append(received)
        cancel.set()

    with pytest.raises(gdown.DownloadCancelled):
        gdown.download(
            url=f"{download_server.url}/compressed",
            output=io.BytesIO(),
            use_cookies=False,
            quiet=True,
            cancel=cancel,
            progress=report,
        )
    assert len(reported) == 1


def test_cancel_after_body_flush_precedes_exhausted_retries(
    *, download_server: DownloadServer
) -> None:
    cancel = threading.Event()

    class CancellingStream(io.BytesIO):
        def flush(self) -> None:
            super().flush()
            cancel.set()

    with pytest.raises(gdown.DownloadCancelled):
        gdown.download(
            url=f"{download_server.url}/reconnect",
            output=CancellingStream(),
            use_cookies=False,
            quiet=True,
            retries=0,
            cancel=cancel,
        )
    assert download_server.paths == ["/reconnect"]
