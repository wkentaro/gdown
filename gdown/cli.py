from __future__ import print_function

import argparse
import os.path
import re
import sys
import warnings

import six

from . import __version__
from .download import download
from .download_folder import MAX_NUMBER_FILES
from .download_folder import download_folder


class _ShowVersionAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        print(
            "gdown {ver} at {pos}".format(
                ver=__version__, pos=os.path.dirname(os.path.dirname(__file__))
            )
        )
        parser.exit()


def file_size(argv):
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


def main():
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
    parser.add_argument(
        "url_or_id", help="url or file/folder id (with --id) to download from"
    )
    parser.add_argument("-O", "--output", help="output file name / path")
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="suppress standard output"
    )
    parser.add_argument(
        "--fuzzy",
        action="store_true",
        help="(fild only) extract Google Drive's file ID",
    )
    parser.add_argument(
        "--id",
        action="store_true",
        help="[DEPRECATED] flag to specify file/folder id instead of url",
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
        help="don't use cookies in ~/.cache/gdown/cookies.json",
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
        help="(file only) resume getting a partially-downloaded file",
    )
    parser.add_argument(
        "--folder",
        action="store_true",
        help="download entire folder instead of a single file "
        "(max {max} files per folder)".format(max=MAX_NUMBER_FILES),
    )
    parser.add_argument(
        "--remaining-ok",
        action="store_true",
        help="(folder only) asserts that is ok to download max "
        "{max} files per folder.".format(max=MAX_NUMBER_FILES),
    )

    args = parser.parse_args()

    if args.output == "-":
        if six.PY3:
            args.output = sys.stdout.buffer
        else:
            args.output = sys.stdout

    if args.id:
        warnings.warn(
            "Option `--id` was deprecated in version 4.3.1 "
            "and will be removed in 5.0. You don't need to "
            "pass it anymore to use a file ID.",
            category=FutureWarning,
        )
        url = None
        id = args.url_or_id
    else:
        if re.match("^https?://.*", args.url_or_id):
            url = args.url_or_id
            id = None
        else:
            url = None
            id = args.url_or_id

    if args.folder:
        filenames = download_folder(
            url=url,
            id=id,
            output=args.output,
            quiet=args.quiet,
            proxy=args.proxy,
            speed=args.speed,
            use_cookies=not args.no_cookies,
            remaining_ok=args.remaining_ok,
        )
        success = filenames is not None
    else:
        filename = download(
            url=url,
            output=args.output,
            quiet=args.quiet,
            proxy=args.proxy,
            speed=args.speed,
            use_cookies=not args.no_cookies,
            verify=not args.no_check_certificate,
            id=id,
            fuzzy=args.fuzzy,
            resume=args.continue_,
        )
        success = filename is not None

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
