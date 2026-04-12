import argparse
import os.path
import re
import sys
import textwrap
from collections.abc import Sequence
from typing import Any

import requests

from . import __version__
from .download import download
from .download_folder import download_folder
from .exceptions import DownloadError


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
        "--format",
        help="Format of Google Docs, Spreadsheets and Slides. "
        "Default is Google Docs: 'docx', Spreadsheet: 'xlsx', Slides: 'pptx'.",
    )
    parser.add_argument(
        "--user-agent",
        help="User-Agent to use for downloading file.",
    )

    args = parser.parse_args()

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
            download_folder(
                url=url,
                id=id,
                output=args.output,
                quiet=args.quiet,
                proxy=args.proxy,
                speed=args.speed,
                use_cookies=not args.no_cookies,
                verify=not args.no_check_certificate,
                user_agent=args.user_agent,
                resume=args.continue_,
            )
        else:
            download(
                url=url,
                output=args.output,
                quiet=args.quiet,
                proxy=args.proxy,
                speed=args.speed,
                use_cookies=not args.no_cookies,
                verify=not args.no_check_certificate,
                id=id,
                resume=args.continue_,
                format=args.format,
                user_agent=args.user_agent,
            )
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
