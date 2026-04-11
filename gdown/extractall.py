import os.path as osp
import tarfile
import zipfile


def extractall(path: str, to: str | None = None) -> list[str]:
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
        with zipfile.ZipFile(path, "r") as f:
            f.extractall(path=to)
            names = f.namelist()
        return [osp.join(to, name) for name in names]

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

    with tarfile.open(name=path, mode=tar_mode) as f:
        f.extractall(path=to)
        names = [m.path for m in f.getmembers()]

    return [osp.join(to, name) for name in names]
