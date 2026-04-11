import importlib.metadata

from . import exceptions
from .cached_download import cached_download
from .download import download
from .download_folder import download_folder
from .exceptions import DownloadError
from .exceptions import FileURLRetrievalError
from .extractall import extractall

__version__ = importlib.metadata.version("gdown")
