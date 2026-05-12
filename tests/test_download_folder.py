import os.path as osp
import sys
import tempfile
import unittest.mock
from pathlib import Path

import pytest

from gdown.download_folder import _GoogleDriveFile
from gdown.download_folder import _parse_embedded_folder_view
from gdown.download_folder import download_folder
from gdown.exceptions import DownloadError

here = osp.dirname(osp.abspath(__file__))


@pytest.mark.network
def test_download_folder_google_slides_without_extension(tmp_path: Path) -> None:
    # The folder contains a Google Slides file named "gdown" with no extension in
    # Google Drive. Previously, download_folder() passed this extensionless name as
    # the output path to download(), which saved the file without .pptx extension.
    # The fix passes the directory instead, letting download() resolve the filename
    # (including extension) from the Content-Disposition header.
    url = "https://drive.google.com/drive/folders/12zxlvJtuHFV6awc3AINaNHnfvRttPv0i"
    files = download_folder(url=url, output=str(tmp_path), quiet=True)
    assert len(files) == 1
    assert isinstance(files[0], str)
    assert files[0].endswith(".pptx")


def _make_folder_root(
    name: str = "folder", child_name: str = "file.txt"
) -> _GoogleDriveFile:
    return _GoogleDriveFile(
        id="root_id",
        name=name,
        type=_GoogleDriveFile.TYPE_FOLDER,
        children=[
            _GoogleDriveFile(
                id="child_id",
                name=child_name,
                type="text/plain",
            ),
        ],
    )


def test_root_folder_name_path_traversal_is_sanitized(tmp_path: Path) -> None:
    root = _make_folder_root(name="../../evil", child_name="safe_file.txt")
    output_dir = str(tmp_path) + osp.sep

    with unittest.mock.patch.object(
        sys.modules["gdown.download_folder"],
        "_download_and_parse_google_drive_link",
        return_value=root,
    ):
        files = download_folder(
            url="https://drive.google.com/drive/folders/dummy",
            output=output_dir,
            skip_download=True,
            quiet=True,
        )

    for file in files:
        assert not isinstance(file, str)
        resolved = osp.realpath(file.local_path)
        assert resolved.startswith(osp.realpath(output_dir))


def test_download_folder_propagates_download_error(tmp_path: Path) -> None:
    root = _make_folder_root()

    with (
        unittest.mock.patch.object(
            sys.modules["gdown.download_folder"],
            "_download_and_parse_google_drive_link",
            return_value=root,
        ),
        unittest.mock.patch.object(
            sys.modules["gdown.download_folder"],
            "download",
            side_effect=DownloadError("access denied"),
        ),
        pytest.raises(DownloadError, match="access denied"),
    ):
        download_folder(
            url="https://drive.google.com/drive/folders/dummy",
            output=str(tmp_path) + osp.sep,
            quiet=True,
        )


def test_parse_embedded_folder_view() -> None:
    html_file = osp.join(here, "data/embedded-folder-view-sample.html")
    with open(html_file) as f:
        content = f.read()

    mock_response = unittest.mock.Mock()
    mock_response.status_code = 200
    mock_response.text = content

    mock_sess = unittest.mock.Mock()
    mock_sess.get.return_value = mock_response

    result = _parse_embedded_folder_view(sess=mock_sess, folder_id="test_folder_id")

    assert result is not None
    folder_name, children = result
    assert folder_name == "files_100"
    assert len(children) == 4

    ids = [r[0] for r in children]
    names = [r[1] for r in children]
    types = [r[2] for r in children]

    assert ids == [
        "108RHF3bQb6dgOByv_KMGzHuktJOwU_jL",
        "1Sul7bhaimPjncS2GE73nVloSPQbtyzu-",
        "1xYz2AbCdEfGhIjKlMnOpQrStUvWxYz3A",
        "1aMZqPaU03E7XOQNXtjSCdguRHBaIQ82m",
    ]
    assert names == ["file_00.txt", "file_01.txt", "photo.jpg", "subfolder"]
    assert types == [
        "application/octet-stream",
        "application/octet-stream",
        "application/octet-stream",
        _GoogleDriveFile.TYPE_FOLDER,
    ]


@pytest.mark.parametrize(
    ("include", "expected_urls"),
    [
        (
            ["shad"],
            ["https://drive.google.com/uc?id=shad_id"],
        ),
        (
            ["shad", "igu"],
            [
                "https://drive.google.com/uc?id=shad_id",
                "https://drive.google.com/uc?id=mc_igu_id",
            ],
        ),
    ],
)
def test_download_folder_include_filters_files_by_name_substring(
    tmp_path: Path,
    include: list[str],
    expected_urls: list[str],
) -> None:
    with (
        unittest.mock.patch.object(
            sys.modules["gdown.download_folder"],
            "_parse_embedded_folder_view",
            return_value=(
                "music_folder",
                [
                    ("shad_id", "shad - track 1.mp3", "audio/mpeg"),
                    ("mc_igu_id", "mc igu - track 2.mp3", "audio/mpeg"),
                    ("other_id", "random song.mp3", "audio/mpeg"),
                ],
            ),
        ),
        unittest.mock.patch.object(
            sys.modules["gdown.download_folder"],
            "download",
            return_value="dummy-output",
        ) as mock_download,
    ):
        download_folder(
            url="https://drive.google.com/drive/folders/dummy",
            output=str(tmp_path) + osp.sep,
            include=include,
            quiet=True,
        )

    assert [
        call.kwargs["url"] for call in mock_download.call_args_list
    ] == expected_urls


def test_download_folder_without_include_downloads_all_files(
    tmp_path: Path,
) -> None:
    with (
        unittest.mock.patch.object(
            sys.modules["gdown.download_folder"],
            "_parse_embedded_folder_view",
            return_value=(
                "music_folder",
                [
                    ("shad_id", "shad - track 1.mp3", "audio/mpeg"),
                    ("mc_igu_id", "mc igu - track 2.mp3", "audio/mpeg"),
                    ("other_id", "random song.mp3", "audio/mpeg"),
                ],
            ),
        ),
        unittest.mock.patch.object(
            sys.modules["gdown.download_folder"],
            "download",
            return_value="dummy-output",
        ) as mock_download,
    ):
        download_folder(
            url="https://drive.google.com/drive/folders/dummy",
            output=str(tmp_path) + osp.sep,
            quiet=True,
        )

    assert [call.kwargs["url"] for call in mock_download.call_args_list] == [
        "https://drive.google.com/uc?id=shad_id",
        "https://drive.google.com/uc?id=mc_igu_id",
        "https://drive.google.com/uc?id=other_id",
    ]


def test_parse_embedded_folder_view_http_error() -> None:
    mock_response = unittest.mock.Mock()
    mock_response.status_code = 404

    mock_sess = unittest.mock.Mock()
    mock_sess.get.return_value = mock_response

    with pytest.raises(DownloadError, match="status code 404"):
        _parse_embedded_folder_view(sess=mock_sess, folder_id="nonexistent")


def test_parse_embedded_folder_view_malformed_html() -> None:
    mock_response = unittest.mock.Mock()
    mock_response.status_code = 200
    mock_response.text = "<html><body>no title</body></html>"

    mock_sess = unittest.mock.Mock()
    mock_sess.get.return_value = mock_response

    with pytest.raises(DownloadError, match="page structure may have changed"):
        _parse_embedded_folder_view(sess=mock_sess, folder_id="test")


@pytest.mark.network
def test_download_folder_dry_run() -> None:
    url = "https://drive.google.com/drive/folders/1KpLl_1tcK0eeehzN980zbG-3M2nhbVks"
    tmp_dir = tempfile.mkdtemp()
    files = download_folder(url=url, output=tmp_dir, skip_download=True)
    assert len(files) == 6
    for file in files:
        assert hasattr(file, "id")
        assert hasattr(file, "path")
        assert hasattr(file, "local_path")
