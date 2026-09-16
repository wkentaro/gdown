# Progress Callback Cancellation

gdown will not add a return-value protocol to the `progress` callback, or a
library-owned `DownloadCancelledError`, for stopping a download in flight.

## Why this is out of scope

Cancellation already exists. The `progress` callback is called after every
chunk, and the `download()` docstring states that raising any exception from it
aborts the download. On that path the temporary file, the progress bar, and the
HTTP response are closed, the `.part` file is left in place for `resume`, a
caller-provided stream stays open, and the output path is never written. Three
tests cover it.

A caller that wants a named cancellation can define its own exception, raise it
from the callback, and catch it around the call. Because that exception is not a
`DownloadError`, neither `download_folder()` nor `cached_download()` swallows
it, so the caller's request to stop is never overridden. `cached_download()`
also removes its staging directory on the way out, as it does for any
exception.

Letting the callback return `False` instead adds a second cancellation
mechanism that must stay in sync with the first, a new public exception class,
and a wider callback type on every public signature that forwards `progress`.
None of it lets a caller do anything the exception path cannot.

The argument that a raise "reads as a failure rather than a request" is about
the caller's code, and the caller controls the name of the exception it raises.

## Prior requests

- [PR #508](https://github.com/wkentaro/gdown/pull/508) - Timeout, cancellation,
  and streaming hash for downloads
- [PR #511](https://github.com/wkentaro/gdown/pull/511) - Let the progress
  callback cancel a download
