import io
import os
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Literal

import pytest

from gdown.extractall import extractall


@pytest.fixture
def _tmp_extract_dir(tmp_path: Path) -> str:
    d = tmp_path / "extract"
    d.mkdir()
    return str(d)


def test_zip_normal(tmp_path: Path, _tmp_extract_dir: str) -> None:
    zip_path = str(tmp_path / "normal.zip")
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("hello.txt", "hello world")
        zf.writestr("subdir/nested.txt", "nested content")

    result = extractall(path=zip_path, to=_tmp_extract_dir)

    assert os.path.exists(os.path.join(_tmp_extract_dir, "hello.txt"))
    assert os.path.exists(os.path.join(_tmp_extract_dir, "subdir", "nested.txt"))
    assert len(result) == 2


def test_tar_normal(tmp_path: Path, _tmp_extract_dir: str) -> None:
    tar_path = str(tmp_path / "normal.tar")
    with tarfile.open(name=tar_path, mode="w") as tf:
        data = b"hello world"
        info = tarfile.TarInfo(name="hello.txt")
        info.size = len(data)
        tf.addfile(tarinfo=info, fileobj=io.BytesIO(data))

    result = extractall(path=tar_path, to=_tmp_extract_dir)

    assert os.path.exists(os.path.join(_tmp_extract_dir, "hello.txt"))
    assert len(result) == 1


def test_zip_path_traversal(tmp_path: Path, _tmp_extract_dir: str) -> None:
    zip_path = str(tmp_path / "evil.zip")
    with zipfile.ZipFile(zip_path, "w") as zf:
        info = zipfile.ZipInfo(filename="../evil.txt")
        zf.writestr(info, "malicious content")

    with pytest.raises(ValueError, match="would extract outside target directory"):
        extractall(path=zip_path, to=_tmp_extract_dir)

    evil_path = os.path.join(_tmp_extract_dir, "..", "evil.txt")
    assert not os.path.exists(evil_path)


def test_zip_absolute_path(tmp_path: Path, _tmp_extract_dir: str) -> None:
    zip_path = str(tmp_path / "evil.zip")
    with zipfile.ZipFile(zip_path, "w") as zf:
        info = zipfile.ZipInfo(filename="/tmp/evil.txt")
        zf.writestr(info, "malicious content")

    with pytest.raises(ValueError, match="would extract outside target directory"):
        extractall(path=zip_path, to=_tmp_extract_dir)


def test_tar_absolute_path(tmp_path: Path, _tmp_extract_dir: str) -> None:
    evil_path = str(tmp_path / "outside" / "evil.txt")
    tar_path = str(tmp_path / "evil.tar")
    with tarfile.open(name=tar_path, mode="w") as tf:
        data = b"malicious content"
        info = tarfile.TarInfo(name=evil_path)
        info.size = len(data)
        tf.addfile(tarinfo=info, fileobj=io.BytesIO(data))

    # Python 3.10-3.11: manual _is_within_directory check raises ValueError.
    # Python 3.12+ Unix: data filter strips the leading '/' and extracts safely.
    # Python 3.12+ Windows: data filter raises AbsolutePathError (TarError)
    #   because drive-letter paths (C:\...) remain absolute after stripping.
    try:
        extractall(path=tar_path, to=_tmp_extract_dir)
    except (ValueError, tarfile.TarError):
        pass

    assert not os.path.exists(evil_path)


def test_tar_path_traversal(tmp_path: Path, _tmp_extract_dir: str) -> None:
    tar_path = str(tmp_path / "evil.tar")
    with tarfile.open(name=tar_path, mode="w") as tf:
        data = b"malicious content"
        info = tarfile.TarInfo(name="../evil.txt")
        info.size = len(data)
        tf.addfile(tarinfo=info, fileobj=io.BytesIO(data))

    if sys.version_info >= (3, 12):
        with pytest.raises(tarfile.FilterError):
            extractall(path=tar_path, to=_tmp_extract_dir)
    else:
        with pytest.raises(ValueError, match="would extract outside target directory"):
            extractall(path=tar_path, to=_tmp_extract_dir)

    evil_path = os.path.join(_tmp_extract_dir, "..", "evil.txt")
    assert not os.path.exists(evil_path)


def test_tar_symlink_rejected(tmp_path: Path, _tmp_extract_dir: str) -> None:
    tar_path = str(tmp_path / "symlink.tar")
    with tarfile.open(name=tar_path, mode="w") as tf:
        info = tarfile.TarInfo(name="evil_link")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        tf.addfile(tarinfo=info)

    if sys.version_info >= (3, 12):
        with pytest.raises(tarfile.FilterError):
            extractall(path=tar_path, to=_tmp_extract_dir)
    else:
        with pytest.raises(ValueError, match="is a link"):
            extractall(path=tar_path, to=_tmp_extract_dir)


def test_tar_hardlink_rejected(tmp_path: Path, _tmp_extract_dir: str) -> None:
    tar_path = str(tmp_path / "hardlink.tar")
    with tarfile.open(name=tar_path, mode="w") as tf:
        info = tarfile.TarInfo(name="evil_link")
        info.type = tarfile.LNKTYPE
        info.linkname = "/etc/passwd"
        tf.addfile(tarinfo=info)

    if sys.version_info >= (3, 12):
        with pytest.raises(tarfile.FilterError):
            extractall(path=tar_path, to=_tmp_extract_dir)
    else:
        with pytest.raises(ValueError, match="is a link"):
            extractall(path=tar_path, to=_tmp_extract_dir)


def test_tar_special_file_rejected(tmp_path: Path, _tmp_extract_dir: str) -> None:
    tar_path = str(tmp_path / "fifo.tar")
    with tarfile.open(name=tar_path, mode="w") as tf:
        info = tarfile.TarInfo(name="evil_fifo")
        info.type = tarfile.FIFOTYPE
        tf.addfile(tarinfo=info)

    if sys.version_info >= (3, 12):
        with pytest.raises(tarfile.FilterError):
            extractall(path=tar_path, to=_tmp_extract_dir)
    else:
        with pytest.raises(ValueError, match="is a special file"):
            extractall(path=tar_path, to=_tmp_extract_dir)


@pytest.mark.parametrize(
    "suffix, write_mode",
    [
        (".tar.gz", "w:gz"),
        (".tgz", "w:gz"),
        (".tar.bz2", "w:bz2"),
        (".tbz", "w:bz2"),
    ],
)
def test_tar_compressed_normal(
    suffix: str,
    write_mode: Literal["w:gz", "w:bz2"],
    tmp_path: Path,
    _tmp_extract_dir: str,
) -> None:
    tar_path = str(tmp_path / f"normal{suffix}")
    with tarfile.open(name=tar_path, mode=write_mode) as tf:
        data = b"hello world"
        info = tarfile.TarInfo(name="hello.txt")
        info.size = len(data)
        tf.addfile(tarinfo=info, fileobj=io.BytesIO(data))

    result = extractall(path=tar_path, to=_tmp_extract_dir)

    assert os.path.exists(os.path.join(_tmp_extract_dir, "hello.txt"))
    assert len(result) == 1


def test_unsupported_format(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no appropriate extractor"):
        extractall(path=str(tmp_path / "archive.rar"))


def test_to_none_defaults_to_archive_parent(tmp_path: Path) -> None:
    zip_path = str(tmp_path / "a.zip")
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("hello.txt", "hello world")

    result = extractall(path=zip_path)

    assert os.path.exists(os.path.join(str(tmp_path), "hello.txt"))
    assert result == [os.path.join(str(tmp_path), "hello.txt")]
