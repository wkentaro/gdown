import http.cookiejar
import http.server
import io
import os
import sqlite3
import sys
import threading
import unittest.mock
from pathlib import Path
from typing import BinaryIO
from typing import Final
from typing import Literal
from typing import NamedTuple

import pytest
import requests

from gdown._vendor._ytdlp_cookies import extract_cookies_from_browser
from gdown.download import CHUNK_SIZE
from gdown.download import GoogleDriveFileToDownload
from gdown.download import _get_session
from gdown.download import _import_cookies_from_browser
from gdown.download import _load_cookies
from gdown.download import _save_cookies
from gdown.download import download
from gdown.exceptions import DownloadError

from .conftest import build_google_cookie
from .conftest import build_response

DOWNLOAD_URL: Final[str] = (
    "https://raw.githubusercontent.com/wkentaro/gdown/3.1.0/gdown/__init__.py"
)


class DownloadEnv(NamedTuple):
    file_path: str
    url: str


@pytest.fixture()
def download_env(*, tmp_path: Path) -> DownloadEnv:
    return DownloadEnv(
        file_path=str(tmp_path / "file"),
        url=DOWNLOAD_URL,
    )


@pytest.fixture()
def download_session(
    *,
    monkeypatch: pytest.MonkeyPatch,
) -> unittest.mock.Mock:
    response = build_response(headers={"Content-Length": "4"}, chunks=[b"data"])

    session = unittest.mock.Mock()
    session.get.return_value = response
    monkeypatch.setattr(
        sys.modules["gdown.download"],
        "_get_session",
        lambda **_kwargs: (session, "cookies.txt"),
    )
    return session


@pytest.fixture()
def opened_files(*, monkeypatch: pytest.MonkeyPatch) -> list[BinaryIO]:
    files: list[BinaryIO] = []

    def open_file(path: str, mode: Literal["ab"]) -> BinaryIO:
        file = open(path, mode)
        files.append(file)
        return file

    monkeypatch.setattr(
        sys.modules["gdown.download"],
        "open",
        open_file,
        raising=False,
    )
    return files


@pytest.mark.network
def test_download(*, download_env: DownloadEnv) -> None:
    # Usage before https://github.com/wkentaro/gdown/pull/32
    assert (
        download(url=download_env.url, output=download_env.file_path, quiet=False)
        == download_env.file_path
    )


@pytest.mark.network
def test_download_progress(*, download_env: DownloadEnv) -> None:
    reported: list[tuple[int, int | None]] = []
    download(
        url=download_env.url,
        output=download_env.file_path,
        quiet=True,
        progress=lambda current, total: reported.append((current, total)),
    )

    assert len(reported) >= 1

    currents = [c for c, _ in reported]
    assert currents == sorted(currents)

    final_current, final_total = reported[-1]
    assert final_total is not None
    assert final_current == os.path.getsize(download_env.file_path)


def test_download_closes_resources_when_progress_raises(
    *,
    tmp_path: Path,
    download_session: unittest.mock.Mock,
    opened_files: list[BinaryIO],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pbar = unittest.mock.Mock()
    monkeypatch.setattr(
        sys.modules["gdown.download"].tqdm, "tqdm", lambda **_kwargs: pbar
    )

    with pytest.raises(RuntimeError, match="stop"):
        download(
            url="https://example.com/file",
            output=str(tmp_path / "output"),
            quiet=False,
            use_cookies=False,
            progress=unittest.mock.Mock(side_effect=RuntimeError("stop")),
        )

    pbar.close.assert_called_once_with()
    assert opened_files[0].closed
    download_session.close.assert_called_once_with()
    part_files = list(tmp_path.glob("output*.part"))
    assert len(part_files) == 1
    assert part_files[0].read_bytes() == b"data"


def test_download_closes_resources_when_resume_request_raises(
    *,
    tmp_path: Path,
    download_session: unittest.mock.Mock,
    opened_files: list[BinaryIO],
) -> None:
    download_session.get.side_effect = [
        download_session.get.return_value,
        requests.ConnectionError("range request failed"),
    ]
    part = tmp_path / "output.partial.part"
    part.write_bytes(b"partial")

    with pytest.raises(requests.ConnectionError, match="range request failed"):
        download(
            url="https://example.com/file",
            output=str(tmp_path / "output"),
            quiet=True,
            use_cookies=False,
            resume=True,
        )

    assert opened_files[0].closed
    download_session.close.assert_called_once_with()
    assert part.read_bytes() == b"partial"


def test_download_keeps_caller_output_open_when_progress_raises(
    *,
    download_session: unittest.mock.Mock,
) -> None:
    output = io.BytesIO()

    with pytest.raises(RuntimeError, match="stop"):
        download(
            url="https://example.com/file",
            output=output,
            quiet=True,
            use_cookies=False,
            progress=unittest.mock.Mock(side_effect=RuntimeError("stop")),
        )

    assert not output.closed
    assert output.getvalue() == b"data"
    download_session.close.assert_called_once_with()


def test_download_attempts_all_cleanup_when_closers_raise(
    *,
    tmp_path: Path,
    download_session: unittest.mock.Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    file = unittest.mock.mock_open()
    file().tell.return_value = 0
    file().close.side_effect = OSError("file close failed")
    pbar = unittest.mock.Mock()
    pbar.close.side_effect = OSError("pbar close failed")
    monkeypatch.setattr(sys.modules["gdown.download"], "open", file, raising=False)
    monkeypatch.setattr(
        sys.modules["gdown.download"].tqdm, "tqdm", lambda **_kwargs: pbar
    )

    with pytest.raises(OSError, match="file close failed"):
        download(
            url="https://example.com/file",
            output=str(tmp_path / "output"),
            quiet=False,
            use_cookies=False,
            progress=unittest.mock.Mock(side_effect=RuntimeError("stop")),
        )

    pbar.close.assert_called_once_with()
    file().close.assert_called_once_with()
    download_session.close.assert_called_once_with()


def test_download_propagates_pbar_close_error_and_keeps_part(
    *,
    tmp_path: Path,
    download_session: unittest.mock.Mock,
    opened_files: list[BinaryIO],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "output"
    pbar = unittest.mock.Mock()
    pbar.close.side_effect = OSError("pbar close failed")
    monkeypatch.setattr(
        sys.modules["gdown.download"].tqdm, "tqdm", lambda **_kwargs: pbar
    )

    with pytest.raises(OSError, match="pbar close failed"):
        download(
            url="https://example.com/file",
            output=str(output),
            quiet=False,
            use_cookies=False,
        )

    assert opened_files[0].closed
    download_session.close.assert_called_once_with()
    assert not output.exists()
    part_files = list(tmp_path.glob("output*.part"))
    assert len(part_files) == 1
    assert part_files[0].read_bytes() == b"data"


@pytest.mark.network
def test_download_output_dir_with_trailing_slash(*, tmp_path: Path) -> None:
    output_dir = str(tmp_path / "subdir") + "/"
    result = download(url=DOWNLOAD_URL, output=output_dir, quiet=True)
    assert isinstance(result, str)
    assert Path(result).parent == tmp_path / "subdir"
    assert Path(result).is_file()


@pytest.mark.network
def test_download_output_dir_with_trailing_backslash(*, tmp_path: Path) -> None:
    output_dir = str(tmp_path / "subdir") + "\\"
    result = download(url=DOWNLOAD_URL, output=output_dir, quiet=True)
    assert isinstance(result, str)
    # On Unix, '\' is a valid filename char, so the dir name includes it.
    # On Windows, '\' is the path separator, so it behaves like '/'.
    assert Path(result).is_file()


@pytest.mark.network
def test_download_output_existing_dir(*, tmp_path: Path) -> None:
    output_dir = tmp_path / "existing"
    output_dir.mkdir()
    result = download(url=DOWNLOAD_URL, output=str(output_dir), quiet=True)
    assert isinstance(result, str)
    assert Path(result).parent == output_dir
    assert Path(result).is_file()


@pytest.mark.network
def test_download_resume_skips_existing_file(
    *, download_env: DownloadEnv, capsys: pytest.CaptureFixture[str]
) -> None:
    download(url=download_env.url, output=download_env.file_path, quiet=True)
    mtime_before = os.path.getmtime(download_env.file_path)

    result = download(
        url=download_env.url,
        output=download_env.file_path,
        quiet=False,
        resume=True,
    )
    assert result == download_env.file_path
    assert os.path.getmtime(download_env.file_path) == mtime_before
    assert "Skipping already downloaded file" in capsys.readouterr().err


@pytest.mark.network
def test_download_resume_skips_existing_file_in_dir(*, tmp_path: Path) -> None:
    output_dir = tmp_path / "subdir"
    output_dir.mkdir()
    result = download(url=DOWNLOAD_URL, output=str(output_dir), quiet=True)
    assert isinstance(result, str)
    mtime_before = os.path.getmtime(result)

    resume_result = download(
        url=DOWNLOAD_URL, output=str(output_dir), quiet=True, resume=True
    )
    assert resume_result == result
    assert os.path.getmtime(result) == mtime_before


@pytest.mark.parametrize(
    "share_url",
    [
        "https://drive.google.com/file/d/0B9P1L--7Wd2vU3VUVlFnbTgtS2c/view?usp=sharing",
        "https://drive.google.com/open?id=0B9P1L--7Wd2vU3VUVlFnbTgtS2c",
        "https://drive.google.com/uc?id=0B9P1L--7Wd2vU3VUVlFnbTgtS2c",
    ],
)
def test_download_rewrites_google_drive_share_link(
    *, tmp_path: Path, share_url: str
) -> None:
    expected_url = "https://drive.google.com/uc?id=0B9P1L--7Wd2vU3VUVlFnbTgtS2c"

    mock_response = unittest.mock.Mock()
    mock_response.status_code = 200
    mock_response.headers = {
        "Content-Type": "application/octet-stream",
        "Content-Disposition": 'attachment; filename="test.bin"',
    }
    mock_response.iter_content = lambda **_kwargs: [b"data"]
    mock_response.url = expected_url

    mock_sess = unittest.mock.Mock()
    mock_sess.get.return_value = mock_response
    mock_sess.cookies = []

    with unittest.mock.patch.object(
        sys.modules["gdown.download"],
        "_get_session",
        return_value=(mock_sess, str(tmp_path / "cookies.txt")),
    ):
        download(url=share_url, output=str(tmp_path / "out"), quiet=True)

        actual_url = mock_sess.get.call_args_list[0].args[0]
        assert actual_url == expected_url


def test_download_skip_download_returns_file_object(*, tmp_path: Path) -> None:
    file_id = "0B9P1L--7Wd2vU3VUVlFnbTgtS2c"

    mock_response = unittest.mock.Mock()
    mock_response.status_code = 200
    mock_response.headers = {
        "Content-Type": "application/octet-stream",
        "Content-Disposition": 'attachment; filename="spam.txt"',
    }
    mock_response.url = f"https://drive.google.com/uc?id={file_id}"

    mock_sess = unittest.mock.Mock()
    mock_sess.get.return_value = mock_response
    mock_sess.cookies = []

    with unittest.mock.patch.object(
        sys.modules["gdown.download"],
        "_get_session",
        return_value=(mock_sess, str(tmp_path / "cookies.txt")),
    ):
        result = download(
            url=f"https://drive.google.com/uc?id={file_id}",
            quiet=True,
            skip_download=True,
        )

    assert result == GoogleDriveFileToDownload(
        id=file_id, path="spam.txt", local_path="spam.txt"
    )
    mock_response.iter_content.assert_not_called()


@pytest.mark.network
def test_download_google_slides_without_extension(*, tmp_path: Path) -> None:
    # The file "gdown" in Google Drive is a Google Slides file with no extension
    # in its filename. When downloading directly, download() resolves the correct
    # .pptx extension from the Content-Disposition header.
    output = download(
        url="https://docs.google.com/presentation/d/1DvsG277pWa4WMssXjD9qYYAdF51y7hVidZ6eklfq480/edit?usp=drive_link",
        output=str(tmp_path) + os.sep,
        quiet=True,
    )
    assert isinstance(output, str)
    assert output.endswith(".pptx")


def test_download_keeps_part_then_resumes_when_body_ends_before_announced_size(
    *,
    tmp_path: Path,
    download_session: unittest.mock.Mock,
) -> None:
    output = tmp_path / "output"
    download_session.get.return_value = build_response(
        headers={"Content-Length": "10"}, chunks=[b"data"]
    )

    with pytest.raises(DownloadError, match="received 4 bytes.*announced 10 bytes"):
        download(url="https://example.com/file", output=str(output), quiet=True)

    assert not output.exists()
    (part,) = tmp_path.glob("output*.part")
    assert part.read_bytes() == b"data"

    download_session.get.side_effect = [
        download_session.get.return_value,
        build_response(headers={"Content-Length": "6"}, chunks=[b"123456"]),
    ]
    download(
        url="https://example.com/file", output=str(output), quiet=True, resume=True
    )

    assert output.read_bytes() == b"data123456"
    assert not part.exists()


def test_download_counts_resumed_bytes_toward_announced_size(
    *,
    tmp_path: Path,
    download_session: unittest.mock.Mock,
) -> None:
    output = tmp_path / "output"
    part = tmp_path / "output.partial.part"
    part.write_bytes(b"partial")
    download_session.get.side_effect = [
        build_response(headers={"Content-Length": "11"}, chunks=[b"partial"]),
        build_response(headers={"Content-Length": "4"}, chunks=[b"da"]),
    ]

    with pytest.raises(DownloadError, match="received 9 bytes.*announced 11 bytes"):
        download(
            url="https://example.com/file", output=str(output), quiet=True, resume=True
        )

    assert part.read_bytes() == b"partialda"


def test_download_fails_when_body_ends_early_for_a_caller_stream(
    *,
    download_session: unittest.mock.Mock,
) -> None:
    output = io.BytesIO()
    download_session.get.return_value = build_response(
        headers={"Content-Length": "10"}, chunks=[b"data"]
    )

    with pytest.raises(DownloadError, match="received 4 bytes"):
        download(url="https://example.com/file", output=output, quiet=True)

    assert not output.closed
    assert output.getvalue() == b"data"


def test_download_fails_when_the_transport_reports_a_broken_body(
    *,
    tmp_path: Path,
    download_session: unittest.mock.Mock,
) -> None:
    output = tmp_path / "output"
    download_session.get.return_value.iter_content.side_effect = (
        requests.exceptions.ChunkedEncodingError("connection broken")
    )

    with pytest.raises(DownloadError, match="received 0 bytes"):
        download(url="https://example.com/file", output=str(output), quiet=True)

    assert not output.exists()


@pytest.mark.parametrize(
    ("headers", "total"),
    [
        ({}, None),
        ({"Content-Length": "not-a-number"}, None),
        ({"Content-Length": "-1"}, None),
        # Content-Length counts the compressed wire bytes, not the decoded ones.
        ({"Content-Length": "10", "Content-Encoding": "gzip"}, 10),
        # A transfer encoding makes the client ignore Content-Length.
        ({"Content-Length": "100", "Transfer-Encoding": "chunked"}, 100),
    ],
)
def test_download_accepts_body_when_announced_size_is_not_comparable(
    *,
    tmp_path: Path,
    download_session: unittest.mock.Mock,
    headers: dict[str, str],
    total: int | None,
) -> None:
    output = tmp_path / "output"
    download_session.get.return_value = build_response(
        headers=headers, chunks=[b"data"]
    )
    reported: list[tuple[int, int | None]] = []

    download(
        url="https://example.com/file",
        output=str(output),
        quiet=True,
        progress=lambda current, total: reported.append((current, total)),
    )

    assert output.read_bytes() == b"data"
    assert reported == [(4, total)]


def test_download_keeps_part_when_the_connection_closes_early(
    *, tmp_path: Path
) -> None:
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Length", str(2 * CHUNK_SIZE))
            self.end_headers()
            self.wfile.write(b"x" * (CHUNK_SIZE + 1000))

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.handle_request, daemon=True).start()
    output = tmp_path / "output"

    with pytest.raises(DownloadError, match=f"announced {2 * CHUNK_SIZE} bytes"):
        download(
            url=f"http://127.0.0.1:{server.server_port}/",
            output=str(output),
            quiet=True,
        )

    server.server_close()
    assert not output.exists()
    (part,) = tmp_path.glob("output*.part")
    # How much of the unfinished chunk survives depends on the HTTP client.
    assert len(part.read_bytes()) >= CHUNK_SIZE


def test_import_cookies_from_browser_merges_into_file(
    *, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    # A bare filename has no directory part, which the save path must tolerate.
    cookies_file = "cookies.txt"
    _save_cookies(
        cookies=[build_google_cookie(name="OTHER", value="kept")],
        cookies_file=cookies_file,
    )

    def fake_extractor(
        browser_name: str, *_args: object, **_kwargs: object
    ) -> list[http.cookiejar.Cookie]:
        assert browser_name == "firefox"
        return [
            build_google_cookie(name="SID", value="from-browser"),
            build_google_cookie(name="NID", value="persistent", expires=4102444800),
        ]

    monkeypatch.setattr(
        "gdown._vendor._ytdlp_cookies.extract_cookies_from_browser", fake_extractor
    )

    n_cookies = _import_cookies_from_browser(
        browser="firefox", cookies_file=cookies_file
    )
    assert n_cookies == 2  # noqa: PLR2004
    # A second import must replace, not duplicate, the existing entries.
    _import_cookies_from_browser(browser="firefox", cookies_file=cookies_file)

    assert {(c.name, c.value) for c in _load_cookies(cookies_file=cookies_file)} == {
        ("OTHER", "kept"),
        ("SID", "from-browser"),
        ("NID", "persistent"),
    }
    if os.name != "nt":
        assert oct(os.stat(cookies_file).st_mode & 0o777) == "0o600"


def test_load_cookies_keeps_extension_exported_session_cookies(
    *, tmp_path: Path
) -> None:
    cookies_file = tmp_path / "cookies.txt"
    # Browser extensions write session cookies with an expiry of 0.
    cookies_file.write_text(
        "# Netscape HTTP Cookie File\n"
        ".google.com\tTRUE\t/\tTRUE\t0\tSID\tsession\n"
        ".google.com\tTRUE\t/\tTRUE\t1\tOLD\texpired\n"
    )

    jar = _load_cookies(cookies_file=str(cookies_file))

    assert {c.name for c in jar} == {"SID"}
    assert next(iter(jar)).expires is None


def test_load_cookies_replaces_unreadable_file(*, tmp_path: Path) -> None:
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_bytes(b"\x80not a cookies file")

    with pytest.warns(UserWarning, match="Replacing unreadable cookies file"):
        jar = _load_cookies(cookies_file=str(cookies_file))

    assert len(jar) == 0


def test_download_warns_when_cookies_cannot_be_saved(*, tmp_path: Path) -> None:
    mock_response = unittest.mock.Mock()
    mock_response.status_code = 200
    mock_response.headers = {
        "Content-Type": "application/octet-stream",
        "Content-Disposition": 'attachment; filename="test.bin"',
    }
    mock_response.iter_content = lambda **_kwargs: [b"data"]
    mock_response.url = "https://drive.google.com/uc?id=dummy"
    mock_sess = unittest.mock.Mock()
    mock_sess.get.return_value = mock_response
    mock_sess.cookies = []
    unwritable = str(tmp_path / "missing" / "cookies.txt")

    with (
        unittest.mock.patch.object(
            sys.modules["gdown.download"],
            "_get_session",
            return_value=(mock_sess, unwritable),
        ),
        unittest.mock.patch.object(
            sys.modules["gdown.download"],
            "_save_cookies",
            side_effect=OSError("read-only"),
        ),
        pytest.warns(UserWarning, match="Failed to save cookies"),
    ):
        download(id="dummy", output=str(tmp_path / "out"), quiet=True)

    assert (tmp_path / "out").read_bytes() == b"data"


def test_vendored_extractor_reads_firefox_profile(*, tmp_path: Path) -> None:
    connection = sqlite3.connect(tmp_path / "cookies.sqlite")
    connection.executescript(
        """
        PRAGMA user_version = 13;
        CREATE TABLE moz_cookies (
            host TEXT, name TEXT, value TEXT, path TEXT, expiry INTEGER,
            isSecure INTEGER, originAttributes TEXT DEFAULT ''
        );
        INSERT INTO moz_cookies (host, name, value, path, expiry, isSecure)
        VALUES ('.google.com', 'SID', 'from-firefox', '/', 4102444800, 1);
        """
    )
    connection.close()

    jar = extract_cookies_from_browser("firefox", profile=str(tmp_path))

    assert [(c.domain, c.name, c.value) for c in jar] == [
        (".google.com", "SID", "from-firefox")
    ]


def test_get_session_loads_cookies_file(*, tmp_path: Path) -> None:
    cookies_file = tmp_path / "cache" / "cookies.txt"
    _save_cookies(
        cookies=[build_google_cookie(name="SID", value="saved")],
        cookies_file=str(cookies_file),
    )

    sess, used_file = _get_session(
        proxy=None,
        use_cookies=True,
        user_agent="test",
        cookies_file=str(cookies_file),
    )

    assert used_file == str(cookies_file)
    assert sess.cookies.get("SID", domain=".google.com") == "saved"
