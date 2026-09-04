import argparse
import json
import os.path
import re
import sys
import textwrap
from collections.abc import Sequence
from typing import Any
from typing import Final

import requests

from . import __version__
from ._vendor._ytdlp_cookies import SUPPORTED_BROWSERS
from .download import DEFAULT_COOKIES_FILE
from .download import GoogleDriveFileToDownload
from .download import _import_cookies_from_browser
from .download import download
from .download_folder import download_folder
from .exceptions import DownloadError

BROWSERS: Final = tuple(sorted(SUPPORTED_BROWSERS))


class _ShowVersionAction(argparse.Action):
    # The callback protocol requires the full signature even when values are unused.
    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,  # noqa: ARG002
        values: str | Sequence[Any] | None,  # noqa: ARG002
        option_string: str | None = None,  # noqa: ARG002
    ) -> None:  # noqa: GR005 -- inherited protocol accepts both call styles
        print(f"gdown {__version__} at {os.path.dirname(os.path.dirname(__file__))}")
        parser.exit()


def file_size(argv: str | None) -> float | None:  # noqa: GR005 -- public API accepts both call styles
    if argv is None:
        return None
    m = re.match(r"([0-9]+)(GB|MB|KB|B)", argv)
    if not m:
        raise TypeError
    size, unit = m.groups()
    size = float(size)
    if unit == "KB":
        size *= 1024
    elif unit == "MB":
        size *= 1024**2
    elif unit == "GB":
        size *= 1024**3
    elif unit == "B":
        pass
    return size


def main() -> None:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-V",
        "--version",
        action=_ShowVersionAction,
        help="display version",
        nargs=0,
    )
    parser.add_argument("url_or_id", help="url or file/folder id to download from")
    parser.add_argument(
        "-O",
        "--output",
        help=(
            f'output file name/path; end with "{os.path.sep}" to create a new directory'
        ),
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="suppress logging except errors",
    )
    parser.add_argument(
        "--proxy",
        help="<protocol://host:port> download using the specified proxy",
    )
    parser.add_argument(
        "--speed",
        type=file_size,
        help="download speed limit in second (e.g., '10MB' -> 10MB/s)",
    )
    parser.add_argument(
        "--cookies",
        metavar="FILE",
        # Absent from the namespace unless given, which is how the conflict
        # check below tells "not passed" from "passed"; it also keeps the
        # formatter from printing "(default: None)" after the real default.
        default=argparse.SUPPRESS,
        help=(
            "Netscape cookies file to read cookies from and save them to "
            "(default: ~/.cache/gdown/cookies.txt)"
        ),
    )
    parser.add_argument(
        "--cookies-from-browser",
        metavar="BROWSER",
        choices=BROWSERS,
        help=(
            "copy your Google cookies from this browser into the cookies file, "
            "so this and later runs download as your signed-in account. "
            f"One of: {', '.join(BROWSERS)}"
        ),
    )
    parser.add_argument(
        "--no-cookies",
        action="store_true",
        help="don't read or save cookies",
    )
    parser.add_argument(
        "--no-check-certificate",
        action="store_true",
        help="don't check the server's TLS certificate",
    )
    parser.add_argument(
        "--continue",
        "-c",
        dest="continue_",
        action="store_true",
        help="resume getting partially-downloaded files while "
        "skipping fully downloaded ones",
    )
    parser.add_argument(
        "--folder",
        action="store_true",
        help="download entire folder instead of a single file",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help=(
            "(beta) list file or folder contents as a JSON array on stdout "
            "instead of downloading. Each entry is an object with 'url' and "
            "'path'. The output format may change in a future release. "
            "Cannot be combined with -O/--output."
        ),
    )
    parser.add_argument(
        "--format",
        help="Format of Google Docs, Spreadsheets and Slides. "
        "Default is Google Docs: 'docx', Spreadsheet: 'xlsx', Slides: 'pptx'.",
    )
    parser.add_argument(
        "--user-agent",
        help="User-Agent to use for downloading file.",
    )

    args = parser.parse_args()

    if args.json and args.output is not None:
        parser.error("--json cannot be combined with -O/--output")

    if args.no_cookies and ("cookies" in args or args.cookies_from_browser):
        parser.error(
            "--no-cookies cannot be combined with --cookies or --cookies-from-browser"
        )
    if "cookies" in args and not args.cookies:
        parser.error("--cookies needs a file path")
    cookies_file = os.path.expanduser(getattr(args, "cookies", DEFAULT_COOKIES_FILE))

    browser = args.cookies_from_browser
    if browser:
        try:
            n_cookies = _import_cookies_from_browser(
                browser=browser, cookies_file=cookies_file
            )
        except Exception as e:
            hint = ""
            if sys.platform == "win32" and browser != "firefox":
                hint = (
                    "\n\nChrome 127+ on Windows blocks other programs from "
                    "reading its cookies. Try --cookies-from-browser firefox."
                )
            reason = textwrap.indent(str(e), prefix="\t")
            print(
                f"Failed to import cookies from {browser} into {cookies_file}:"
                f"\n\n{reason}{hint}",
                file=sys.stderr,
            )
            sys.exit(1)
        if n_cookies == 0:
            print(
                f"No Google cookies found in {browser}. Sign in to Google in that "
                "browser, or pick another one with --cookies-from-browser.",
                file=sys.stderr,
            )
            sys.exit(1)
        if not args.quiet:
            noun = "cookie" if n_cookies == 1 else "cookies"
            print(
                f"Saved {n_cookies} Google {noun} from {browser} to {cookies_file}",
                file=sys.stderr,
            )

    if args.json and not args.quiet:
        print(
            "warning: `--json` is in beta and its output format may change in a "
            "future release",
            file=sys.stderr,
        )

    if args.output == "-":
        args.output = sys.stdout.buffer

    if re.match("^https?://.*", args.url_or_id):
        url = args.url_or_id
        id = None
    else:
        url = None
        id = args.url_or_id

    try:
        if args.folder:
            if not (args.output is None or isinstance(args.output, str)):
                raise ValueError("--folder does not support stdout output (-O -)")
            result = download_folder(
                url=url,
                id=id,
                output=args.output,
                quiet=args.quiet or args.json,
                proxy=args.proxy,
                speed=args.speed,
                use_cookies=not args.no_cookies,
                verify=not args.no_check_certificate,
                user_agent=args.user_agent,
                resume=args.continue_,
                skip_download=args.json,
                cookies_file=cookies_file,
            )
        else:
            result = download(
                url=url,
                output=args.output,
                quiet=args.quiet or args.json,
                proxy=args.proxy,
                speed=args.speed,
                use_cookies=not args.no_cookies,
                verify=not args.no_check_certificate,
                id=id,
                resume=args.continue_,
                format=args.format,
                user_agent=args.user_agent,
                skip_download=args.json,
                cookies_file=cookies_file,
            )

        if args.json:
            files = result if args.folder else [result]
            entries = []
            for file in files:
                assert isinstance(file, GoogleDriveFileToDownload)
                entries.append(
                    {
                        "url": f"https://drive.google.com/uc?id={file.id}",
                        "path": file.path.replace(os.sep, "/"),
                    }
                )
            print(json.dumps(entries, ensure_ascii=False, indent=2))
    except DownloadError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.ProxyError as e:
        print(
            "Failed to use proxy:\n\n{}\n\nPlease check your proxy settings.".format(
                textwrap.indent("\n".join(textwrap.wrap(str(e))), prefix="\t")
            ),
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        print(
            "Error:\n\n{}\n\nTo report issues, please visit "
            "https://github.com/wkentaro/gdown/issues.".format(
                textwrap.indent("\n".join(textwrap.wrap(str(e))), prefix="\t")
            ),
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
