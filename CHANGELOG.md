# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

<!-- towncrier release notes start -->

## 6.4.0 - 2026-09-17

### Added

- Optional cancellation events for `download()` and `cached_download()` interrupt stalled response reads and download waits without shortening network timeouts, raising `DownloadCancelled` while preserving partial-file cleanup. ([#525](https://github.com/wkentaro/gdown/pull/525))

### Changed

- An invalid `--speed` value now reports the accepted units instead of an internal function name. ([#527](https://github.com/wkentaro/gdown/pull/527))

### Removed

- `importlib` is no longer exported from the `gdown` package; it was listed in `__all__` by accident. ([#526](https://github.com/wkentaro/gdown/pull/526))

## 6.3.0 - 2026-09-16

### Added

- Add a `secretstorage` installation extra for importing Chromium cookies from GNOME Keyring with `pip install 'gdown[secretstorage]'` or `uvx --from 'gdown[secretstorage]' gdown`. ([#505](https://github.com/wkentaro/gdown/pull/505))
- `download()`, `download_folder()`, and `cached_download()` accept a requests-style `timeout`, exposed on the command line as `--timeout SECONDS`, so a stalled server no longer blocks forever. ([#510](https://github.com/wkentaro/gdown/pull/510))
- Add opt-in `--retries N` and Python `retries=N` for automatic recovery of interrupted file and folder downloads, with bounded backoff and validated byte-range resume; `--continue` still controls reuse of earlier downloads. ([#517](https://github.com/wkentaro/gdown/pull/517))

### Changed

- `cached_download()` verifies `hash` while streaming instead of reading the finished file back from disk. ([#512](https://github.com/wkentaro/gdown/pull/512))
- The command line reports a hit `--timeout` as a timeout instead of asking to file an issue. ([#513](https://github.com/wkentaro/gdown/pull/513))

### Fixed

- Propagate progress callback exceptions unchanged instead of misreporting chunked-encoding errors as incomplete downloads. ([#519](https://github.com/wkentaro/gdown/pull/519))

## 6.2.0 - 2026-09-06

### Added

- Add `--cookies-from-browser BROWSER` to download as your signed-in Google account using cookies read straight from a local browser, and `--cookies FILE` to use a cookies file other than `~/.cache/gdown/cookies.txt`. The cookies file is now written owner-only and keeps session cookies. ([#494](https://github.com/wkentaro/gdown/pull/494))

### Changed

- Continue downloading the remaining files in a folder after individual downloads fail, then report all failures together. ([#495](https://github.com/wkentaro/gdown/pull/495))
- Automatically detect Google Drive folder URLs, making `--folder` necessary only for ambiguous bare IDs. ([#496](https://github.com/wkentaro/gdown/pull/496))

### Fixed

- Close download sessions and streamed responses on early exits, failures, and response replacement, including single-file Listing and resumed downloads. ([#499](https://github.com/wkentaro/gdown/pull/499))
- Remove cached-download staging directories after success or interruption, and create the cache on demand instead of during import. ([#500](https://github.com/wkentaro/gdown/pull/500))
- Honor an explicitly supplied user agent for file downloads within folders while retaining the existing default user agents. ([#501](https://github.com/wkentaro/gdown/pull/501))
- Fix folder `--json` export paths and preserve export extensions for dotted Google-native filenames. ([#503](https://github.com/wkentaro/gdown/pull/503))
- Preserve the saved cookies file when browser cookie extraction reports an error instead of replacing working session cookies with invalid decrypted values. ([#504](https://github.com/wkentaro/gdown/pull/504))

## 6.1.1 - 2026-09-04

### Fixed

- Fixed downloads leaking HTTP sessions, progress bars, or output files when an exception interrupted a file or folder download. ([#478](https://github.com/wkentaro/gdown/pull/478))
- Reject incomplete response bodies instead of saving them as completed downloads. ([#481](https://github.com/wkentaro/gdown/pull/481))
- Normalized archive member paths returned by `extractall`, so ZIP and tar results use native path separators consistently. ([#487](https://github.com/wkentaro/gdown/pull/487))

## 6.1.0 - 2026-05-30

### Added

- Added `--json` output for folder downloads as an array of URL and path records. ([#460](https://github.com/wkentaro/gdown/pull/460))
- Extended `--json` to resolve single-file URLs and filenames without downloading the file body. ([#463](https://github.com/wkentaro/gdown/pull/463))

### Changed

- Marked `--json` as beta and added a warning that can be suppressed with `--quiet`. ([#465](https://github.com/wkentaro/gdown/pull/465))

## v6.0.0 and earlier

See the [GitHub Releases](https://github.com/wkentaro/gdown/releases) page for changelogs of v6.0.0 and earlier.
