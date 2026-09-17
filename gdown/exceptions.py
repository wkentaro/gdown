class DownloadError(Exception):
    pass


class FileURLRetrievalError(DownloadError):
    pass


class DownloadCancelled(Exception):
    pass
