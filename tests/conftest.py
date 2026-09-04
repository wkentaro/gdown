import http.cookiejar
import unittest.mock
from typing import Final

GITHUB_RELEASE_URL: Final = (
    "https://github.com/wkentaro/gdown/archive/refs/tags/v4.0.0.tar.gz"
)


def build_response(
    *, headers: dict[str, str], chunks: list[bytes]
) -> unittest.mock.Mock:
    response = unittest.mock.Mock()
    response.status_code = 200
    response.headers = {"Content-Type": "application/octet-stream", **headers}
    response.iter_content.return_value = chunks
    response.url = "https://example.com/file"
    return response


def build_google_cookie(
    *,
    name: str,
    value: str = "secret",
    expires: int | None = None,
    domain: str = ".google.com",
) -> http.cookiejar.Cookie:
    return http.cookiejar.Cookie(
        version=0,
        name=name,
        value=value,
        port=None,
        port_specified=False,
        domain=domain,
        domain_specified=True,
        domain_initial_dot=domain.startswith("."),
        path="/",
        path_specified=True,
        secure=True,
        expires=expires,
        discard=expires is None,
        comment=None,
        comment_url=None,
        rest={},
    )
