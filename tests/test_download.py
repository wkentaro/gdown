import os
from pathlib import Path
from typing import Final
from typing import NamedTuple

import pytest

from gdown.download import download

DOWNLOAD_URL: Final[str] = (
    "https://raw.githubusercontent.com/wkentaro/gdown/3.1.0/gdown/__init__.py"
)


class DownloadEnv(NamedTuple):
    file_path: str
    url: str


@pytest.fixture()
def download_env(tmp_path: Path) -> DownloadEnv:
    return DownloadEnv(
        file_path=str(tmp_path / "file"),
        url=DOWNLOAD_URL,
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


def test_download_output_dir_with_trailing_slash(tmp_path: Path) -> None:
    output_dir = str(tmp_path / "subdir") + "/"
    result = download(url=DOWNLOAD_URL, output=output_dir, quiet=True)
    assert isinstance(result, str)
    assert Path(result).parent == tmp_path / "subdir"
    assert Path(result).is_file()


def test_download_output_dir_with_trailing_backslash(tmp_path: Path) -> None:
    output_dir = str(tmp_path / "subdir") + "\\"
    result = download(url=DOWNLOAD_URL, output=output_dir, quiet=True)
    assert isinstance(result, str)
    # On Unix, '\' is a valid filename char, so the dir name includes it.
    # On Windows, '\' is the path separator, so it behaves like '/'.
    assert Path(result).is_file()


def test_download_output_existing_dir(tmp_path: Path) -> None:
    output_dir = tmp_path / "existing"
    output_dir.mkdir()
    result = download(url=DOWNLOAD_URL, output=str(output_dir), quiet=True)
    assert isinstance(result, str)
    assert Path(result).parent == output_dir
    assert Path(result).is_file()


def test_download_resume_skips_existing_file(
    download_env: DownloadEnv, capsys: pytest.CaptureFixture[str]
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


def test_download_resume_skips_existing_file_in_dir(tmp_path: Path) -> None:
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
