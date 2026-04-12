import os
import os.path as osp
import sys
import tarfile
import zipfile


def _is_within_directory(directory, target):
    abs_directory = osp.realpath(directory)
    abs_target = osp.realpath(target)
    return abs_target.startswith(abs_directory + os.sep) or abs_target == abs_directory


def extractall(path, to=None):
    """Extract archive file.

    Parameters
    ----------
    path: str
        Path of archive file to be extracted.
    to: str, optional
        Directory to which the archive file will be extracted.
        If None, it will be set to the parent directory of the archive file.
    """
    if to is None:
        to = osp.dirname(path)

    if path.endswith(".zip"):
        return _extractall_zip(path, to)

    if path.endswith(".tar"):
        tar_mode = "r"
    elif path.endswith(".tar.gz") or path.endswith(".tgz"):
        tar_mode = "r:gz"
    elif path.endswith(".tar.bz2") or path.endswith(".tbz"):
        tar_mode = "r:bz2"
    else:
        raise ValueError(
            "Could not extract '%s' as no appropriate extractor is found" % path
        )

    return _extractall_tar(path, to, tar_mode)


def _extractall_zip(path, to):
    with zipfile.ZipFile(path, "r") as f:
        names = f.namelist()
        for member in names:
            member_path = osp.join(to, member)
            if not _is_within_directory(to, member_path):
                raise ValueError(
                    "Archive member '%s' would extract outside "
                    "target directory: %s" % (member, to)
                )
        f.extractall(path=to)
    return [osp.join(to, name) for name in names]


def _extractall_tar(path, to, tar_mode):
    with tarfile.open(path, tar_mode) as f:
        members = f.getmembers()
        if sys.version_info >= (3, 12):
            f.extractall(path=to, filter="data")
        else:
            for member in members:
                if member.issym() or member.islnk():
                    raise ValueError(
                        "Archive member '%s' is a link, "
                        "which is not allowed for security reasons"
                        % member.name
                    )
                if member.ischr() or member.isblk() or member.isfifo():
                    raise ValueError(
                        "Archive member '%s' is a special file, "
                        "which is not allowed for security reasons"
                        % member.name
                    )
                member_path = osp.join(to, member.name)
                if not _is_within_directory(to, member_path):
                    raise ValueError(
                        "Archive member '%s' would extract outside "
                        "target directory: %s" % (member.name, to)
                    )
            f.extractall(path=to)

    return [osp.join(to, m.path) for m in members]
