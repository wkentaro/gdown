import os.path as osp
import re
import sys
import tempfile
import unittest.mock
from pathlib import Path
from typing import Final

import pytest
import requests

from gdown.download_folder import _GoogleDriveFile
from gdown.download_folder import _parse_embedded_folder_view
from gdown.download_folder import download_folder
from gdown.exceptions import DownloadError

from .conftest import build_response

here = osp.dirname(osp.abspath(__file__))


@pytest.mark.network
def test_download_folder_google_slides_without_extension(*, tmp_path: Path) -> None:
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


def _make_folder_root(*, name: str, child_names: list[str]) -> _GoogleDriveFile:
    return _GoogleDriveFile(
        id="root_id",
        name=name,
        type=_GoogleDriveFile.TYPE_FOLDER,
        children=[
            _GoogleDriveFile(
                id=f"child_{index}",
                name=child_name,
                type="text/plain",
            )
            for index, child_name in enumerate(child_names)
        ],
    )


def test_root_folder_name_path_traversal_is_sanitized(*, tmp_path: Path) -> None:
    root = _make_folder_root(name="../../evil", child_names=["safe_file.txt"])
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


def test_download_folder_lists_every_failed_file(*, tmp_path: Path) -> None:
    root = _make_folder_root(name="folder", child_names=["first.txt", "second.txt"])
    first_path = tmp_path / "folder" / "first.txt"
    second_path = tmp_path / "folder" / "second.txt"

    with (
        unittest.mock.patch.object(
            sys.modules["gdown.download_folder"],
            "_download_and_parse_google_drive_link",
            return_value=root,
        ),
        unittest.mock.patch.object(
            sys.modules["gdown.download_folder"],
            "download",
            side_effect=[DownloadError("first error"), DownloadError("second error")],
        ),
        pytest.raises(DownloadError) as exc_info,
    ):
        download_folder(
            url="https://drive.google.com/drive/folders/dummy",
            output=str(tmp_path) + osp.sep,
            quiet=True,
        )

    assert str(first_path) in str(exc_info.value)
    assert str(second_path) in str(exc_info.value)


def test_download_folder_does_not_catch_other_errors(*, tmp_path: Path) -> None:
    root = _make_folder_root(name="folder", child_names=["first.txt", "second.txt"])

    with (
        unittest.mock.patch.object(
            sys.modules["gdown.download_folder"],
            "_download_and_parse_google_drive_link",
            return_value=root,
        ),
        unittest.mock.patch.object(
            sys.modules["gdown.download_folder"],
            "download",
            side_effect=OSError("disk full"),
        ) as mock_download,
        pytest.raises(OSError, match="disk full"),
    ):
        download_folder(
            url="https://drive.google.com/drive/folders/dummy",
            output=str(tmp_path) + osp.sep,
            quiet=True,
        )

    mock_download.assert_called_once()


def test_download_folder_returns_every_file_after_success(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _make_folder_root(name="folder", child_names=["first.txt", "second.txt"])
    downloaded_paths = [str(tmp_path / name) for name in ("first.txt", "second.txt")]

    with (
        unittest.mock.patch.object(
            sys.modules["gdown.download_folder"],
            "_download_and_parse_google_drive_link",
            return_value=root,
        ),
        unittest.mock.patch.object(
            sys.modules["gdown.download_folder"],
            "download",
            side_effect=downloaded_paths,
        ),
    ):
        files = download_folder(
            url="https://drive.google.com/drive/folders/dummy",
            output=str(tmp_path) + osp.sep,
            quiet=False,
        )

    assert files == downloaded_paths
    assert "Download completed\n" in capsys.readouterr().err


def test_download_folder_closes_session_when_parsing_raises() -> None:
    session = unittest.mock.Mock()

    with (
        unittest.mock.patch.object(
            sys.modules["gdown.download_folder"],
            "_get_session",
            return_value=(session, "cookies.txt"),
        ),
        unittest.mock.patch.object(
            sys.modules["gdown.download_folder"],
            "_download_and_parse_google_drive_link",
            side_effect=DownloadError("parse failed"),
        ),
        pytest.raises(DownloadError, match="parse failed"),
    ):
        download_folder(id="folder_id", quiet=True)

    session.close.assert_called_once_with()


def test_download_folder_parses_id_before_url_suffix(*, tmp_path: Path) -> None:
    folder_id = "1uUbx_lRLLE9O4WnI8TS77dUOJw_DjljV"

    with unittest.mock.patch.object(
        sys.modules["gdown.download_folder"],
        "_download_and_parse_google_drive_link",
        return_value=_make_folder_root(name="folder", child_names=["file.txt"]),
    ) as parse_folder:
        download_folder(
            url=f"https://drive.google.com/drive/folders/{folder_id}/view",
            output=str(tmp_path),
            quiet=True,
            skip_download=True,
        )

    assert parse_folder.call_args.kwargs["folder_id"] == folder_id


def test_parse_embedded_folder_view() -> None:
    html_file = osp.join(here, "data/embedded-folder-view-sample.html")
    with open(html_file) as f:
        content = f.read()

    mock_response = unittest.mock.Mock()
    mock_response.status_code = 200
    mock_response.text = content

    mock_sess = unittest.mock.Mock()
    mock_sess.get.return_value = mock_response

    result = _parse_embedded_folder_view(
        sess=mock_sess, folder_id="test_folder_id", verify=True
    )

    assert result is not None
    folder_name, children = result
    assert folder_name == "files_100"
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


def test_parse_embedded_folder_view_http_error() -> None:
    mock_response = unittest.mock.Mock()
    mock_response.status_code = 404

    mock_sess = unittest.mock.Mock()
    mock_sess.get.return_value = mock_response

    with pytest.raises(DownloadError, match="status code 404"):
        _parse_embedded_folder_view(
            sess=mock_sess, folder_id="nonexistent", verify=True
        )


def test_parse_embedded_folder_view_malformed_html() -> None:
    mock_response = unittest.mock.Mock()
    mock_response.status_code = 200
    mock_response.text = "<html><body>no title</body></html>"

    mock_sess = unittest.mock.Mock()
    mock_sess.get.return_value = mock_response

    with pytest.raises(DownloadError, match="page structure may have changed"):
        _parse_embedded_folder_view(sess=mock_sess, folder_id="test", verify=True)


@pytest.mark.network
def test_download_folder_dry_run() -> None:
    EXPECTED_FILE_COUNT: Final = 6
    url = "https://drive.google.com/drive/folders/1KpLl_1tcK0eeehzN980zbG-3M2nhbVks"
    tmp_dir = tempfile.mkdtemp()
    files = download_folder(url=url, output=tmp_dir, skip_download=True)
    assert len(files) == EXPECTED_FILE_COUNT
    for file in files:
        assert hasattr(file, "id")
        assert hasattr(file, "path")
        assert hasattr(file, "local_path")


@pytest.mark.parametrize("quiet", [False, True])
def test_download_folder_continues_after_truncation_then_resumes(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], quiet: bool
) -> None:
    root = _make_folder_root(name="folder", child_names=["first.txt", "second.txt"])
    first_path = tmp_path / "first.txt"
    second_path = tmp_path / "second.txt"
    responses = {
        "child_0": build_response(
            headers={
                "Content-Disposition": 'attachment; filename="first.txt"',
                "Content-Length": "10",
            },
            chunks=[b"data"],
        ),
        "child_1": build_response(
            headers={
                "Content-Disposition": 'attachment; filename="second.txt"',
                "Content-Length": "6",
            },
            chunks=[b"second"],
        ),
    }

    def get_response(
        url: str, *, headers: dict[str, str] | None = None, **_kwargs: object
    ) -> unittest.mock.Mock:
        if headers is not None:
            assert headers == {"Range": "bytes=4-"}
            return build_response(headers={"Content-Length": "6"}, chunks=[b"123456"])
        file_id = url.rsplit("=", 1)[1]
        if file_id == "child_1" and not second_path.exists():
            stderr = capsys.readouterr().err
            if quiet:
                assert stderr == ""
            else:
                assert (
                    f"Failed to download {first_path}: Download is incomplete" in stderr
                )
                assert "received 4 bytes" in stderr
                assert "Download completed" not in stderr
        return responses[file_id]

    with (
        unittest.mock.patch.object(
            sys.modules["gdown.download_folder"],
            "_download_and_parse_google_drive_link",
            return_value=root,
        ),
        unittest.mock.patch("requests.sessions.Session.get", side_effect=get_response),
    ):
        with pytest.raises(DownloadError, match=re.escape(str(first_path))):
            download_folder(
                id="root_id", output=str(tmp_path), quiet=quiet, use_cookies=False
            )

        stderr = capsys.readouterr().err
        assert "Download completed" not in stderr
        if quiet:
            assert stderr == ""
        assert not first_path.exists()
        (part,) = tmp_path.glob("first.txt*.part")
        assert part.read_bytes() == b"data"
        assert second_path.read_bytes() == b"second"

        responses["child_1"].iter_content.side_effect = AssertionError(
            "Completed files must not be downloaded again"
        )
        files = download_folder(
            id="root_id",
            output=str(tmp_path),
            quiet=quiet,
            use_cookies=False,
            resume=True,
        )

    assert files == [str(first_path), str(second_path)]
    assert first_path.read_bytes() == b"data123456"
    assert second_path.read_bytes() == b"second"
    assert not part.exists()
    stderr = capsys.readouterr().err
    if quiet:
        assert stderr == ""
    else:
        assert "Download completed\n" in stderr


@pytest.mark.parametrize("user_agent", [None, "custom-agent"])
def test_download_folder_preserves_user_agent(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, user_agent: str | None
) -> None:
    agents = []
    file_id = "x" * 25

    def get_response(
        session: requests.Session, url: str, **_kwargs: object
    ) -> unittest.mock.Mock:
        agents.append(session.headers["User-Agent"])
        if "embeddedfolderview" in url:
            response = unittest.mock.Mock()
            response.status_code = 200
            response.text = (
                "<title>folder</title>"
                f'<a href="https://drive.google.com/file/d/{file_id}/view">file.txt</a>'
            )
            return response
        return build_response(
            headers={"Content-Disposition": 'attachment; filename="file.txt"'},
            chunks=[b"data"],
        )

    monkeypatch.setattr(requests.Session, "get", get_response)
    files = download_folder(
        id="folder-id",
        output=str(tmp_path),
        quiet=True,
        use_cookies=False,
        user_agent=user_agent,
    )
    assert files == [str(tmp_path / "file.txt")]
    assert (tmp_path / "file.txt").read_bytes() == b"data"
    if user_agent is None:
        assert "Chrome/98" in agents[0]
        assert "Chrome/39" in agents[1]
    else:
        assert agents == [user_agent, user_agent]
