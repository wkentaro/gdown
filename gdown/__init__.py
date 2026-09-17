from importlib.metadata import version as _get_distribution_version

from . import exceptions
from . import parse_url
from .cached_download import cached_download
from .download import download
from .download_folder import download_folder
from .exceptions import DownloadCancelled
from .exceptions import DownloadError
from .exceptions import FileURLRetrievalError
from .extractall import extractall

__all__ = [
    "DownloadCancelled",
    "DownloadError",
    "FileURLRetrievalError",
    "cached_download",
    "download",
    "download_folder",
    "exceptions",
    "extractall",
    "parse_url",
]
__version__ = _get_distribution_version("gdown")
