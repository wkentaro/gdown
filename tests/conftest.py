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
