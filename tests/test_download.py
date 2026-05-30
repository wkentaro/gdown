import os
import sys
import unittest.mock
from pathlib import Path
from typing import Final
from typing import NamedTuple

import pytest

from gdown.download import GoogleDriveFileToDownload
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


@pytest.mark.network
def test_download(download_env: DownloadEnv) -> None:
    # Usage before https://github.com/wkentaro/gdown/pull/32
    assert (
        download(url=download_env.url, output=download_env.file_path, quiet=False)
        == download_env.file_path
    )


@pytest.mark.network
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


@pytest.mark.network
def test_download_output_dir_with_trailing_slash(tmp_path: Path) -> None:
    output_dir = str(tmp_path / "subdir") + "/"
    result = download(url=DOWNLOAD_URL, output=output_dir, quiet=True)
    assert isinstance(result, str)
    assert Path(result).parent == tmp_path / "subdir"
    assert Path(result).is_file()


@pytest.mark.network
def test_download_output_dir_with_trailing_backslash(tmp_path: Path) -> None:
    output_dir = str(tmp_path / "subdir") + "\\"
    result = download(url=DOWNLOAD_URL, output=output_dir, quiet=True)
    assert isinstance(result, str)
    # On Unix, '\' is a valid filename char, so the dir name includes it.
    # On Windows, '\' is the path separator, so it behaves like '/'.
    assert Path(result).is_file()


@pytest.mark.network
def test_download_output_existing_dir(tmp_path: Path) -> None:
    output_dir = tmp_path / "existing"
    output_dir.mkdir()
    result = download(url=DOWNLOAD_URL, output=str(output_dir), quiet=True)
    assert isinstance(result, str)
    assert Path(result).parent == output_dir
    assert Path(result).is_file()


@pytest.mark.network
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


@pytest.mark.network
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


@pytest.mark.parametrize(
    "share_url",
    [
        "https://drive.google.com/file/d/0B9P1L--7Wd2vU3VUVlFnbTgtS2c/view?usp=sharing",
        "https://drive.google.com/open?id=0B9P1L--7Wd2vU3VUVlFnbTgtS2c",
        "https://drive.google.com/uc?id=0B9P1L--7Wd2vU3VUVlFnbTgtS2c",
    ],
)
def test_download_rewrites_google_drive_share_link(
    tmp_path: Path, share_url: str
) -> None:
    expected_url = "https://drive.google.com/uc?id=0B9P1L--7Wd2vU3VUVlFnbTgtS2c"

    mock_response = unittest.mock.Mock()
    mock_response.status_code = 200
    mock_response.headers = {
        "Content-Type": "application/octet-stream",
        "Content-Disposition": 'attachment; filename="test.bin"',
    }
    mock_response.iter_content = lambda chunk_size: [b"data"]
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


def test_download_skip_download_returns_file_object(tmp_path: Path) -> None:
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
def test_download_google_slides_without_extension(tmp_path: Path) -> None:
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
