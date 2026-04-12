from __future__ import annotations

import hashlib
import os
import os.path as osp
import shutil
import sys
import tempfile
from collections.abc import Callable
from typing import TypedDict

if sys.version_info >= (3, 12):
    from typing import Unpack
else:
    from typing_extensions import Unpack

import filelock

from .download import download


class _DownloadKwargs(TypedDict, total=False):
    proxy: str | None
    speed: float | None
    use_cookies: bool
    verify: bool | str
    id: str | None
    resume: bool
    format: str | None
    user_agent: str | None
    progress: Callable[[int, int | None], None] | None


cache_root = osp.join(osp.expanduser("~"), ".cache/gdown")
if not osp.exists(cache_root):
    try:
        os.makedirs(cache_root)
    except OSError:
        pass


def cached_download(
    url: str | None = None,
    path: str | None = None,
    quiet: bool = False,
    postprocess: Callable[[str], object] | None = None,
    hash: str | None = None,
    **kwargs: Unpack[_DownloadKwargs],
) -> str:
    """Cached download from URL.

    Parameters
    ----------
    url:
        URL. Google Drive URL is also supported.
    path:
        Output filename. Default is basename of URL.
    quiet:
        Suppress terminal output. Default is False.
    postprocess:
        Function called with filename as postprocess.
    hash:
        Hash value of file in the format of {algorithm}:{hash_value}
        such as sha256:abcdef.... Supported algorithms: md5, sha1, sha256, sha512.
    kwargs:
        Keyword arguments to be passed to `download`.

    Returns
    -------
    path:
        Output filename.

    Raises
    ------
    ValueError
        If url is not specified when path is not specified.
    DownloadError
        If the download fails.
    """
    if path is None:
        if url is None:
            raise ValueError("url must be specified when path is not specified")
        path = (
            url.replace("/", "-SLASH-")
            .replace(":", "-COLON-")
            .replace("=", "-EQUAL-")
            .replace("?", "-QUESTION-")
        )
        path = osp.join(cache_root, path)

    # check existence
    if osp.exists(path) and not hash:
        if not quiet:
            print(f"File exists: {path}", file=sys.stderr)
        return path
    elif osp.exists(path) and hash:
        try:
            _assert_filehash(path=path, hash=hash, quiet=quiet)
            return path
        except AssertionError as e:
            print(e, file=sys.stderr)

    # download
    lock_path = osp.join(cache_root, "_dl_lock")
    try:
        os.makedirs(osp.dirname(path))
    except OSError:
        pass
    temp_root = tempfile.mkdtemp(dir=cache_root)
    try:
        temp_path = osp.join(temp_root, "dl")

        log_message_hash = f"Hash: {hash}\n" if hash else ""
        download(
            url=url,
            output=temp_path,
            quiet=quiet,
            log_messages={
                "start": f"Cached downloading...\n{log_message_hash}",
                "output": f"To: {path}\n",
            },
            **kwargs,
        )
        if hash:
            _assert_filehash(path=temp_path, hash=hash, quiet=quiet)
        with filelock.FileLock(lock_path):
            shutil.move(temp_path, path)
    except Exception:
        shutil.rmtree(temp_root)
        raise

    # postprocess
    if postprocess is not None:
        postprocess(path)

    return path


def _compute_filehash(path: str, algorithm: str) -> str:
    BLOCKSIZE = 65536

    if algorithm not in hashlib.algorithms_guaranteed:
        raise ValueError(
            f"Unsupported hash algorithm: {algorithm}. "
            f"Supported algorithms: {hashlib.algorithms_guaranteed}"
        )

    algorithm_instance = getattr(hashlib, algorithm)()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(BLOCKSIZE), b""):
            algorithm_instance.update(block)
    return f"{algorithm}:{algorithm_instance.hexdigest()}"


def _assert_filehash(path: str, hash: str, quiet: bool = False) -> None:
    if ":" not in hash:
        raise ValueError(
            f"Invalid hash: {hash}. "
            "Hash must be in the format of {algorithm}:{hash_value}."
        )
    algorithm = hash.split(":")[0]

    hash_actual = _compute_filehash(path=path, algorithm=algorithm)

    if hash_actual != hash:
        raise AssertionError(
            f"File hash doesn't match:\nactual: {hash_actual}\nexpected: {hash}"
        )
