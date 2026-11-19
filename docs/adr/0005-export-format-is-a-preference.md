# 5. The export format is a preference, also for folders

Date: 2026-11-19

## Status

Accepted

## Context

`--format` chose the export format of a single Google-native file, but a
folder download ignored it and always wrote `.docx`, `.xlsx` and `.pptx`.
ADR-0003 left the folder case open as a separate feature. A folder can hold
Docs, Sheets and Slides together, and no format except `pdf` is valid for all
three: Google answers a Slides export as `csv` with HTTP 404.

Treating the format as a requirement would fail the Docs file in a folder
downloaded with `--format csv` while the `.jpg` next to it, which cannot
become `csv` either, downloads without complaint.
[rclone](https://rclone.org/drive/#import-export-of-google-documents) treats
its export formats as preferred and falls back to its defaults.

## Decision

The format is a preference. A Google-native file is downloaded in the
requested format when Google can export it. When Google answers the export
with an HTTP error, the file is downloaded in its default format with a
warning. This holds for a single file and for each file of a folder alike. A
file Google does not export at all, whose export ends on the editor page
instead of a file, still fails.

`download_folder(format=...)` and `--format` on a folder pass the one format
to every Google-native file. Ordinary files never receive it, because a
folder writes them under their folder-view name (ADR-0003) and a converted
file would keep the wrong extension.

Not adopted now, and addable later without changing this decision: a strict
mode that turns the fallback into an error, and an ordered list of formats
such as `csv,pdf`.

## Consequences

- A download no longer fails because Google rejects the format. The written
  filename and a Listing `path` carry the extension of the format actually
  used, so a caller that needs the requested format checks the extension.
- A file that falls back is resolved a second time from its own URL, which
  repeats the requests of the first resolution.
- A single uploaded `.pptx` can still be exported in another format, as
  before, while the same file inside a folder keeps its bytes.
