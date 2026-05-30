# gdown

Command-line tool and Python library for downloading files and folders from Google Drive, where direct URL downloads are blocked by interstitial pages (virus-scan confirmation, quota limits).

## Language

**Drive filename**:
The true name Google Drive holds for a file, carrying its real extension. For a single file it is read from the `Content-Disposition` response header; for a folder it is read from the embedded folder-view HTML. Distinct from the URL basename, which for a Drive download URL is meaningless (e.g. `uc`, `open`).
_Avoid_: output name, basename

**Listing**:
The `--json` output: a JSON array of `{url, path}` entries describing what would be downloaded, emitted instead of downloading. A dry run that resolves names without fetching file bodies. Works for both a single file and a folder; takes no output destination (combining with `-O`/`--output`, including `-O -`, is a hard error).
_Avoid_: manifest, index, dump

**path** (in a Listing entry):
The location a file would be written to, relative to the download root. For a folder, includes the directory structure. For a single file, it is the bare Drive filename. Always a real Drive filename; never a URL-basename fallback.

**GoogleDriveFileToDownload**:
The probe result returned by both downloaders under `skip_download=True`: `(id, path, local_path)`. Reused for single files so the probe mode is type-distinct from the normal `str | None` download return, making the mode self-announcing to Python callers and type-checkers.

## Example dialogue

> **Dev:** For a single-file `--json`, what's `path`?
> **Maintainer:** The Drive filename. Same guarantee as a folder entry: a real name with its real extension, never `uc`.
> **Dev:** And if there's no `Content-Disposition`, like a non-Drive URL?
> **Maintainer:** Then there's no Drive filename to report. We error out rather than emit a bad name. The Listing only ever contains real names.
