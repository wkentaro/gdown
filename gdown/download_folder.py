from __future__ import annotations

import os
import os.path as osp
import re
import sys
import urllib.parse
from http import HTTPStatus
from typing import Final

import bs4
import requests

from .download import GoogleDriveFileToDownload
from .download import _get_session
from .download import _sanitize_filename
from .download import download
from .exceptions import DownloadError
from .parse_url import _parse_google_drive_folder_id


class _GoogleDriveFile:
    id: str
    name: str
    type: str
    children: list[_GoogleDriveFile]

    TYPE_FOLDER: Final = "application/vnd.google-apps.folder"
    TYPE_DOCUMENT: Final = "application/vnd.google-apps.document"
    TYPE_SPREADSHEET: Final = "application/vnd.google-apps.spreadsheet"
    TYPE_PRESENTATION: Final = "application/vnd.google-apps.presentation"

    def __init__(
        self,
        *,
        id: str,
        name: str,
        type: str,
        children: list[_GoogleDriveFile] | None = None,
    ) -> None:
        self.id = id
        self.name = name
        self.type = type
        self.children = children if children is not None else []

    def is_folder(self) -> bool:
        return self.type == self.TYPE_FOLDER

    def is_google_native(self) -> bool:
        # Any docs.google.com kind (Forms, Drawings, ...) exports too, so the
        # export name must come from the response, not the folder view.
        return self.type.startswith("application/vnd.google-apps.") and not (
            self.is_folder()
        )


def _get_directory_structure(
    *, gdrive_file: _GoogleDriveFile, previous_path: str
) -> list[tuple[_GoogleDriveFile | None, str]]:
    directory_structure = []
    for file in gdrive_file.children:
        file.name = _sanitize_filename(filename=file.name)
        if file.is_folder():
            directory_structure.append((None, osp.join(previous_path, file.name)))
            for i in _get_directory_structure(
                gdrive_file=file,
                previous_path=osp.join(previous_path, file.name),
            ):
                directory_structure.append(i)
        elif not file.children:
            directory_structure.append((file, osp.join(previous_path, file.name)))
    return directory_structure


# Parameters remain positional-or-keyword for backward compatibility.
def download_folder(
    url: str | None = None,
    id: str | None = None,
    output: str | None = None,
    quiet: bool = False,  # noqa: FBT001, FBT002
    proxy: str | None = None,
    speed: float | None = None,
    use_cookies: bool = True,  # noqa: FBT001, FBT002
    verify: bool | str = True,  # noqa: FBT001, FBT002
    user_agent: str | None = None,
    skip_download: bool = False,  # noqa: FBT001, FBT002
    resume: bool = False,  # noqa: FBT001, FBT002
    cookies_file: str | None = None,
) -> list[str] | list[GoogleDriveFileToDownload]:  # noqa: GR005 -- public API accepts both call styles
    """Downloads entire folder from URL.

    Parameters
    ----------
    url:
        URL of the Google Drive folder.
        Must be of the format 'https://drive.google.com/drive/folders/{url}'.
    id:
        Google Drive's folder ID.
    output:
        String containing the path of the output folder.
        Defaults to current working directory.
    quiet:
        Suppress terminal output.
    proxy:
        Proxy.
    speed:
        Download byte size per second (e.g., 256KB/s = 256 * 1024).
    use_cookies:
        Flag to use cookies. Default is True.
    verify:
        Either a bool, in which case it controls whether the server's TLS
        certificate is verified, or a string, in which case it must be a path
        to a CA bundle to use. Default is True.
    user_agent:
        User-agent to use in the HTTP request.
    skip_download:
        If True, return the list of files to download without downloading them.
        Defaults to False.
    resume:
        Resume interrupted transfers.
        Completed output files will be skipped.
        Partial tempfiles will be reused, if the transfer is incomplete.
        Default is False.
    cookies_file:
        Netscape cookies file to load when a session opens and save after
        every Google Drive file response. Default is
        ~/.cache/gdown/cookies.txt. Ignored when use_cookies is False.

    Returns
    -------
    files:
        If skip_download is False, list of local file paths downloaded.
        If skip_download is True, list of GoogleDriveFileToDownload that contains
        id, path, and local_path.

    Raises
    ------
    ValueError
        If neither url nor id is specified, or both are specified.
    DownloadError
        If a file in the folder fails to download.

    Example
    -------
    gdown.download_folder(
        "https://drive.google.com/drive/folders/" +
        "1ZXEhzbLRLU1giKKRJkjm8N04cO_JoYE2",
    )
    """
    if not (id is None) ^ (url is None):
        raise ValueError("Either url or id has to be specified")
    if id is None:
        assert url is not None
        folder_id = _extract_folder_id(url=url)
    else:
        folder_id = id
    FOLDER_USER_AGENT: Final = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36"  # NOQA: E501
    sess, _ = _get_session(
        proxy=proxy,
        use_cookies=use_cookies,
        # Folder listing needs a different default agent than file download.
        user_agent=FOLDER_USER_AGENT if user_agent is None else user_agent,
        cookies_file=cookies_file,
    )
    try:
        if not quiet:
            print("Retrieving folder contents", file=sys.stderr)
        gdrive_file = _download_and_parse_google_drive_link(
            sess=sess,
            folder_id=folder_id,
            quiet=quiet,
            verify=verify,
        )
    finally:
        sess.close()

    gdrive_file.name = _sanitize_filename(filename=gdrive_file.name)

    if not quiet:
        print("Retrieving folder contents completed", file=sys.stderr)
        print("Building directory structure", file=sys.stderr)
    directory_structure = _get_directory_structure(
        gdrive_file=gdrive_file, previous_path=""
    )
    if not quiet:
        print("Building directory structure completed", file=sys.stderr)

    if output is None:
        output = os.getcwd() + osp.sep
    if output.endswith(osp.sep):
        root_dir = osp.join(output, gdrive_file.name)
    else:
        root_dir = output
    if not skip_download and not osp.exists(root_dir):
        os.makedirs(root_dir)

    files = []
    failed_paths: list[str] = []
    for gdrive_file, path in directory_structure:
        local_path = osp.join(root_dir, path)

        if gdrive_file is None:  # folder
            if not skip_download and not osp.exists(local_path):
                os.makedirs(local_path)
            continue

        if skip_download and not gdrive_file.is_google_native():
            files.append(
                GoogleDriveFileToDownload(
                    id=gdrive_file.id, path=path, local_path=local_path
                )
            )
            continue

        download_output = local_path
        if gdrive_file.is_google_native():
            # The folder view omits the selected export extension.
            download_output = (
                None if skip_download else osp.dirname(local_path) + osp.sep
            )
        try:
            downloaded_file = download(
                url="https://drive.google.com/uc?id=" + gdrive_file.id,
                output=download_output,
                quiet=quiet,
                proxy=proxy,
                speed=speed,
                use_cookies=use_cookies,
                verify=verify,
                resume=resume,
                cookies_file=cookies_file,
                user_agent=user_agent,
                skip_download=skip_download,
            )
        except DownloadError as e:
            if skip_download:
                raise
            failed_paths.append(local_path)
            if not quiet:
                print(f"Failed to download {local_path}: {e}", file=sys.stderr)
            continue

        if skip_download:
            assert isinstance(downloaded_file, GoogleDriveFileToDownload)
            path = osp.join(osp.dirname(path), downloaded_file.path)
            files.append(
                GoogleDriveFileToDownload(
                    id=gdrive_file.id,
                    path=path,
                    local_path=osp.join(root_dir, path),
                )
            )
        else:
            files.append(downloaded_file)
    if failed_paths:
        raise DownloadError(
            "Failed to download the following files:\n"
            + "\n".join(f"- {path}" for path in failed_paths)
        )
    if not quiet:
        print("Download completed", file=sys.stderr)
    return files


def _extract_folder_id(*, url: str) -> str:
    return (
        _parse_google_drive_folder_id(url=url)
        or urllib.parse.urlparse(url).path.rstrip("/").split("/")[-1]
    )


def _parse_embedded_folder_view(
    *,
    sess: requests.Session,
    folder_id: str,
    verify: bool | str,
) -> tuple[str, list[tuple[str, str, str]]]:
    params = urllib.parse.urlencode({"id": folder_id})
    url = f"https://drive.google.com/embeddedfolderview?{params}"
    res = sess.get(url, verify=verify)
    if res.status_code != HTTPStatus.OK:
        raise DownloadError(
            f"Failed to retrieve folder contents for folder ID: {folder_id} "
            f"(status code {res.status_code}). "
            "You may need to change the permission to "
            "'Anyone with the link', or have had many accesses. "
            "Check FAQ in https://github.com/wkentaro/gdown?tab=readme-ov-file#faq.",
        )

    soup = bs4.BeautifulSoup(res.text, features="html.parser")

    if soup.title is None or soup.title.string is None:
        raise DownloadError(
            f"Failed to parse folder contents for folder ID: {folder_id}. "
            "The page structure may have changed.",
        )
    folder_name = soup.title.string

    children: list[tuple[str, str, str]] = []
    for a_tag in soup.find_all(name="a"):
        href = a_tag.get("href", "")
        if not isinstance(href, str):
            continue

        file_match = re.match(
            pattern=r"https://drive\.google\.com/file/d/([-\w]{25,})/view",
            string=href,
        )
        if file_match:
            file_id = file_match.group(1)
            file_name = a_tag.get_text(strip=True)
            children.append((file_id, file_name, "application/octet-stream"))
            continue

        # The link host, not the visible name, tells Google-native files apart.
        docs_match = re.match(
            pattern=r"https://docs\.google\.com/(\w+)/d/([-\w]{25,})/",
            string=href,
        )
        if docs_match:
            kind, file_id = docs_match.groups()
            file_name = a_tag.get_text(strip=True)
            # Drive's MIME types are singular ("spreadsheet"); the URL is not.
            file_type = "application/vnd.google-apps." + kind.removesuffix("s")
            children.append((file_id, file_name, file_type))
            continue

        child_folder_id = _parse_google_drive_folder_id(url=href)
        if child_folder_id is not None:
            child_name = a_tag.get_text(strip=True)
            children.append((child_folder_id, child_name, _GoogleDriveFile.TYPE_FOLDER))
            continue

    return (folder_name, children)


def _download_and_parse_google_drive_link(
    *,
    sess: requests.Session,
    folder_id: str,
    quiet: bool,
    verify: bool | str,
) -> _GoogleDriveFile:
    folder_name, children = _parse_embedded_folder_view(
        sess=sess, folder_id=folder_id, verify=verify
    )

    gdrive_file = _GoogleDriveFile(
        id=folder_id,
        name=folder_name,
        type=_GoogleDriveFile.TYPE_FOLDER,
    )

    for child_id, child_name, child_type in children:
        if child_type != _GoogleDriveFile.TYPE_FOLDER:
            if not quiet:
                print(
                    "Processing file",
                    child_id,
                    child_name,
                )
            gdrive_file.children.append(
                _GoogleDriveFile(
                    id=child_id,
                    name=child_name,
                    type=child_type,
                )
            )
            continue

        if not quiet:
            print(
                "Retrieving folder",
                child_id,
                child_name,
            )
        child = _download_and_parse_google_drive_link(
            sess=sess,
            folder_id=child_id,
            quiet=quiet,
            verify=verify,
        )
        gdrive_file.children.append(child)
    return gdrive_file
