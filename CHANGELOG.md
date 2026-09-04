# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

<!-- towncrier release notes start -->

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
