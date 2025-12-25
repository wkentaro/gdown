import collections
import itertools
import json
import os
import os.path as osp
import re
import sys
import warnings
from typing import List
from typing import Union

import bs4
from requests import Session
from playwright.sync_api import sync_playwright

from .download import _get_session
from .download import download
from .parse_url import is_google_drive_url


class _GoogleDriveFile(object):
    TYPE_FOLDER = "application/vnd.google-apps.folder"
    TYPE_FILE = "file"

    def __init__(self, id, name, type, children=None):
        self.id = id
        self.name = name
        self.type = type
        self.children = children if children is not None else []

    def is_folder(self):
        return self.type == self.TYPE_FOLDER


def _download_and_parse_google_drive_link_folder(
    sess: Session,
    url,
    quiet=False,
    remaining_ok=False,
    verify=True,
):
    """Get folder structure of Google Drive folder URL."""
    id_folder = url.split("/")[-1]
    return_code = True
    if is_google_drive_url(url):
        # canonicalize the language into English
        if "?" in url:
            url += "&hl=en"
        else:
            url += "?hl=en"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            proxy={
                "server": (
                    sess.proxies.get("http").replace("http://", "http=")
                ),
                "username": sess.proxies.get("username"),
                "password": sess.proxies.get("password"),
            } if sess.proxies.get("http") else None,
        )
        context = browser.new_context(
            user_agent=sess.headers.get("User-Agent", None),
            ignore_https_errors=not verify,
        )
        page = context.new_page()
        page.goto(url)
        folder_name = ""
        count_rows = 0
        while True:
            table_elm = page.query_selector("tbody.B3Kdce")
            rows = table_elm.query_selector_all("tr.qwPkcb.yjl6dc.O5x1db.Ss7qXc")
            last_elm = rows[-1]
            last_elm.scroll_into_view_if_needed()

            if len(rows) == count_rows:
                folder_name = page.query_selector("div.o-Yc-o-T").inner_text()
                if not quiet:
                    print("Reached the end of the folder", folder_name, id_folder)
                break
            else:
                count_rows = len(rows)
            page.wait_for_timeout(5000)

        current_folder_meta = _GoogleDriveFile(
            id=id_folder,
            name=folder_name,
            type=_GoogleDriveFile.TYPE_FOLDER,
        )
        id_name_type_iter = []
        if len(rows):
            for i in range(len(rows)):
                div_name_type = rows[i].query_selector("div.JxSEve")
                name_att = div_name_type.get_attribute("aria-label")
                elm_id = rows[i].get_attribute("data-id")
                elm_name = rows[i].query_selector("div.i92Sbe.a65Cwf").inner_text()
                if " ".join(name_att.split(" ")[-2:]) == "Shared folder":
                    elm_type = _GoogleDriveFile.TYPE_FOLDER
                else:
                    elm_type = _GoogleDriveFile.TYPE_FILE
                id_name_type_iter.append((elm_id, elm_name, elm_type))
        page.wait_for_timeout(5000)
        browser.close()
    for child_id, child_name, child_type in id_name_type_iter:
        if child_type != _GoogleDriveFile.TYPE_FOLDER:
            if not quiet:
                print(
                    "Processing file",
                    child_id,
                    child_name,
                )
            current_folder_meta.children.append(
                _GoogleDriveFile(
                    id=child_id,
                    name=child_name,
                    type=child_type,
                )
            )
            if not return_code:
                return return_code, None
            continue

        if not quiet:
            print(
                "Retrieving folder",
                child_id,
                child_name,
            )
        return_code, child = _download_and_parse_google_drive_link_folder(
            sess=sess,
            url="https://drive.google.com/drive/folders/" + child_id,
            quiet=quiet,
            remaining_ok=remaining_ok,
        )
        if not return_code:
            return return_code, None
        current_folder_meta.children.append(child)
    return True, current_folder_meta


def _get_directory_structure(gdrive_file, previous_path):
    """Converts a Google Drive folder structure into a local directory list."""

    directory_structure = []
    for file in gdrive_file.children:
        file.name = file.name.replace(osp.sep, "_")
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
    url=None,
    id=None,
    output=None,
    quiet=False,
    proxy=None,
    speed=None,
    use_cookies=True,
    remaining_ok=False,
    verify=True,
    user_agent=None,
    skip_download: bool = False,
    resume=False,
) -> Union[List[str], List[GoogleDriveFileToDownload], None]:
    """Downloads entire folder from URL.

    Parameters
    ----------
    url: str
        URL of the Google Drive folder.
        Must be of the format 'https://drive.google.com/drive/folders/{url}'.
    id: str
        Google Drive's folder ID.
    output: str, optional
        String containing the path of the output folder.
        Defaults to current working directory.
    quiet: bool, optional
        Suppress terminal output.
    proxy: str, optional
        Proxy.
    speed: float, optional
        Download byte size per second (e.g., 256KB/s = 256 * 1024).
    use_cookies: bool, optional
        Flag to use cookies. Default is True.
    verify: bool or string
        Either a bool, in which case it controls whether the server's TLS
        certificate is verified, or a string, in which case it must be a path
        to a CA bundle to use. Default is True.
    user_agent: str, optional
        User-agent to use in the HTTP request.
    skip_download: bool, optional
        If True, return the list of files to download without downloading them.
        Defaults to False.
    resume: bool
        Resume interrupted transfers.
        Completed output files will be skipped.
        Partial tempfiles will be reused, if the transfer is incomplete.
        Default is False.

    Returns
    -------
    files: List[str] or List[GoogleDriveFileToDownload] or None
        If dry_run is False, list of local file paths downloaded or None if failed.
        If dry_run is True, list of GoogleDriveFileToDownload that contains
        id, path, and local_path.

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
        url = "https://drive.google.com/drive/folders/{id}".format(id=id)
    if user_agent is None:
        # We need to use different user agent for folder download c.f., file
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36"  # NOQA: E501

    sess = _get_session(proxy=proxy, use_cookies=use_cookies, user_agent=user_agent)

    if not quiet:
        print("Retrieving folder contents", file=sys.stderr)
    is_success, gdrive_file = _download_and_parse_google_drive_link_folder(
        sess,
        url,
        quiet=quiet,
        remaining_ok=remaining_ok,
        verify=verify,
    )
    if not is_success:
        print("Failed to retrieve folder contents", file=sys.stderr)
        return None

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
            if resume and os.path.isfile(local_path):
                if not quiet:
                    print(
                        f"Skipping already downloaded file {local_path}",
                        file=sys.stderr,
                    )
                files.append(local_path)
                continue

            local_path = download(
                url="https://drive.google.com/uc?id=" + id,
                output=local_path,
                quiet=quiet,
                proxy=proxy,
                speed=speed,
                use_cookies=use_cookies,
                verify=verify,
                resume=resume,
            )
            if local_path is None:
                if not quiet:
                    print("Download ended unsuccessfully", file=sys.stderr)
                return None
            files.append(local_path)
    if not quiet:
        print("Download completed", file=sys.stderr)
    return files
