import argparse
import json
import os.path
import re
import sys
import textwrap
from collections.abc import Sequence
from typing import Any

import requests

from . import __version__
from .download import GoogleDriveFileToDownload
from .download import download
from .download_folder import download_folder
from .exceptions import DownloadError
from .exceptions import FileURLRetrievalError

_FOLDER_URL_RE = re.compile(r"^https?://drive\.google\.com/drive/(u/[0-9]+/)?folders/")


class _ShowVersionAction(argparse.Action):
    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        print(f"gdown {__version__} at {os.path.dirname(os.path.dirname(__file__))}")
        parser.exit()


def file_size(argv: str | None) -> float | None:
    if argv is not None:
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
        "--no-cookies",
        action="store_true",
        help="don't use cookies in ~/.cache/gdown/cookies.txt",
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
        "--auto",
        action="store_true",
        help=(
            "autodetect whether to download a file or a folder instead of "
            "requiring --folder. A '/drive/folders/' URL is treated as a "
            "folder; anything else is tried as a file first and retried as "
            "a folder if Drive reports it isn't a downloadable file. "
            "Cannot be combined with --folder."
        ),
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

    if args.auto and args.folder:
        parser.error("--auto cannot be combined with --folder")

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

    as_folder = args.folder
    if args.auto and url is not None and _FOLDER_URL_RE.match(url):
        as_folder = True

    def _download_as_folder() -> list[str] | list[GoogleDriveFileToDownload]:
        if not (args.output is None or isinstance(args.output, str)):
            raise ValueError("--folder does not support stdout output (-O -)")
        return download_folder(
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
        )

    try:
        if as_folder:
            result = _download_as_folder()
        else:
            try:
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
                )
            except FileURLRetrievalError:
                if not args.auto:
                    raise
                # Not a downloadable file; retry assuming url_or_id is a folder.
                as_folder = True
                result = _download_as_folder()

        if args.json:
            files = result if as_folder else [result]
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
