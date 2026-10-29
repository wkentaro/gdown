import errno
import hashlib
import http.server
import os
import shutil
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
    stagings: list[Path] = []

    def write_download(*, output: str, **_kwargs: object) -> str:
        stagings.append(Path(output).parent)
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
    [staging] = stagings
    assert staging.parent == tmp_path
    assert staging.name.startswith(".output.")
    assert staging.name.endswith(".gdown")
    assert {path for path in tmp_path.iterdir() if path.is_dir()} == {cache}


def test_cached_download_accepts_a_maximum_length_name(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        sys.modules["gdown.cached_download"], "cache_root", str(tmp_path / "cache")
    )
    output = tmp_path / ("a" * 255)

    def write_download(*, output: str, **_kwargs: object) -> str:
        Path(output).write_bytes(b"data")
        return output

    monkeypatch.setattr(
        sys.modules["gdown.cached_download"], "download", write_download
    )
    assert gdown.cached_download(
        url="https://example.com/file", path=str(output), quiet=True
    ) == str(output)
    assert output.read_bytes() == b"data"


def test_cached_download_cache_hits_only_see_complete_files(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = tmp_path / "cache"
    output = tmp_path / "output"
    body = b"complete downloaded payload"
    observed: list[bytes] = []
    monkeypatch.setattr(sys.modules["gdown.cached_download"], "cache_root", str(cache))

    def write_download(*, output: str, **_kwargs: object) -> str:
        Path(output).write_bytes(body)
        return output

    def observe_cache_hit() -> None:
        path = gdown.cached_download(
            url="https://example.com/file", path=str(output), quiet=True
        )
        observed.append(Path(path).read_bytes())

    real_rename, real_replace, real_copyfile = os.rename, os.replace, shutil.copyfile

    def rename(source: str, destination: str) -> None:
        if Path(destination) == output and cache in Path(source).parents:
            # Model a cache and destination on different mounted filesystems.
            raise OSError(errno.EXDEV, "cross-device link")
        real_rename(source, destination)
        if Path(destination) == output:
            observe_cache_hit()

    def replace(source: str, destination: str) -> None:
        real_replace(source, destination)
        if Path(destination) == output:
            observe_cache_hit()

    def copyfile(source: str, destination: str, *, follow_symlinks: bool = True) -> str:
        if Path(destination) != output:
            return real_copyfile(source, destination, follow_symlinks=follow_symlinks)
        with open(source, "rb") as src, open(destination, "wb") as dst:
            dst.write(src.read(3))
            dst.flush()
            # Interleave another caller while shutil.move's fallback copies.
            observe_cache_hit()
            shutil.copyfileobj(src, dst)
        return destination

    monkeypatch.setattr(
        sys.modules["gdown.cached_download"], "download", write_download
    )
    monkeypatch.setattr(os, "rename", rename)
    monkeypatch.setattr(os, "replace", replace)
    monkeypatch.setattr(shutil, "copyfile", copyfile)

    assert gdown.cached_download(
        url="https://example.com/file", path=str(output), quiet=True
    ) == str(output)
    assert observed == [body]
    assert output.read_bytes() == body


@pytest.mark.parametrize("existing", [False, True])
def test_cached_download_failed_publication_preserves_destination(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing: bool
) -> None:
    cache = tmp_path / "cache"
    output = tmp_path / "output"
    body = b"complete downloaded payload"
    if existing:
        output.write_bytes(b"previous file")
    monkeypatch.setattr(sys.modules["gdown.cached_download"], "cache_root", str(cache))

    def write_download(
        *, output: str, hasher: "hashlib._Hash | None" = None, **_kwargs: object
    ) -> str:
        Path(output).write_bytes(body)
        if hasher is not None:
            hasher.update(body)
        return output

    real_rename, real_replace, real_copyfile = os.rename, os.replace, shutil.copyfile

    def rename(source: str, destination: str) -> None:
        if Path(destination) == output:
            if cache in Path(source).parents:
                raise OSError(errno.EXDEV, "cross-device link")
            raise OSError(errno.EIO, "publication failed")
        real_rename(source, destination)

    def replace(source: str, destination: str) -> None:
        if Path(destination) == output:
            raise OSError(errno.EIO, "publication failed")
        real_replace(source, destination)

    def copyfile(source: str, destination: str, *, follow_symlinks: bool = True) -> str:
        if Path(destination) != output:
            return real_copyfile(source, destination, follow_symlinks=follow_symlinks)
        Path(destination).write_bytes(b"par")
        raise OSError(errno.EIO, "publication failed")

    monkeypatch.setattr(
        sys.modules["gdown.cached_download"], "download", write_download
    )
    monkeypatch.setattr(os, "rename", rename)
    monkeypatch.setattr(os, "replace", replace)
    monkeypatch.setattr(shutil, "copyfile", copyfile)

    with pytest.raises(OSError, match="publication failed"):
        gdown.cached_download(
            url="https://example.com/file",
            path=str(output),
            quiet=True,
            hash=f"sha256:{hashlib.sha256(body).hexdigest()}",
        )
    if existing:
        assert output.read_bytes() == b"previous file"
    else:
        assert not output.exists()
    assert set(tmp_path.iterdir()) == ({cache, output} if existing else {cache})


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
