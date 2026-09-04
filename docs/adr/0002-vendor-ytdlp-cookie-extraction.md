# 2. Vendor yt-dlp's cookie extraction instead of adding a dependency

Date: 2026-09-04

## Status

Accepted

## Context

Google Drive throttles popular public files with "Too many users have viewed
or downloaded this file recently", but serves the same file to a signed-in
account. Verified on 2026-09-04: a throttled Newer College rosbag failed
without cookies and downloaded with a signed-in browser's Google cookies.

gdown could already use cookies, but only from a Netscape file the user
exported with a browser extension and moved into the cache directory. The
convention set by yt-dlp and copied by gallery-dl is `--cookies FILE` plus
`--cookies-from-browser BROWSER`, and `uvx gdown` must work with no extra.

Reading a browser's cookie store means SQLite, per-platform key retrieval,
and AES decryption. Browser extraction is the one CLI-only feature in gdown,
and most installs use gdown as a library, so a new runtime dependency for it
is hard to justify. The options:

- Depend on browser-cookie3 (LGPL, three to six transitive packages, two of
  them C extensions, upstream mostly idle since December 2024). Rejected:
  every library user pays for a CLI feature, and LGPL code cannot be copied
  into an MIT project if we later want to drop the dependency.
- Depend on yt-dlp. Rejected: a 3 MB dependency for one function.
- Copy the code from gallery-dl. Rejected: GPL-2.
- Vendor from yt-dlp. Its `cookies.py` and pure-Python `aes.py` are
  released under the Unlicense (public domain), need only the standard
  library plus system tools (`security` on macOS, `dbus-send` and `kwallet`
  on Linux, DPAPI via ctypes on Windows), and are actively maintained.
- Ship it as an optional extra. Rejected: extras only add dependencies, so a
  slim `gdown[core]` cannot be expressed, and `uvx gdown` would not have it.

No option reads Chrome 127+ cookies on Windows without admin rights, because
of Google's App-Bound Encryption. Firefox works everywhere.

## Decision

Vendor a symbol-level extraction of yt-dlp's cookie module. A checked-in
script pins a yt-dlp release tag, downloads `cookies.py` and `aes.py`, walks
the closure of `extract_cookies_from_browser` over their top-level
definitions, and writes one generated file. The generated file is never
edited by hand; upgrading is rerunning the script with a newer tag.

The dozen yt-dlp internals the extracted code imports (its logger, progress
printer, subprocess wrapper, and small string helpers) live in a
hand-written shim next to the generated file, so the generated file stays a
pure copy and the hand-maintained surface is about a hundred lines.

The CLI copies the browser's google.com cookies into the cookies file once,
before the download, so the library keeps a single cookie source and later
runs need no flag. Both flags follow the yt-dlp names. Session cookies are
kept when saving and loading the file, because Google's sign-in state partly
lives in them.

## Consequences

- `uvx gdown --cookies-from-browser firefox URL` works with no extra and no
  new runtime dependency.
- About 1,600 generated lines live in the repository and are excluded from
  lint and type checks. They change only when the script is rerun.
- When upstream renames one of its internals, the script's shim-name report
  and the import of the generated module fail loudly, which is the signal to
  extend the shim.
- The browser list is whatever the pinned yt-dlp release supports.
- The cookies file holds a signed-in Google session, so it is written
  owner-only and the README says to treat it like a password.
- Windows Chrome users get an error that points them to Firefox.
