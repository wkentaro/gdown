import collections
import contextlib
import datetime
import email.utils
import hashlib
import os
import os.path as osp
import re
import shutil
import sys
import tempfile
import textwrap
import time
import urllib.parse
import warnings
from collections.abc import Callable
from collections.abc import Iterable
from http import HTTPStatus
from http.cookiejar import Cookie
from http.cookiejar import MozillaCookieJar
from typing import BinaryIO
from typing import Final

import bs4
import requests
import tqdm

from ._vendor._ytdlp_shim import _YDLLogger
from .exceptions import DownloadError
from .exceptions import FileURLRetrievalError
from .parse_url import parse_url

CHUNK_SIZE: Final = 512 * 1024  # 512KB
home = osp.expanduser("~")
DEFAULT_COOKIES_FILE: Final = osp.join(home, ".cache/gdown/cookies.txt")

GoogleDriveFileToDownload = collections.namedtuple(
    "GoogleDriveFileToDownload", ("id", "path", "local_path")
)


def get_url_from_gdrive_confirmation(contents: str) -> str:  # noqa: GR005 -- public API accepts both call styles
    url = ""
    for line in contents.splitlines():
        m = re.search(r'href="(\/uc\?export=download[^"]+)', line)
        if m:
            url = "https://docs.google.com" + m.groups()[0]
            url = url.replace("&amp;", "&")
            break
        soup = bs4.BeautifulSoup(line, features="html.parser")
        form = soup.select_one("#download-form")
        if form is not None:
            action = form["action"]
            assert isinstance(action, str)
            url = action.replace("&amp;", "&")
            url_components = urllib.parse.urlsplit(url)
            query_params = urllib.parse.parse_qs(url_components.query)
            for param in form.find_all("input", attrs={"type": "hidden"}):
                param_name = param["name"]
                param_value = param["value"]
                assert isinstance(param_name, str)
                assert isinstance(param_value, str)
                query_params[param_name] = [param_value]
            query = urllib.parse.urlencode(query_params, doseq=True)
            url = urllib.parse.urlunsplit(url_components._replace(query=query))
            break
        m = re.search('"downloadUrl":"([^"]+)', line)
        if m:
            url = m.groups()[0]
            url = url.replace("\\u003d", "=")
            url = url.replace("\\u0026", "&")
            break
        m = re.search('<p class="uc-error-subcaption">(.*)</p>', line)
        if m:
            error = m.groups()[0]
            raise FileURLRetrievalError(error)
    if not url:
        raise FileURLRetrievalError(
            "Cannot retrieve the public link of the file. "
            "You may need to change the permission to "
            "'Anyone with the link', or have had many accesses. "
            "Check FAQ in https://github.com/wkentaro/gdown?tab=readme-ov-file#faq.",
        )
    return url


def _sanitize_filename(*, filename: str) -> str:
    filename = filename.replace("\x00", "")
    filename = filename.replace("/", "_").replace("\\", "_").strip()
    if filename in ("", ".", ".."):
        return "_"
    return filename


def _get_filename_from_response(*, response: requests.Response) -> str | None:
    content_disposition = urllib.parse.unquote(response.headers["Content-Disposition"])

    m = re.search(r"filename\*=UTF-8''(.*)", content_disposition)
    if m:
        return _sanitize_filename(filename=m.groups()[0])

    m = re.search('attachment; filename="(.*?)"', content_disposition)
    if m:
        return _sanitize_filename(filename=m.groups()[0])

    return None


def _get_content_length_from_response(*, response: requests.Response) -> int | None:
    content_length = response.headers.get("Content-Length")
    if content_length is None:
        return None
    try:
        size = int(content_length)
    except ValueError:
        return None
    return size if size >= 0 else None


def _has_only_identity_encoding(*, response: requests.Response, header: str) -> bool:
    encodings = response.headers.get(header, "").split(",")
    return all(encoding.strip().lower() in ("", "identity") for encoding in encodings)


def _is_content_length_comparable(*, response: requests.Response) -> bool:
    # A content encoding the client decodes transparently makes Content-Length
    # count the encoded bytes on the wire instead of the ones iteration yields,
    # and a transfer encoding makes the client ignore Content-Length entirely.
    return _has_only_identity_encoding(
        response=response, header="Content-Encoding"
    ) and _has_only_identity_encoding(response=response, header="Transfer-Encoding")


def _get_modified_time_from_response(
    *,
    response: requests.Response,
) -> datetime.datetime | None:
    if "Last-Modified" not in response.headers:
        return None

    raw = response.headers["Last-Modified"]
    if raw is None:
        return None

    return email.utils.parsedate_to_datetime(raw)


def _compute_filehash(*, path: str, algorithm: str) -> str:
    BLOCKSIZE: Final = 65536

    if algorithm not in hashlib.algorithms_guaranteed:
        raise ValueError(
            f"Unsupported hash algorithm: {algorithm}. "
            f"Supported algorithms: {hashlib.algorithms_guaranteed}"
        )

    algorithm_instance = getattr(hashlib, algorithm)()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(BLOCKSIZE), b""):
            algorithm_instance.update(block)
    return f"{algorithm}:{algorithm_instance.hexdigest()}"


def _assert_filehash(*, path: str, hash: str) -> None:
    if ":" not in hash:
        raise ValueError(
            f"Invalid hash: {hash}. "
            "Hash must be in the format of {algorithm}:{hash_value}."
        )
    algorithm = hash.split(":")[0]

    hash_actual = _compute_filehash(path=path, algorithm=algorithm)

    if hash_actual != hash:
        raise AssertionError(
            f"File hash doesn't match:\nactual: {hash_actual}\nexpected: {hash}"
        )


def _load_cookies(*, cookies_file: str) -> MozillaCookieJar:
    cookies_file = osp.expanduser(cookies_file)
    cookie_jar = MozillaCookieJar(cookies_file)
    if not osp.exists(cookies_file):
        return cookie_jar
    try:
        # Google's sign-in state partly lives in session cookies, which the
        # Netscape format drops unless told to keep them.
        cookie_jar.load(ignore_discard=True, ignore_expires=True)
    except (OSError, UnicodeDecodeError) as e:
        warnings.warn(
            f"Replacing unreadable cookies file {cookies_file}: {e}", stacklevel=2
        )
        return MozillaCookieJar(cookies_file)
    for cookie in cookie_jar:
        # Browser extensions export session cookies with expiry 0, which the
        # standard library would otherwise treat as already expired.
        if cookie.expires == 0:
            cookie.expires = None
            cookie.discard = True
    cookie_jar.clear_expired_cookies()
    return cookie_jar


def _save_cookies(*, cookies: Iterable[Cookie], cookies_file: str) -> None:
    cookies_file = osp.expanduser(cookies_file)
    cookie_jar = MozillaCookieJar(cookies_file)
    for cookie in cookies:
        cookie_jar.set_cookie(cookie)
    os.makedirs(osp.dirname(cookies_file) or ".", exist_ok=True)
    # The file can hold a signed-in Google session, so make it owner-only
    # before any byte is written. The directory is left alone: for a bare
    # filename it is the working directory.
    os.close(os.open(cookies_file, flags=os.O_WRONLY | os.O_CREAT, mode=0o600))
    os.chmod(cookies_file, 0o600)
    cookie_jar.save(ignore_discard=True)


class _CookieExtractionLogger(_YDLLogger):
    # The vendored extractor reports keyring and decryption trouble here. Its
    # Chromium and Safari paths still use the older only_once spelling, and
    # they raise the same warning for every cookie in the browser's database.
    def __init__(self) -> None:
        super().__init__()
        self._seen: set[str] = set()

    def warning(
        self, message: str, /, *, once: bool = False, only_once: bool = False
    ) -> None:
        if (once or only_once) and message in self._seen:
            return
        self._seen.add(message)
        print(f"warning: {message}", file=sys.stderr)

    def error(self, message: str, /, *, is_error: bool = True) -> None:  # noqa: ARG002
        print(f"error: {message}", file=sys.stderr)


def _import_cookies_from_browser(*, browser: str, cookies_file: str) -> int:
    # Imported here so the extractor's probing code loads only when asked for.
    from ._vendor._ytdlp_cookies import CHROMIUM_BASED_BROWSERS  # noqa: PLC0415
    from ._vendor._ytdlp_cookies import extract_cookies_from_browser  # noqa: PLC0415

    browser_cookies = [
        cookie
        for cookie in extract_cookies_from_browser(
            browser, logger=_CookieExtractionLogger()
        )
        if cookie.domain == "google.com" or cookie.domain.endswith(".google.com")
    ]
    if browser in CHROMIUM_BASED_BROWSERS:
        for cookie in browser_cookies:
            # Chromium stores expiry as microseconds since 1601 and the
            # extractor copies that verbatim, so expired cookies would
            # otherwise be saved as far-future ones.
            if cookie.expires:
                cookie.expires = cookie.expires // 1_000_000 - 11_644_473_600
    if not browser_cookies:
        # Nothing to add, so leave the file system untouched.
        return 0
    cookie_jar = _load_cookies(cookies_file=cookies_file)
    for cookie in browser_cookies:
        cookie_jar.set_cookie(cookie)
    _save_cookies(cookies=cookie_jar, cookies_file=cookies_file)
    return len(browser_cookies)


def _get_session(
    *,
    proxy: str | None,
    use_cookies: bool,
    user_agent: str,
    cookies_file: str | None,
) -> tuple[requests.Session, str]:
    sess = requests.session()

    sess.headers.update({"User-Agent": user_agent})

    if proxy is not None:
        sess.proxies = {"http": proxy, "https": proxy}
        print("Using proxy:", proxy, file=sys.stderr)

    cookies_file = osp.expanduser(cookies_file or DEFAULT_COOKIES_FILE)
    if use_cookies:
        sess.cookies.update(_load_cookies(cookies_file=cookies_file))

    return sess, cookies_file


# Parameters remain positional-or-keyword for backward compatibility.
def download(
    url: str | None = None,
    output: str | BinaryIO | None = None,
    quiet: bool = False,  # noqa: FBT001, FBT002
    proxy: str | None = None,
    speed: float | None = None,
    use_cookies: bool = True,  # noqa: FBT001, FBT002
    verify: bool | str = True,  # noqa: FBT001, FBT002
    id: str | None = None,
    resume: bool = False,  # noqa: FBT001, FBT002
    format: str | None = None,
    user_agent: str | None = None,
    log_messages: dict[str, str] | None = None,
    progress: Callable[[int, int | None], None] | None = None,
    skip_download: bool = False,  # noqa: FBT001, FBT002
    cookies_file: str | None = None,
    hash: str | None = None,
) -> str | BinaryIO | GoogleDriveFileToDownload:  # noqa: GR005 -- public API accepts both call styles
    """Download file from URL.

    Parameters
    ----------
    url:
        URL. Google Drive URL is also supported.
    output:
        Output filename/directory. Default is basename of URL.
        If output is an existing directory or ends with a path separator,
        the basename will be appended automatically.
    quiet:
        Suppress terminal output. Default is False.
    proxy:
        Proxy.
    speed:
        Download byte size per second (e.g., 256KB/s = 256 * 1024).
    use_cookies:
        Flag to use cookies. Default is True.
    verify:
        Either a bool, in which case it controls whether the server's TLS
        certificate is verified, or a string, in which case it must be a path
        to a CA bundle to use. Default is True.
    id:
        Google Drive's file ID.
    resume:
        Resume interrupted downloads while skipping completed ones.
        Default is False.
    format:
        Format of Google Docs, Spreadsheets and Slides. Default is:
            - Google Docs: 'docx'
            - Google Spreadsheet: 'xlsx'
            - Google Slides: 'pptx'
    user_agent:
        User-agent to use in the HTTP request.
    log_messages:
        Log messages to customize. Currently it supports:
        - 'start': the message to show the start of the download
        - 'output': the message to show the output filename
    progress:
        Callback called after each chunk: ``progress(bytes_so_far, bytes_total)``.
        *bytes_total* is None when Content-Length is unavailable.
        Raise any exception from the callback to abort the download.
    skip_download:
        Resolve the Google Drive filename without downloading the file body.
        Default is False.
    cookies_file:
        Netscape cookies file to load before the request and save after
        every Google Drive response. Default is ~/.cache/gdown/cookies.txt.
        Ignored when use_cookies is False.
    hash:
        Expected hash of the downloaded file in the format of
        {algorithm}:{hash_value}. Requires output to be a filename.

    Returns
    -------
    output:
        Output filename when downloading. When skip_download is True, a
        GoogleDriveFileToDownload whose path is the resolved Google Drive
        filename.

    Raises
    ------
    ValueError
        If neither url nor id is specified, both are specified, output is not
        a filename when hash is specified, or hash is malformed or uses an
        unsupported algorithm.
    FileURLRetrievalError
        If the file URL cannot be retrieved from Google Drive, or if
        skip_download is True and no Google Drive filename can be resolved.
    DownloadError
        If the download fails (e.g., the response body ends before the
        announced number of bytes, or multiple temporary files exist during
        resume).
    """
    if not (id is None) ^ (url is None):
        raise ValueError("Either url or id has to be specified")
    if hash and output is not None and not isinstance(output, str):
        raise ValueError("hash can only be verified when output is a filename")
    if id is not None:
        url = f"https://drive.google.com/uc?id={id}"
    assert url is not None
    if user_agent is None:
        # We need to use different user agent for file download c.f., folder
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36"  # NOQA: E501
    if log_messages is None:
        log_messages = {}

    url_origin = url

    sess, cookies_file = _get_session(
        proxy=proxy,
        use_cookies=use_cookies,
        user_agent=user_agent,
        cookies_file=cookies_file,
    )

    gdrive_file_id, is_gdrive_download_link = parse_url(url=url)

    if gdrive_file_id:
        url = f"https://drive.google.com/uc?id={gdrive_file_id}"
        url_origin = url
        is_gdrive_download_link = True

    while True:
        res = sess.get(url, stream=True, verify=verify)

        if not (gdrive_file_id and is_gdrive_download_link):
            break

        if url == url_origin and res.status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
            # The file could be Google Docs or Spreadsheets.
            url = f"https://drive.google.com/open?id={gdrive_file_id}"
            continue

        if res.headers["Content-Type"].startswith("text/html"):
            if "/document/" in res.url and "/export" not in res.url:
                url = (
                    "https://docs.google.com/document/d/{id}/export"
                    "?format={format}".format(
                        id=gdrive_file_id,
                        format="docx" if format is None else format,
                    )
                )
                continue
            elif "/spreadsheets/" in res.url and "/export" not in res.url:
                url = (
                    "https://docs.google.com/spreadsheets/d/{id}/export"
                    "?format={format}".format(
                        id=gdrive_file_id,
                        format="xlsx" if format is None else format,
                    )
                )
                continue
            elif "/presentation/" in res.url and "/export" not in res.url:
                url = (
                    "https://docs.google.com/presentation/d/{id}/export"
                    "?format={format}".format(
                        id=gdrive_file_id,
                        format="pptx" if format is None else format,
                    )
                )
                continue
        elif (
            "Content-Disposition" in res.headers
            and res.headers["Content-Disposition"].endswith("pptx")
            and format not in {None, "pptx"}
        ):
            url = (
                "https://docs.google.com/presentation/d/{id}/export"
                "?format={format}".format(
                    id=gdrive_file_id,
                    format="pptx" if format is None else format,
                )
            )
            continue

        if use_cookies:
            try:
                _save_cookies(cookies=sess.cookies, cookies_file=cookies_file)
            except OSError as e:
                # Persisting cookies must never cost a download that succeeded.
                warnings.warn(
                    f"Failed to save cookies to {cookies_file}: {e}", stacklevel=2
                )

        if "Content-Disposition" in res.headers:
            # This is the file
            break

        # Need to redirect with confirmation
        try:
            url = get_url_from_gdrive_confirmation(res.text)
        except FileURLRetrievalError as e:
            message = (
                "Failed to retrieve file url:\n\n{}\n\n"
                "You may still be able to access the file from the browser:"
                "\n\n\t{}\n\n"
                "but Gdown can't. Please check connections and permissions."
            ).format(
                textwrap.indent("\n".join(textwrap.wrap(str(e))), prefix="\t"),
                url_origin,
            )
            raise FileURLRetrievalError(message)

    filename_from_url = None
    last_modified_time = None
    if gdrive_file_id and is_gdrive_download_link:
        filename_from_url = _get_filename_from_response(response=res)
        last_modified_time = _get_modified_time_from_response(response=res)

    if skip_download:
        if filename_from_url is None:
            raise FileURLRetrievalError(
                "Could not determine the Google Drive filename; --json requires "
                f"a resolvable Google Drive file (got: {url_origin})"
            )
        return GoogleDriveFileToDownload(
            id=gdrive_file_id, path=filename_from_url, local_path=filename_from_url
        )

    if filename_from_url is None:
        filename_from_url = _sanitize_filename(filename=osp.basename(url))

    if output is None:
        output = filename_from_url

    if isinstance(output, str) and (output.endswith(("/", "\\")) or osp.isdir(output)):
        if not osp.exists(output):
            os.makedirs(output)
        output = osp.join(output, filename_from_url)

    if isinstance(output, str):
        if resume and os.path.isfile(output):
            if hash:
                _assert_filehash(path=output, hash=hash)
            if not quiet:
                print(f"Skipping already downloaded file {output}", file=sys.stderr)
            return output

        existing_tmp_files = []
        for file in os.listdir(osp.dirname(output) or "."):
            if file.startswith(osp.basename(output)) and file.endswith(".part"):
                existing_tmp_files.append(osp.join(osp.dirname(output), file))
        if resume and existing_tmp_files:
            if len(existing_tmp_files) != 1:
                lines = ["There are multiple temporary files to resume:", ""]
                for file in existing_tmp_files:
                    lines.append(f"\t{file}")
                lines.append("")
                lines.append("Please remove them except one to resume downloading.")
                raise DownloadError("\n".join(lines))
            tmp_file = existing_tmp_files[0]
        else:
            resume = False
            # Avoid mkstemp which doesn't work on Windows (#153)
            tmp_file_obj = tempfile.NamedTemporaryFile(
                suffix=".part",
                prefix=osp.basename(output),
                dir=osp.dirname(output),
                delete=False,
            )
            tmp_file = tmp_file_obj.name
            tmp_file_obj.close()
        f = open(tmp_file, "ab")
    else:
        tmp_file = None
        f = output

    if not quiet:
        print(log_messages.get("start", "Downloading...\n"), file=sys.stderr, end="")
        if resume:
            print("Resume:", tmp_file, file=sys.stderr)
        if url_origin == url:
            print("From:", url, file=sys.stderr)
        else:
            print("From (original):", url_origin, file=sys.stderr)
            print("From (redirected):", url, file=sys.stderr)
        print(
            log_messages.get(
                "output",
                f"To: {osp.abspath(output) if isinstance(output, str) else output}\n",
            ),
            file=sys.stderr,
            end="",
        )

    with contextlib.ExitStack() as stack:
        stack.callback(sess.close)
        if tmp_file is not None:
            stack.callback(f.close)

        start_size = f.tell() if tmp_file is not None else 0
        if start_size != 0:
            headers = {"Range": f"bytes={start_size}-"}
            res = sess.get(url, headers=headers, stream=True, verify=verify)

        content_length = _get_content_length_from_response(response=res)
        total = None if content_length is None else content_length + start_size
        expected_size = (
            content_length if _is_content_length_comparable(response=res) else None
        )
        if not quiet:
            pbar = tqdm.tqdm(total=total, unit="B", initial=start_size, unit_scale=True)
            stack.callback(pbar.close)
        t_start = time.time()
        downloaded = 0
        truncation_error: requests.exceptions.ChunkedEncodingError | None = None
        try:
            for chunk in res.iter_content(chunk_size=CHUNK_SIZE):
                f.write(chunk)
                downloaded += len(chunk)
                if not quiet:
                    pbar.update(len(chunk))
                if progress is not None:
                    progress(downloaded + start_size, total)
                if speed is None:
                    continue
                elapsed_time_expected = downloaded / speed
                elapsed_time = time.time() - t_start
                if elapsed_time < elapsed_time_expected:
                    time.sleep(elapsed_time_expected - elapsed_time)
        except requests.exceptions.ChunkedEncodingError as e:
            # Some HTTP client versions enforce Content-Length themselves, so a
            # body that ends early surfaces here rather than as a short read.
            truncation_error = e

    if truncation_error is not None or (
        expected_size is not None and downloaded < expected_size
    ):
        message = f"Download is incomplete: received {downloaded + start_size} bytes"
        if expected_size is not None:
            message += f" but the server announced {total} bytes"
        if tmp_file is not None:
            message += (
                f".\nThe received bytes are kept in {tmp_file}, which resume "
                "(--continue on the command line) picks up"
            )
        raise DownloadError(message + ".") from truncation_error

    if tmp_file is not None:
        assert isinstance(output, str)
        if hash:
            try:
                _assert_filehash(path=tmp_file, hash=hash)
            except AssertionError:
                os.remove(tmp_file)
                raise
        shutil.move(tmp_file, output)
    if isinstance(output, str) and last_modified_time:
        mtime = last_modified_time.timestamp()
        os.utime(output, (mtime, mtime))

    return output
