from unittest.mock import MagicMock

import pytest

from gdown.download import _get_filename_from_response
from gdown.download import _sanitize_filename


def _make_response(content_disposition: str) -> MagicMock:
    response = MagicMock()
    response.headers = {"Content-Disposition": content_disposition}
    return response


@pytest.mark.parametrize(
    "content_disposition, expected",
    [
        ("filename*=UTF-8''report.pdf", "report.pdf"),
        ("filename*=UTF-8''Budget%2F2024.pdf", "Budget_2024.pdf"),
        ("filename*=UTF-8''path%5Cto%5Cfile.pdf", "path_to_file.pdf"),
        ('attachment; filename="report.pdf"', "report.pdf"),
        ('attachment; filename="Budget/2024.pdf"', "Budget_2024.pdf"),
        ('attachment; filename="path\\to\\file.pdf"', "path_to_file.pdf"),
    ],
    ids=[
        "utf8-normal",
        "utf8-forward-slash",
        "utf8-backslash",
        "attachment-normal",
        "attachment-forward-slash",
        "attachment-backslash",
    ],
)
def test_get_filename_from_response(content_disposition: str, expected: str) -> None:
    response = _make_response(content_disposition=content_disposition)
    assert _get_filename_from_response(response=response) == expected


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("report.pdf", "report.pdf"),
        ("Budget/2024.pdf", "Budget_2024.pdf"),
        ("path\\to\\file.pdf", "path_to_file.pdf"),
        ("a/b\\c.pdf", "a_b_c.pdf"),
        (" report.pdf ", "report.pdf"),
        ("  folder name  ", "folder name"),
        ("..", "_"),
        (".", "_"),
        ("", "_"),
        ("  ", "_"),
        ("file\x00name.txt", "filename.txt"),
        ("../../../etc/passwd", ".._.._.._etc_passwd"),
    ],
    ids=[
        "no-op",
        "forward-slash",
        "backslash",
        "mixed",
        "trailing-spaces",
        "both-spaces",
        "dot-dot",
        "dot",
        "empty",
        "whitespace-only",
        "null-byte",
        "path-traversal",
    ],
)
def test_sanitize_filename(filename: str, expected: str) -> None:
    assert _sanitize_filename(filename=filename) == expected
