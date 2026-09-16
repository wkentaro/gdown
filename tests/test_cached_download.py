import hashlib
import http.server
import os
import subprocess
import sys
import tempfile
import threading
import unittest.mock
from pathlib import Path

import pytest

import gdown


def _cached_download(*, hash: str) -> None:
    url = "https://drive.google.com/uc?id=0B9P1L--7Wd2vU3VUVlFnbTgtS2c"
    fd, path = tempfile.mkstemp()
    os.close(fd)
    for _ in range(2):
        gdown.cached_download(url=url, path=path, hash=hash)
    os.remove(path)


@pytest.mark.network
def test_cached_download_md5() -> None:
    _cached_download(hash="md5:cb31a703b96c1ab2f80d164e9676fe7d")


@pytest.mark.network
def test_cached_download_sha1() -> None:
    _cached_download(hash="sha1:69a5a1000f98237efea9231c8a39d05edf013494")


@pytest.mark.network
def test_cached_download_sha256() -> None:
    _cached_download(
        hash="sha256:284e3029cce3ae5ee0b05866100e300046359f53ae4c77fe6b34c05aa7a72cee"
    )


@pytest.mark.parametrize("outcome", ["success", "failure", "interrupt", "hash"])
def test_cached_download_cleans_staging(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    cache = tmp_path / "cache"
    monkeypatch.setattr(sys.modules["gdown.cached_download"], "cache_root", str(cache))
    output = tmp_path / "output"

    def write_download(*, output: str, **_kwargs: object) -> str:
        Path(output).write_bytes(b"data")
        if outcome == "failure":
            raise RuntimeError("failed")
        if outcome == "interrupt":
            raise KeyboardInterrupt
        return output

    monkeypatch.setattr(
        sys.modules["gdown.cached_download"], "download", write_download
    )
    if outcome == "success":
        assert gdown.cached_download(
            url="https://example.com/file", path=str(output), quiet=True
        ) == str(output)
        assert output.read_bytes() == b"data"
    else:
        error = {
            "failure": RuntimeError,
            "interrupt": KeyboardInterrupt,
            "hash": AssertionError,
        }[outcome]
        with pytest.raises(error):
            gdown.cached_download(
                url="https://example.com/file",
                path=str(output),
                quiet=True,
                hash="md5:wrong" if outcome == "hash" else None,
            )
        assert not output.exists()
    assert not [path for path in cache.iterdir() if path.is_dir()]


@pytest.mark.parametrize("matches", [True, False])
def test_cached_download_hashes_the_stream_without_rereading_the_file(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, matches: bool
) -> None:
    body = b"cached download body"
    digest = hashlib.sha256(body).hexdigest() if matches else "0" * 64

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.handle_request, daemon=True).start()
    monkeypatch.setattr(
        sys.modules["gdown.cached_download"], "cache_root", str(tmp_path / "cache")
    )
    monkeypatch.setattr(
        sys.modules["gdown.cached_download"],
        "_compute_filehash",
        unittest.mock.Mock(side_effect=AssertionError("read the finished file back")),
    )
    path = tmp_path / "file"

    def download_file() -> str:
        return gdown.cached_download(
            url=f"http://127.0.0.1:{server.server_port}/",
            path=str(path),
            quiet=True,
            hash=f"sha256:{digest}",
        )

    try:
        if matches:
            assert download_file() == str(path)
            assert path.read_bytes() == body
        else:
            with pytest.raises(AssertionError, match="File hash doesn't match"):
                download_file()
            assert not path.exists()
    finally:
        server.server_close()


def test_import_does_not_create_cache(*, tmp_path: Path) -> None:
    subprocess.run(
        [sys.executable, "-c", "import gdown"],
        env={**os.environ, "HOME": str(tmp_path), "USERPROFILE": str(tmp_path)},
        check=True,
    )
    assert not (tmp_path / ".cache").exists()
