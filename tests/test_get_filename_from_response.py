import sys
from unittest.mock import MagicMock

import pytest

from gdown.download import _get_filename_from_response
from gdown.download import _sanitize_filename


def _make_response(*, content_disposition: str) -> MagicMock:
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
def test_get_filename_from_response(*, content_disposition: str, expected: str) -> None:
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
def test_sanitize_filename(*, filename: str, expected: str) -> None:
    assert _sanitize_filename(filename=filename) == expected


@pytest.mark.parametrize("platform", ["win32", "linux", "darwin"])
@pytest.mark.parametrize(
    "filename, windows_name",
    [
        (":RE PART 1", "_RE PART 1"),
        ('a<>:"|?*b.txt', "a_______b.txt"),
        *[(f"a{chr(code)}b.txt", "a_b.txt") for code in range(1, 32)],
        ("trailing. .", "trailing"),
        ("...", "_"),
        ("CON", "_CON"),
        ("con.txt", "_con.txt"),
        ("PRN", "_PRN"),
        ("AUX.txt", "_AUX.txt"),
        ("NUL.tar.gz", "_NUL.tar.gz"),
        ("NUL .txt", "_NUL .txt"),
        ("COM1", "_COM1"),
        ("com9.txt", "_com9.txt"),
        ("LPT1", "_LPT1"),
        ("lpt9.txt", "_lpt9.txt"),
        ("COM\u00b9.txt", "_COM\u00b9.txt"),
        ("LPT\u00b2", "_LPT\u00b2"),
        ("COM\u00b3", "_COM\u00b3"),
        ("CONIN$", "_CONIN$"),
        ("CONOUT$", "_CONOUT$"),
        ("COM0.txt", "COM0.txt"),
        ("COM10.txt", "COM10.txt"),
        ("console.txt", "console.txt"),
        ("\u8cc7\u6599.txt", "\u8cc7\u6599.txt"),
    ],
)
def test_sanitize_filename_platform_rules(
    *, monkeypatch: pytest.MonkeyPatch, platform: str, filename: str, windows_name: str
) -> None:
    monkeypatch.setattr(sys, "platform", platform)
    assert _sanitize_filename(filename=filename) == (
        windows_name if platform == "win32" else filename
    )
