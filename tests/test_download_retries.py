import hashlib
import http.server
import io
import sys
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import TypeAlias

import pytest
import requests

from gdown.__main__ import main
from gdown.cached_download import cached_download
from gdown.download import CHUNK_SIZE
from gdown.download import download
from gdown.download_folder import download_folder
from gdown.exceptions import DownloadError

RetryServer: TypeAlias = tuple[
    str, list[tuple[int, dict[str, str], bytes]], list[str | None]
]


@pytest.fixture(autouse=True)
def retry_delays(*, monkeypatch: pytest.MonkeyPatch) -> list[float]:
    delays: list[float] = []
    monkeypatch.setattr(sys.modules["gdown.download"].time, "sleep", delays.append)
    monkeypatch.setattr(
        sys.modules["gdown.download"].random, "uniform", lambda _low, high: high
    )
    return delays


@pytest.fixture()
def retry_server() -> Iterator[RetryServer]:
    replies: list[tuple[int, dict[str, str], bytes]] = []
    ranges: list[str | None] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            ranges.append(self.headers.get("Range"))
            status, headers, body = replies.pop(0)
            if status == 0:
                return
            self.send_response(status)
            if "Content-Type" not in headers:
                self.send_header("Content-Type", "application/octet-stream")
            for key, value in headers.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

    with http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(
            target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        )
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}/file", replies, ranges
        finally:
            server.shutdown()
            thread.join()


@pytest.mark.parametrize("connection_failure_first", [True, False])
def test_retry_resumes_its_own_partial_and_hashes_each_byte_once(
    *,
    retry_server: RetryServer,
    retry_delays: list[float],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    connection_failure_first: bool,
) -> None:
    url, replies, ranges = retry_server
    prefix = b"a" * CHUNK_SIZE
    body = prefix + b"end"
    replies.extend(
        [
            (200, {"Content-Length": str(len(body))}, prefix),
            (
                206,
                {
                    "Content-Length": "3",
                    "Content-Range": f"bytes {CHUNK_SIZE}-{len(body) - 1}/{len(body)}",
                },
                b"end",
            ),
        ]
    )
    replies.insert(0 if connection_failure_first else 1, (0, {}, b""))
    output = tmp_path / "output"
    output.write_bytes(b"old completed file")
    old_part = tmp_path / "output.old.part"
    old_part.write_bytes(b"old partial file")
    progress = []
    hasher = hashlib.sha256()
    download(
        url=url,
        output=str(output),
        retries=2,
        hasher=hasher,
        progress=lambda done, total: progress.append((done, total)),
        use_cookies=False,
    )
    assert output.read_bytes() == body
    assert old_part.read_bytes() == b"old partial file"
    assert list(tmp_path.glob("*.part")) == [old_part]
    assert hasher.digest() == hashlib.sha256(body).digest()
    assert progress == [(CHUNK_SIZE, len(body)), (len(body), len(body))]
    assert ranges == [
        None,
        None if connection_failure_first else f"bytes={CHUNK_SIZE}-",
        f"bytes={CHUNK_SIZE}-",
    ]
    assert retry_delays == [1, 2]
    assert "Retrying (2/2)" in capsys.readouterr().err


def test_retry_budget_does_not_reset_after_progress(
    *, retry_server: RetryServer, tmp_path: Path
) -> None:
    url, replies, ranges = retry_server
    prefix = b"a" * CHUNK_SIZE
    total = CHUNK_SIZE * 3
    replies.extend(
        [
            (200, {"Content-Length": str(CHUNK_SIZE * 3)}, prefix),
            (
                206,
                {
                    "Content-Length": str(CHUNK_SIZE * 2),
                    "Content-Range": f"bytes {CHUNK_SIZE}-{total - 1}/{total}",
                },
                prefix,
            ),
        ]
    )
    output = tmp_path / "output"
    with pytest.raises(DownloadError, match="incomplete"):
        download(url=url, output=str(output), retries=1, quiet=True, use_cookies=False)
    assert not output.exists()
    assert next(tmp_path.glob("*.part")).read_bytes() == prefix * 2
    assert ranges == [None, f"bytes={CHUNK_SIZE}-"]


@pytest.mark.parametrize(
    "status, content_range, body",
    [
        (200, None, b"def"),
        (416, None, b"def"),
        (206, "bytes 0-2/3", b"def"),
        (206, "bytes 4-6/7", b"def"),
        (206, "bytes 3-4/6", b"deX"),
        (206, "bytes 3-4/*", b"de"),
        (206, "not a range", b"def"),
    ],
)
@pytest.mark.parametrize("content_length", ["3", None])
def test_retry_refuses_invalid_range_without_appending(
    *,
    retry_server: RetryServer,
    tmp_path: Path,
    status: int,
    content_range: str | None,
    body: bytes,
    content_length: str | None,
) -> None:
    url, replies, ranges = retry_server
    headers = {}
    if content_length is not None:
        headers["Content-Length"] = content_length
    if content_range is not None:
        headers["Content-Range"] = content_range
    replies.extend([(200, {"Content-Length": "6"}, b"abcdef"), (status, headers, body)])
    part = tmp_path / "output.saved.part"
    part.write_bytes(b"abc")
    with pytest.raises(DownloadError, match="byte range"):
        download(
            url=url,
            output=str(tmp_path / "output"),
            resume=True,
            retries=2,
            quiet=True,
            use_cookies=False,
        )
    assert part.read_bytes() == b"abc"
    assert ranges == [None, "bytes=3-"]


def test_resume_accepts_complete_range_with_unknown_total(
    *, retry_server: RetryServer, tmp_path: Path
) -> None:
    url, replies, ranges = retry_server
    replies.extend(
        [
            (200, {"Content-Length": "6"}, b"abcdef"),
            (206, {"Content-Range": "bytes 3-5/*"}, b"def"),
        ]
    )
    output = tmp_path / "output"
    part = tmp_path / "output.saved.part"
    part.write_bytes(b"abc")
    download(url=url, output=str(output), resume=True, quiet=True, use_cookies=False)
    assert output.read_bytes() == b"abcdef"
    assert not part.exists()
    assert ranges == [None, "bytes=3-"]


@pytest.mark.parametrize(
    "error",
    [
        requests.ConnectionError("cancel"),
        requests.Timeout("cancel"),
        requests.exceptions.ChunkedEncodingError("cancel"),
        OSError("disk full"),
    ],
)
def test_retry_does_not_intercept_callback_exceptions(
    *, retry_server: RetryServer, tmp_path: Path, error: Exception
) -> None:
    url, replies, ranges = retry_server
    replies.append((200, {"Content-Length": "4"}, b"data"))

    def stop(_done: int, _total: int | None) -> None:
        raise error

    with pytest.raises(type(error)) as caught:
        download(
            url=url,
            output=str(tmp_path / "output"),
            retries=2,
            quiet=True,
            progress=stop,
            use_cookies=False,
        )
    assert caught.value is error
    assert ranges == [None]
    assert next(tmp_path.glob("*.part")).read_bytes() == b"data"


@pytest.mark.parametrize("status", [403, 429, 503])
def test_retry_does_not_retry_http_errors(
    *, retry_server: RetryServer, tmp_path: Path, status: int
) -> None:
    url, replies, ranges = retry_server
    replies.append((status, {"Content-Length": "0"}, b""))
    with pytest.raises(requests.HTTPError):
        download(
            url=url,
            output=str(tmp_path / "output"),
            retries=2,
            quiet=True,
            use_cookies=False,
        )
    assert ranges == [None]
    assert not list(tmp_path.iterdir())


def test_retry_backoff_is_capped_and_connection_budget_exhausts(
    *, retry_server: RetryServer, retry_delays: list[float], tmp_path: Path
) -> None:
    url, replies, ranges = retry_server
    replies.extend([(0, {}, b"")] * 8)
    with pytest.raises(DownloadError, match="after 7 retries"):
        download(
            url=url,
            output=str(tmp_path / "output"),
            retries=7,
            quiet=True,
            use_cookies=False,
        )
    assert ranges == [None] * 8
    assert retry_delays == [1, 2, 4, 8, 16, 30, 30]


@pytest.mark.parametrize("retries", [-1, 1.5, True])
def test_retry_rejects_invalid_budget(*, retries: int) -> None:
    for downloader in [download, download_folder]:
        with pytest.raises(ValueError, match="nonnegative integer"):
            downloader(id="file", retries=retries)


def test_retry_rejects_streams() -> None:
    with pytest.raises(ValueError, match="filesystem destination"):
        download(id="file", output=io.BytesIO(), retries=1)


def test_cached_download_retries_with_correct_hash(
    *, retry_server: RetryServer, tmp_path: Path
) -> None:
    url, replies, _ranges = retry_server
    prefix = b"a" * CHUNK_SIZE
    body = prefix + b"end"
    replies.extend(
        [
            (200, {"Content-Length": str(len(body))}, prefix),
            (
                206,
                {
                    "Content-Length": "3",
                    "Content-Range": f"bytes {CHUNK_SIZE}-{len(body) - 1}/{len(body)}",
                },
                b"end",
            ),
        ]
    )
    output = tmp_path / "cached"
    cached_download(
        url=url,
        path=str(output),
        hash=f"sha256:{hashlib.sha256(body).hexdigest()}",
        retries=1,
        quiet=True,
        use_cookies=False,
    )
    assert output.read_bytes() == body


def test_cli_retries_a_failed_connection(
    *, retry_server: RetryServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url, replies, ranges = retry_server
    replies.extend([(0, {}, b""), (200, {"Content-Length": "4"}, b"data")])
    output = tmp_path / "output"
    monkeypatch.setattr(
        sys, "argv", ["gdown", "--no-cookies", "--retries", "1", url, "-O", str(output)]
    )
    main()
    assert output.read_bytes() == b"data"
    assert ranges == [None, None]


@pytest.fixture()
def retry_drive(
    *, retry_server: RetryServer, monkeypatch: pytest.MonkeyPatch
) -> RetryServer:
    server_url, _replies, _ranges = retry_server
    get = requests.Session.get

    def get_response(
        session: requests.Session, _url: str, **kwargs: object
    ) -> requests.Response:
        return get(session, server_url, **kwargs)

    monkeypatch.setattr(requests.Session, "get", get_response)
    return retry_server


@pytest.mark.parametrize("cli", [False, True])
def test_folder_retries_each_file_and_reports_exhaustion(
    *,
    retry_drive: RetryServer,
    tmp_path: Path,
    retry_delays: list[float],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    cli: bool,
) -> None:
    _url, replies, ranges = retry_drive
    listing = "<title>folder</title>" + "".join(
        f'<a href="https://drive.google.com/file/d/{name * 25}/view">{name}.txt</a>'
        for name in ["first", "second"]
    )
    replies.extend(
        [
            (200, {"Content-Type": "text/html"}, listing.encode()),
            (0, {}, b""),
            (0, {}, b""),
            (0, {}, b""),
            (
                200,
                {
                    "Content-Disposition": 'attachment; filename="second.txt"',
                    "Content-Length": "4",
                },
                b"data",
            ),
        ]
    )
    if cli:
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "gdown",
                "--no-cookies",
                "--retries",
                "1",
                "https://drive.google.com/drive/folders/" + "x" * 25,
                "-O",
                str(tmp_path),
            ],
        )
        with pytest.raises(SystemExit) as error:
            main()
        assert error.value.code == 1
    else:
        with pytest.raises(DownloadError, match="first.txt"):
            download_folder(
                id="folder-id", output=str(tmp_path), retries=1, use_cookies=False
            )
    assert not (tmp_path / "first.txt").exists()
    assert (tmp_path / "second.txt").read_bytes() == b"data"
    assert ranges == [None] * 5
    assert retry_delays == [1, 1]
    assert "Failed to download" in capsys.readouterr().err


@pytest.mark.parametrize("mode", ["discovery", "file_listing", "folder_listing"])
def test_discovery_and_listings_do_not_retry(
    *, retry_drive: RetryServer, retry_delays: list[float], mode: str
) -> None:
    _url, replies, ranges = retry_drive
    replies.append((0, {}, b""))
    with pytest.raises(requests.ConnectionError):
        if mode == "file_listing":
            download(id="file", retries=2, skip_download=True, use_cookies=False)
        else:
            download_folder(
                id="folder",
                retries=2,
                skip_download=mode == "folder_listing",
                use_cookies=False,
            )
    assert ranges == [None]
    assert retry_delays == []


@pytest.mark.parametrize(
    "error",
    [
        requests.exceptions.SSLError("certificate"),
        requests.exceptions.ProxyError("proxy"),
    ],
)
def test_permanent_connection_errors_are_not_retried(
    *,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    retry_delays: list[float],
    error: Exception,
) -> None:
    def fail(_session: requests.Session, _url: str, **_kwargs: object) -> None:
        raise error

    monkeypatch.setattr(requests.Session, "get", fail)
    with pytest.raises(type(error)) as caught:
        download(
            url="https://example.com/file",
            output=str(tmp_path / "output"),
            retries=2,
            use_cookies=False,
        )
    assert caught.value is error
    assert retry_delays == []


def test_retry_recovers_from_a_timeout(
    *,
    retry_server: RetryServer,
    tmp_path: Path,
    retry_delays: list[float],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url, replies, ranges = retry_server
    replies.append((200, {"Content-Length": "4"}, b"data"))
    get = requests.Session.get
    errors = [requests.Timeout("no response")]

    def get_response(
        session: requests.Session, url: str, **kwargs: object
    ) -> requests.Response:
        if errors:
            raise errors.pop()
        return get(session, url, **kwargs)

    monkeypatch.setattr(requests.Session, "get", get_response)
    output = tmp_path / "output"
    download(url=url, output=str(output), retries=1, use_cookies=False, quiet=True)
    assert output.read_bytes() == b"data"
    assert retry_delays == [1]
    assert ranges == [None]
