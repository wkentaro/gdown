import os
import tempfile

import gdown


def _cached_download(**kwargs):
    url = "https://drive.google.com/uc?id=0B9P1L--7Wd2vU3VUVlFnbTgtS2c"
    path = tempfile.mktemp()
    for _ in range(2):
        gdown.cached_download(url=url, path=path, **kwargs)
    os.remove(path)


def test_cached_download_md5():
    _cached_download(hash="md5:cb31a703b96c1ab2f80d164e9676fe7d")


def test_cached_download_sha1():
    _cached_download(hash="sha1:69a5a1000f98237efea9231c8a39d05edf013494")


def test_cached_download_sha256():
    _cached_download(
        hash="sha256:284e3029cce3ae5ee0b05866100e300046359f53ae4c77fe6b34c05aa7a72cee"
    )
