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

The format is a preference. Every file is downloaded: a Google-native file in
the requested format when Google can export it, and otherwise in its default
format with a warning. This holds for a single file and for each file of a
folder alike.

`download_folder(format=...)` and `--format` on a folder pass the one format
to every Google-native file. Ordinary files never receive it, because a
folder writes them under their folder-view name (ADR-0003) and a converted
file would keep the wrong extension.

Not adopted now, and addable later without changing this decision: a strict
mode that turns the fallback into an error, and an ordered list of formats
such as `csv,pdf`.

## Consequences

- A download no longer fails because of the format. The written filename and
  a Listing `path` carry the extension of the format actually used, so a
  caller that needs the requested format checks the extension.
- A file that falls back costs two extra requests, since the default export
  is resolved again from the file's own URL.
- A single uploaded `.pptx` can still be exported in another format, as
  before, while the same file inside a folder keeps its bytes.
