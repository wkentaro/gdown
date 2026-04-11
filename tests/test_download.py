import os
import tempfile
from collections.abc import Iterator
from typing import NamedTuple

import pytest

from gdown.download import download


class DownloadEnv(NamedTuple):
    file_path: str
    url: str


@pytest.fixture()
def download_env() -> Iterator[DownloadEnv]:
    with tempfile.TemporaryDirectory() as d:
        yield DownloadEnv(
            file_path=os.path.join(d, "file"),
            url="https://raw.githubusercontent.com/wkentaro/gdown/3.1.0/gdown/__init__.py",
        )


def test_download(download_env: DownloadEnv) -> None:
    # Usage before https://github.com/wkentaro/gdown/pull/32
    assert (
        download(url=download_env.url, output=download_env.file_path, quiet=False)
        == download_env.file_path
    )


def test_download_progress(download_env: DownloadEnv) -> None:
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
