# -*- encoding: utf-8 -*-

from __future__ import print_function

import itertools
import json
import os
import os.path as osp
import re
import sys
import textwrap

import bs4

from .download import _get_session
from .download import download
from .download import indent

MAX_NUMBER_FILES = 50


class _GoogleDriveFile(object):
    TYPE_FOLDER = "application/vnd.google-apps.folder"

    def __init__(self, id, name, type, children=None):
        self.id = id
        self.name = name
        self.type = type
        self.children = children if children is not None else []

    def is_folder(self):
        return self.type == self.TYPE_FOLDER


def _parse_google_drive_file(folder, content):
    """Extracts information about the current page file and its children."""

    folder_soup = bs4.BeautifulSoup(content, features="html.parser")

    # finds the script tag with window['_DRIVE_ivd']
    encoded_data = None
    for script in folder_soup.select("script"):
        inner_html = script.decode_contents()

        if "_DRIVE_ivd" in inner_html:
            # first js string is _DRIVE_ivd, the second one is the encoded arr
            regex_iter = re.compile(r"'((?:[^'\\]|\\.)*)'").finditer(
                inner_html
            )
            # get the second elem in the iter
            try:
                encoded_data = next(
                    itertools.islice(regex_iter, 1, None)
                ).group(1)
            except StopIteration:
                raise RuntimeError(
                    "Couldn't find the folder encoded JS string"
                )
            break

    if encoded_data is None:
        raise RuntimeError(
            "Cannot retrieve the folder information from the link. "
            "You may need to change the permission to "
            "'Anyone with the link'."
        )

    # decodes the array and evaluates it as a python array
    decoded = encoded_data.encode("utf-8").decode("unicode_escape")
    folder_arr = json.loads(decoded)

    folder_contents = [] if folder_arr[0] is None else folder_arr[0]

    sep = " - "  # unicode dash
    splitted = folder_soup.title.contents[0].split(sep)
    if len(splitted) >= 2:
        name = sep.join(splitted[:-1])
    else:
        raise RuntimeError(
            "file/folder name cannot be extracted from: {}".format(
                folder_soup.title.contents[0]
            )
        )

    gdrive_file = _GoogleDriveFile(
        id=folder.split("/")[-1],
        name=name,
        type=_GoogleDriveFile.TYPE_FOLDER,
    )

    id_name_type_iter = [
        (e[0], e[2].encode("raw_unicode_escape").decode("utf-8"), e[3])
        for e in folder_contents
    ]

    return gdrive_file, id_name_type_iter


def _download_and_parse_google_drive_link(
    sess,
    folder,
    quiet=False,
    remaining_ok=False,
):
    """Get folder structure of Google Drive folder URL."""

    return_code = True

    # canonicalize the language into English
    if "?" in folder:
        folder += "&hl=en"
    else:
        folder += "?hl=en"

    folder_page = sess.get(folder)

    if folder_page.status_code != 200:
        return False, None

    gdrive_file, id_name_type_iter = _parse_google_drive_file(
        folder,
        folder_page.text,
    )

    for child_id, child_name, child_type in id_name_type_iter:
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
            if not return_code:
                return return_code, None
            continue

        if not quiet:
            print(
                "Retrieving folder",
                child_id,
                child_name,
            )
        return_code, child = _download_and_parse_google_drive_link(
            sess,
            "https://drive.google.com/drive/folders/" + child_id,
            quiet=quiet,
            remaining_ok=remaining_ok,
        )
        if not return_code:
            return return_code, None
        gdrive_file.children.append(child)
    has_at_least_max_files = len(gdrive_file.children) == MAX_NUMBER_FILES
    if not remaining_ok and has_at_least_max_files:
        err_msg = " ".join(
            [
                "The gdrive folder with url: {url}".format(url=folder),
                "has more than {max} files,".format(max=MAX_NUMBER_FILES),
                "gdrive can't download more than this limit,",
                "if you are ok with this,",
                "please run again with --remaining-ok flag.",
            ]
        )
        raise RuntimeError(err_msg)
    return return_code, gdrive_file


def _get_directory_structure(gdrive_file, previous_path):
    """Converts a Google Drive folder structure into a local directory list."""

    directory_structure = []
    for file in gdrive_file.children:
        file.name = file.name.replace(osp.sep, "_")
        if file.is_folder():
            directory_structure.append(
                (None, osp.join(previous_path, file.name))
            )
            for i in _get_directory_structure(
                file, osp.join(previous_path, file.name)
            ):
                directory_structure.append(i)
        elif not file.children:
            directory_structure.append(
                (file.id, osp.join(previous_path, file.name))
            )
    return directory_structure


def download_folder(
    url=None,
    id=None,
    output=None,
    quiet=False,
    proxy=None,
    speed=None,
    use_cookies=True,
    remaining_ok=False,
):
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

    Returns
    -------
    filenames: list of str
        List of files downloaded, or None if failed.

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

    sess = _get_session(use_cookies=use_cookies)

    if not quiet:
        print("Retrieving folder list", file=sys.stderr)
    try:
        return_code, gdrive_file = _download_and_parse_google_drive_link(
            sess,
            url,
            quiet=quiet,
            remaining_ok=remaining_ok,
        )
    except RuntimeError as e:
        print("Failed to retrieve folder contents:", file=sys.stderr)
        error = "\n".join(textwrap.wrap(str(e)))
        error = indent(error, "\t")
        print("\n", error, "\n", file=sys.stderr)
        return

    if not return_code:
        return return_code
    if not quiet:
        print("Retrieving folder list completed", file=sys.stderr)
        print("Building directory structure", file=sys.stderr)
    if output is None:
        output = os.getcwd() + osp.sep
    if output.endswith(osp.sep):
        root_folder = osp.join(output, gdrive_file.name)
    else:
        root_folder = output
    directory_structure = _get_directory_structure(gdrive_file, root_folder)
    if not osp.exists(root_folder):
        os.makedirs(root_folder)

    if not quiet:
        print("Building directory structure completed")
    filenames = []
    for file_id, file_path in directory_structure:
        if file_id is None:  # folder
            if not osp.exists(file_path):
                os.makedirs(file_path)
            continue

        filename = download(
            "https://drive.google.com/uc?id=" + file_id,
            output=file_path,
            quiet=quiet,
            proxy=proxy,
            speed=speed,
            use_cookies=use_cookies,
        )

        if filename is None:
            if not quiet:
                print("Download ended unsuccessfully", file=sys.stderr)
            return
        filenames.append(filename)
    if not quiet:
        print("Download completed", file=sys.stderr)
    return filenames
