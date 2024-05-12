import hashlib
import os
import subprocess
import sys
import tempfile

from gdown.cached_download import _assert_filehash
from gdown.cached_download import _compute_filehash

here = os.path.dirname(os.path.abspath(__file__))


def _test_cli_with_md5(url_or_id, md5, options=None):
    # We can't use NamedTemporaryFile because Windows doesn't allow the subprocess
    # to write the file created by the parent process.
    with tempfile.TemporaryDirectory() as d:
        file_path = os.path.join(d, "file")
        cmd = ["gdown", "--no-cookies", url_or_id, "-O", file_path]
        if options is not None:
            cmd.extend(options)
        subprocess.call(cmd)
        _assert_filehash(path=file_path, hash=f"md5:{md5}")


def _test_cli_with_content(url_or_id, content):
    # We can't use NamedTemporaryFile because Windows doesn't allow the subprocess
    # to write the file created by the parent process.
    with tempfile.TemporaryDirectory() as d:
        file_path = os.path.join(d, "file")
        cmd = ["gdown", "--no-cookies", url_or_id, "-O", file_path]
        subprocess.call(cmd)
        with open(file_path) as f:
            assert f.read() == content


def test_download_from_url_other_than_gdrive():
    url = "https://raw.githubusercontent.com/wkentaro/gdown/3.1.0/gdown/__init__.py"
    md5 = "2a51927dde6b146ce56b4d89ebbb5268"
    _test_cli_with_md5(url_or_id=url, md5=md5)


def test_download_small_file_from_gdrive():
    with open(os.path.join(here, "data/file_ids.csv")) as f:
        file_ids = [file_id.strip() for file_id in f]

    for file_id in file_ids:
        try:
            _test_cli_with_content(url_or_id=file_id, content="spam\n")
            break
        except AssertionError as e:
            print(e, file=sys.stderr)
            continue
    else:
        raise AssertionError(f"Failed to download any of the files: {file_ids}")


def test_download_large_file_from_gdrive():
    with open(os.path.join(here, "data/file_ids_large.csv")) as f:
        file_id_and_md5s = [[x.strip() for x in file_id.split(",")] for file_id in f]

    for file_id, md5 in file_id_and_md5s:
        try:
            _test_cli_with_md5(url_or_id=file_id, md5=md5)
            break
        except AssertionError as e:
            print(e, file=sys.stderr)
            continue
    else:
        file_ids, _ = zip(*file_id_and_md5s)
        raise AssertionError(f"Failed to download any of the files: {file_ids}")


def test_download_and_extract():
    cmd = "gdown --no-cookies https://github.com/wkentaro/gdown/archive/refs/tags/v4.0.0.tar.gz -O - | tar zxvf -"  # noqa: E501
    with tempfile.TemporaryDirectory() as d:
        subprocess.call(cmd, shell=True, cwd=d)
        assert os.path.exists(os.path.join(d, "gdown-4.0.0/gdown/__init__.py"))


def test_download_folder_from_gdrive():
    with open(os.path.join(here, "data/folder_ids.csv")) as f:
        folder_id_and_md5s = [
            [x.strip() for x in folder_id.split(",")] for folder_id in f
        ]

    for folder_id, md5 in folder_id_and_md5s:
        with tempfile.TemporaryDirectory() as d:
            cmd = ["gdown", "--no-cookies", folder_id, "-O", d, "--folder"]
            subprocess.call(cmd)

            md5s_actual = []
            for dirpath, dirnames, filenames in os.walk(d):
                for filename in filenames:
                    md5_actual = _compute_filehash(
                        path=os.path.join(dirpath, filename), algorithm="md5"
                    )[len("md5:") :]
                    md5s_actual.append(md5_actual)

            md5_actual = hashlib.md5(
                ("".join(x + "\n" for x in sorted(md5s_actual))).encode()
            ).hexdigest()
        try:
            assert md5_actual == md5
            break
        except AssertionError as e:
            print(e, file=sys.stderr)
    else:
        file_ids, md5s = zip(*folder_id_and_md5s)
        raise AssertionError(f"Failed to download any of the folders: {file_ids}")


def test_download_a_folder_with_remining_ok_false():
    with tempfile.TemporaryDirectory() as d:
        cmd = [
            "gdown",
            "--no-cookies",
            "https://drive.google.com/drive/folders/1gd3xLkmjT8IckN6WtMbyFZvLR4exRIkn",
            "-O",
            d,
            "--folder",
        ]
    assert subprocess.call(cmd) == 1


# def test_download_docs_from_gdrive():
#     file_id = "1TFYNzuZJTgNGzGmjraZ58ZVOh9_YoKeBnU-opWgXQL4"
#     md5 = "6c17d87d3d01405ac5c9bb65ee2d2fc2"
#     _test_cli_with_md5(url_or_id=file_id, md5=md5, options="--format txt")
#
#
# def test_download_spreadsheets_from_gdrive():
#     file_id = "1h6wQX7ATSJDOSWFEjHPmv_nukJzZD_zZ30Jvy6XNiTE"
#     md5 = "5be20dd8a23afa06365714edc24856f3"
#     _test_cli_with_md5(url_or_id=file_id, md5=md5, options="--format pdf")


def test_download_slides_from_gdrive():
    file_id = "13AhW1Z1GYGaiTpJ0Pr2TTXoQivb6jx-a"
    md5 = "96704c6c40e308a68d3842e83a0136b9"
    _test_cli_with_md5(url_or_id=file_id, md5=md5, options=["--format", "pdf"])


def test_download_a_folder_with_file_content_more_than_the_limit():
    url = "https://drive.google.com/drive/folders/1gd3xLkmjT8IckN6WtMbyFZvLR4exRIkn"

    with tempfile.TemporaryDirectory() as d:
        cmd = ["gdown", "--no-cookies", url, "-O", d, "--folder", "--remaining-ok"]
        subprocess.check_call(cmd)

        filenames = sorted(os.listdir(d))
        for i in range(50):
            assert filenames[i] == f"file_{i:02d}.txt"
