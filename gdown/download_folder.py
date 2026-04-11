from __future__ import annotations

import collections
import os
import os.path as osp
import re
import sys
import urllib.parse

import bs4
import requests

from .download import _get_session
from .download import _sanitize_filename
from .download import download
from .exceptions import DownloadError


class _GoogleDriveFile:
    TYPE_FOLDER = "application/vnd.google-apps.folder"

    def __init__(
        self,
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


def _get_directory_structure(
    gdrive_file: _GoogleDriveFile, previous_path: str
) -> list[tuple[str | None, str]]:
    """Converts a Google Drive folder structure into a local directory list."""

    directory_structure = []
    for file in gdrive_file.children:
        file.name = _sanitize_filename(filename=file.name)
        if file.is_folder():
            directory_structure.append((None, osp.join(previous_path, file.name)))
            for i in _get_directory_structure(file, osp.join(previous_path, file.name)):
                directory_structure.append(i)
        elif not file.children:
            directory_structure.append((file.id, osp.join(previous_path, file.name)))
    return directory_structure


GoogleDriveFileToDownload = collections.namedtuple(
    "GoogleDriveFileToDownload", ("id", "path", "local_path")
)


def download_folder(
    url: str | None = None,
    id: str | None = None,
    output: str | None = None,
    quiet: bool = False,
    proxy: str | None = None,
    speed: float | None = None,
    use_cookies: bool = True,
    verify: bool | str = True,
    user_agent: str | None = None,
    skip_download: bool = False,
    resume: bool = False,
) -> list[str] | list[GoogleDriveFileToDownload]:
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
    if id is not None:
        folder_id = id
    else:
        assert url is not None
        folder_id = _extract_folder_id(url)
    if user_agent is None:
        # We need to use different user agent for folder download c.f., file
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36"  # NOQA: E501

    sess, _ = _get_session(proxy=proxy, use_cookies=use_cookies, user_agent=user_agent)

    if not quiet:
        print("Retrieving folder contents", file=sys.stderr)
    gdrive_file = _download_and_parse_google_drive_link(
        sess=sess,
        folder_id=folder_id,
        quiet=quiet,
        verify=verify,
    )

    gdrive_file.name = _sanitize_filename(filename=gdrive_file.name)

    if not quiet:
        print("Retrieving folder contents completed", file=sys.stderr)
        print("Building directory structure", file=sys.stderr)
    directory_structure = _get_directory_structure(gdrive_file, previous_path="")
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
    for id, path in directory_structure:
        local_path = osp.join(root_dir, path)

        if id is None:  # folder
            if not skip_download and not osp.exists(local_path):
                os.makedirs(local_path)
            continue

        if skip_download:
            files.append(
                GoogleDriveFileToDownload(id=id, path=path, local_path=local_path)
            )
        else:
            # Google-native files (Docs, Sheets, Slides) have no extension
            # in the folder listing. Pass the directory so download() resolves
            # the correct filename from the Content-Disposition header.
            if osp.splitext(local_path)[1]:
                download_output = local_path
            else:
                download_output = osp.dirname(local_path) + osp.sep
            local_path = download(
                url="https://drive.google.com/uc?id=" + id,
                output=download_output,
                quiet=quiet,
                proxy=proxy,
                speed=speed,
                use_cookies=use_cookies,
                verify=verify,
                resume=resume,
            )
            files.append(local_path)
    if not quiet:
        print("Download completed", file=sys.stderr)
    return files


def _extract_folder_id(url: str) -> str:
    return urllib.parse.urlparse(url).path.rstrip("/").split("/")[-1]


def _parse_embedded_folder_view(
    sess: requests.Session,
    folder_id: str,
    verify: bool | str = True,
) -> tuple[str, list[tuple[str, str, str]]]:
    params = urllib.parse.urlencode({"id": folder_id})
    url = f"https://drive.google.com/embeddedfolderview?{params}"
    res = sess.get(url, verify=verify)
    if res.status_code != 200:
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

        # Google-native files (Docs, Sheets, Slides) use docs.google.com
        docs_match = re.match(
            pattern=r"https://docs\.google\.com/\w+/d/([-\w]{25,})/",
            string=href,
        )
        if docs_match:
            file_id = docs_match.group(1)
            file_name = a_tag.get_text(strip=True)
            children.append((file_id, file_name, "application/octet-stream"))
            continue

        folder_match = re.match(
            pattern=r"https://drive\.google\.com/drive/folders/([-\w]{25,})",
            string=href,
        )
        if folder_match:
            child_folder_id = folder_match.group(1)
            child_name = a_tag.get_text(strip=True)
            children.append((child_folder_id, child_name, _GoogleDriveFile.TYPE_FOLDER))
            continue

    return (folder_name, children)


def _download_and_parse_google_drive_link(
    sess: requests.Session,
    folder_id: str,
    quiet: bool = False,
    verify: bool | str = True,
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
