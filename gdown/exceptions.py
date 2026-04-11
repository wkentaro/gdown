class DownloadError(Exception):
    pass


class FileURLRetrievalError(DownloadError):
    pass


class FolderContentsMaximumLimitError(DownloadError):
    pass
