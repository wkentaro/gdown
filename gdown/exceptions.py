class DownloadError(Exception):
    pass


class FileURLRetrievalError(DownloadError):
    pass


# Not a DownloadError: a folder download swallows those to keep going with the
# next file, and a caller that asked to stop must not be overridden that way.
class DownloadCancelledError(Exception):
    pass
