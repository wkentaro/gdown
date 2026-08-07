# Explicit Auto-Detection Flag

gdown will not add an opt-in `--auto` flag to choose between file and folder
downloads.

## Why this is out of scope

A Google Drive folder URL is unambiguous. The CLI should detect it and use the
folder downloader by default. Requiring an additional flag would preserve the
same bad default that existed before `--fuzzy` was removed: gdown would know
the useful interpretation of a URL but require the user to request it.

Bare Drive IDs are different because they do not identify their resource type.
They continue to require `--folder` for folder downloads. Trying file mode and
then treating `FileURLRetrievalError` as a folder signal would make unrelated
file retrieval failures trigger a different download mode.

Automatic routing for known folder URLs is tracked in
[issue #466](https://github.com/wkentaro/gdown/issues/466). The default URL
handling follows the precedent from
[PR #455](https://github.com/wkentaro/gdown/pull/455), which removed `--fuzzy`
and made useful Google Drive URL detection unconditional.

## Prior requests

- [PR #479](https://github.com/wkentaro/gdown/pull/479) - Add `--auto` to detect
  file and folder downloads
