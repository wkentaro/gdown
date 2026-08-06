# 2. `--auto` treats folder URLs as folders, retries everything else on `FileURLRetrievalError`

Date: 2026-08-06

## Status

Accepted

## Context

Users must currently pass `--folder` explicitly; a bare ID or non-`/folders/`
URL that actually points at a folder just fails. `--auto` removes that
requirement by detecting which mode to use.

A Drive folder URL (`.../drive/folders/<id>`) is unambiguous — no probing
needed. A bare ID or a `.../file/d/<id>/...`-shaped URL is not: Drive IDs
don't self-describe their type, and a bare ID is deliberately ambiguous
(could be either). The only way to know for certain is to ask Drive.

Two ways to ask:

- Fetch Drive metadata for the ID up front (e.g. an explicit "what is this"
  request) before choosing a code path.
- Just try file mode; Drive's own response tells us if that was wrong.

`download()` already surfaces "this isn't a downloadable file" as
`FileURLRetrievalError` — raised when the resolution loop can't find a
confirmation link, download form, or `downloadUrl` in Drive's response, which
is exactly what happens when the id/URL is actually a folder. Reusing that
error instead of adding a separate metadata lookup means `--auto` costs no
extra request in the common case (first guess is right) and needs no new
Drive API surface. The error is raised entirely within the URL-resolution
phase of `download()`, before any file is opened for writing, so a retry
never needs to clean up a partial download.

## Decision

`--auto`:

- If `url_or_id` is a URL matching `/drive/folders/`, download as a folder
  directly (same as passing `--folder`).
- Otherwise, attempt file mode. If `download()` raises `FileURLRetrievalError`,
  retry the same `url_or_id` as a folder via `download_folder()`.
- `--auto` and `--folder` are mutually exclusive (`--folder` already commits
  to a mode; combining is either redundant or contradictory) — hard
  `argparse` error, matching the existing `--json`/`-O` conflict style.

## Consequences

- No extra Drive request for the common cases (folder URL, or a file ID that
  really is a file) — detection is free or a natural side effect of the
  existing resolution flow.
- A folder ID given as `url_or_id` (not a `/folders/` URL) costs one wasted
  file-mode round trip before the folder retry. Acceptable: bare IDs are
  ambiguous by construction, and this is the only case that pays the cost.
- Other `DownloadError` subclasses are not treated as "maybe a folder" and
  propagate immediately — only `FileURLRetrievalError` specifically means
  "not a downloadable file," so only it triggers the retry.
