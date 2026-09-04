import os
import sys
import tempfile
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


def test_cached_download_redownloads_when_cached_hash_mismatches(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "file"
    path.write_bytes(b"stale")

    def download(
        *,
        url: str,  # noqa: ARG001
        output: str,
        **kwargs: object,  # noqa: ARG001
    ) -> str:
        Path(output).write_bytes(b"data")
        return output

    monkeypatch.setattr(sys.modules["gdown.cached_download"], "download", download)
    monkeypatch.setattr(
        sys.modules["gdown.cached_download"], "cache_root", str(tmp_path)
    )

    result = gdown.cached_download(
        url="https://example.com/file",
        path=str(path),
        quiet=True,
        hash="md5:8d777f385d3dfec8815d20f7496026dc",
    )

    assert result == str(path)
    assert path.read_bytes() == b"data"


@pytest.mark.parametrize(
    ("hash", "error"),
    [
        ("md5:8D777F385D3DFEC8815D20F7496026DC", AssertionError),
        ("md5:0", AssertionError),
        ("md5:not-hexadecimal", AssertionError),
        ("shake_128:00", TypeError),
    ],
)
def test_cached_download_keeps_legacy_hash_behavior(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    hash: str,
    error: type[Exception],
) -> None:
    def download(*, output: str, **_kwargs: object) -> str:
        Path(output).write_bytes(b"data")
        return output

    monkeypatch.setattr(sys.modules["gdown.cached_download"], "download", download)
    monkeypatch.setattr(
        sys.modules["gdown.cached_download"], "cache_root", str(tmp_path)
    )

    with pytest.raises(error):
        gdown.cached_download(
            url="https://example.com/file",
            path=str(tmp_path / "file"),
            quiet=True,
            hash=hash,
        )
