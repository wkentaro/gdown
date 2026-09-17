# Native download cancellation

We will add an optional cancellation event to single-file and cached downloads.
Progress callbacks cannot interrupt a read while the server withholds headers
or body bytes, so cancellation must work independently of the network timeout.
The downloader will own transport interruption and cleanup; exposing responses
would instead make each caller manage changing sockets across redirects and
retries. Applications remain responsible for deciding when to cancel.

Cancellation will raise `DownloadCancelled`, directly derived from `Exception`
and separate from `DownloadError`, without retrying. The name describes an
intentional outcome; [PEP 8](https://peps.python.org/pep-0008/#programming-recommendations)
permits signaling exceptions without an `Error` suffix. Ordinary exception
handlers can catch it, without treating it as a download failure.

This revises the earlier rejection of a library-owned cancellation exception:
interrupting stalled reads adds a capability that callback exceptions lack.
Returning a cancellation value from the progress callback stays rejected
([PR #511](https://github.com/wkentaro/gdown/pull/511)): it would be a second
mechanism that stops nothing the event or a raised exception cannot.
