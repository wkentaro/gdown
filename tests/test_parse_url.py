import pytest

from gdown.parse_url import parse_url

from .conftest import GITHUB_RELEASE_URL


def test_parse_url_non_gdrive() -> None:
    assert parse_url(GITHUB_RELEASE_URL) == (None, False)


def test_parse_url() -> None:
    file_id = "0B_NiLAzvehC9R2stRmQyM3ZiVjQ"

    # list of (url, expected, check_warn)
    urls = [
        (
            f"https://drive.google.com/open?id={file_id}",
            (file_id, False),
            True,
        ),
        (
            f"https://drive.google.com/uc?id={file_id}",
            (file_id, True),
            False,
        ),
        (
            f"https://drive.google.com/file/d/{file_id}/view?usp=sharing",
            (file_id, False),
            True,
        ),
        (
            "https://drive.google.com/a/jsk.imi.i.u-tokyo.ac.jp/uc?id={}&export=download".format(  # NOQA
                file_id
            ),
            (file_id, True),
            False,
        ),
    ]

    for url, expected, check_warn in urls:
        if check_warn:
            with pytest.warns(UserWarning):
                assert parse_url(url) == expected
        else:
            assert parse_url(url) == expected
