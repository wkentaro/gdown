import os.path as osp
import sys
import tempfile
import unittest.mock
from pathlib import Path

import pytest

from gdown.download_folder import _GoogleDriveFile
from gdown.download_folder import download_folder
from gdown.exceptions import DownloadError

here = osp.dirname(osp.abspath(__file__))



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


def test_download_folder_dry_run() -> None:
    url = "https://drive.google.com/drive/folders/1KpLl_1tcK0eeehzN980zbG-3M2nhbVks"
    tmp_dir = tempfile.mkdtemp()
    files = download_folder(url=url, output=tmp_dir, skip_download=True)
    assert len(files) == 6
    for file in files:
        assert hasattr(file, "id")
        assert hasattr(file, "path")
        assert hasattr(file, "local_path")
