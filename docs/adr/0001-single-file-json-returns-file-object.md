# 1. Single-file `--json` returns GoogleDriveFileToDownload, not a string

Date: 2026-05-30

## Status

Accepted

## Context

`--json` resolves what would be downloaded and prints it as a JSON array of
`{url, path}` instead of downloading. It originally worked only for folders,
backed by `download_folder(skip_download=True)`, which returns
`list[GoogleDriveFileToDownload]`.

Extending `--json` to single files (GitHub #461) requires a `skip_download`
mode on `download()`. The open question was what that mode returns. `download()`
normally returns `str | None` (the output path). Two options for the probe
result:

- A bare `str` (the resolved Drive filename).
- The existing `GoogleDriveFileToDownload` namedtuple `(id, path, local_path)`.

A bare `str` is the smaller contract, but it collides with the normal return:
`download(...)` already returns a path string when downloading. The same type
would then mean "where I wrote the file" in one mode and "what I would have
named it" in the other, with nothing at the type level to distinguish them.
Neither a human reader nor a type checker could tell which mode produced a given
value.

`GoogleDriveFileToDownload` is already public and already returned by
`download_folder(skip_download=True)`, so reusing it adds no new public surface.
It also makes the two `--json` branches return the same element type, so the CLI
serializes both through one loop.

## Decision

Under `skip_download=True`, `download()` returns a single
`GoogleDriveFileToDownload`. For a single file there is no folder root, so
`path` and `local_path` are both the bare Drive filename and `id` is the
resolved Drive file id. `--json` forbids `-O`/`--output`, so `local_path` is
never derived from a download destination.

## Consequences

- Probe mode is type-distinct from the normal `str | None` download return, so
  the mode is self-announcing to readers, callers, and type checkers.
- The CLI serializes single-file and folder results through one shared block;
  the single-file scalar is wrapped as a one-element list, so `--json` always
  emits a JSON array.
- This is a forward API commitment: Python callers will rely on
  `download(url, skip_download=True).path`. Changing the single-file probe shape
  later is a breaking change.
- `local_path` carries no folder-root meaning for a single file; it duplicates
  `path`. Callers inspecting `local_path` to learn a destination get only the
  filename, which is acceptable because `--json` writes nothing.
- `download()`'s return type widens to
  `str | BinaryIO | GoogleDriveFileToDownload | None`. As with
  `download_folder`, the flag-dependent return type is not expressed via
  `@overload`.
