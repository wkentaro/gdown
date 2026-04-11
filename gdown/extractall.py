import os
import os.path as osp
import sys
import tarfile
import zipfile
from typing import Literal

_TarReadMode = Literal["r", "r:gz", "r:bz2"]


def _is_within_directory(directory: str, target: str) -> bool:
    abs_directory = osp.realpath(directory)
    abs_target = osp.realpath(target)
    return abs_target.startswith(abs_directory + os.sep) or abs_target == abs_directory


def extractall(path: str, to: str | None = None) -> list[str]:
    """Extract archive file.

    Parameters
    ----------
    path:
        Path of archive file to be extracted.
    to:
        Directory to which the archive file will be extracted.
        If None, it will be set to the parent directory of the archive file.

    Raises
    ------
    ValueError
        If the archive format is unsupported, or if an archive member would
        extract outside the target directory.
    """
    if to is None:
        to = osp.dirname(path)

    if path.endswith(".zip"):
        return _extractall_zip(path=path, to=to)

    if path.endswith(".tar"):
        tar_mode = "r"
    elif path.endswith(".tar.gz") or path.endswith(".tgz"):
        tar_mode = "r:gz"
    elif path.endswith(".tar.bz2") or path.endswith(".tbz"):
        tar_mode = "r:bz2"
    else:
        raise ValueError(
            f"Could not extract '{path}' as no appropriate extractor is found"
        )

    return _extractall_tar(path=path, to=to, tar_mode=tar_mode)


def _extractall_zip(path: str, to: str) -> list[str]:
    with zipfile.ZipFile(path, "r") as f:
        names = f.namelist()
        for member in names:
            member_path = osp.join(to, member)
            if not _is_within_directory(directory=to, target=member_path):
                raise ValueError(
                    f"Archive member '{member}' would extract outside "
                    f"target directory: {to}"
                )
        f.extractall(path=to)
    return [osp.join(to, name) for name in names]


def _extractall_tar(path: str, to: str, tar_mode: _TarReadMode) -> list[str]:
    with tarfile.open(name=path, mode=tar_mode) as f:
        if sys.version_info >= (3, 12):
            f.extractall(path=to, filter="data")
        else:
            for member in f.getmembers():
                if member.issym() or member.islnk():
                    raise ValueError(
                        f"Archive member '{member.name}' is a link, "
                        f"which is not allowed for security reasons"
                    )
                if member.ischr() or member.isblk() or member.isfifo():
                    raise ValueError(
                        f"Archive member '{member.name}' is a special file, "
                        f"which is not allowed for security reasons"
                    )
                member_path = osp.join(to, member.name)
                if not _is_within_directory(directory=to, target=member_path):
                    raise ValueError(
                        f"Archive member '{member.name}' would extract outside "
                        f"target directory: {to}"
                    )
            f.extractall(path=to)
        names = [m.path for m in f.getmembers()]

    return [osp.join(to, name) for name in names]
