import os
import tempfile

from gdown.download import download


def test_download():
    with tempfile.TemporaryDirectory() as d:
        file_path = os.path.join(d, "file")
        url = "https://raw.githubusercontent.com/wkentaro/gdown/3.1.0/gdown/__init__.py"  # NOQA
        # Usage before https://github.com/wkentaro/gdown/pull/32
        assert download(url=url, output=file_path, quiet=False) == file_path
