class DownloadError(Exception):
    pass


class FileURLRetrievalError(DownloadError):
    pass


class HashMismatchError(DownloadError, AssertionError):
    pass
