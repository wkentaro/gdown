import collections
import contextlib
import datetime
import email.utils
import hashlib
import os
import os.path as osp
import random
import re
import shutil
import sys
import tempfile
import textwrap
import threading
import time
import urllib.parse
import warnings
from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import Iterator
from dataclasses import dataclass
from dataclasses import field
from http import HTTPStatus
from http.cookiejar import Cookie
from http.cookiejar import MozillaCookieJar
from typing import BinaryIO
from typing import Final
from typing import NoReturn

import bs4
import requests
import tqdm

from ._cancellation import _check_cancelled
from ._cancellation import _configure_cancellation
from ._cancellation import _wait_or_cancel
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
        self._error_message: str | None = None

    @property
    def error_message(self) -> str | None:
        return self._error_message

    def warning(
        self, message: str, /, *, once: bool = False, only_once: bool = False
    ) -> None:
        if (once or only_once) and message in self._seen:
            return
        self._seen.add(message)
        print(f"warning: {message}", file=sys.stderr)

    def error(self, message: str, /, *, is_error: bool = True) -> None:
        if is_error:
            self._error_message = message
        print(f"error: {message}", file=sys.stderr)


def _import_cookies_from_browser(*, browser: str, cookies_file: str) -> int:
    # Imported here so the extractor's probing code loads only when asked for.
    from ._vendor._ytdlp_cookies import CHROMIUM_BASED_BROWSERS  # noqa: PLC0415
    from ._vendor._ytdlp_cookies import extract_cookies_from_browser  # noqa: PLC0415

    logger = _CookieExtractionLogger()
    browser_cookies = [
        cookie
        for cookie in extract_cookies_from_browser(browser, logger=logger)
        if cookie.domain == "google.com" or cookie.domain.endswith(".google.com")
    ]
    # Some keyring backends catch exceptions and fall back to an empty password.
    # A reported error must prevent even apparently decrypted cookies being saved.
    if logger.error_message is not None:
        raise DownloadError(logger.error_message)
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


def _validate_retries(*, retries: int) -> None:
    if type(retries) is not int or retries < 0:
        raise ValueError("retries must be a nonnegative integer")


@dataclass(kw_only=True)
class _RetryState:
    retries: int
    quiet: bool
    cancel: threading.Event | None = None
    attempt: int = field(default=0, init=False)


def _raise_retries_exhausted(*, error: Exception, retries: int) -> NoReturn:
    if retries and isinstance(error, requests.exceptions.RequestException):
        raise DownloadError(
            f"Download failed after {retries} retries: {error}"
        ) from error
    raise error


def _wait_for_retry(*, retry: _RetryState, error: Exception) -> None:
    _check_cancelled(cancel=retry.cancel)
    if isinstance(
        error, (requests.exceptions.SSLError, requests.exceptions.ProxyError)
    ):
        raise error
    if retry.attempt == retry.retries:
        _raise_retries_exhausted(error=error, retries=retry.retries)
    delay = random.uniform(0, min(2 ** min(retry.attempt, 5), 30))
    retry.attempt += 1
    if not retry.quiet:
        print(
            f"Retrying ({retry.attempt}/{retry.retries}) in {delay:.1f}s: {error}",
            file=sys.stderr,
        )
    _wait_or_cancel(seconds=delay, cancel=retry.cancel)


def _get_response_with_retries(
    *,
    sess: requests.Session,
    url: str,
    verify: bool | str,
    timeout: float | tuple[float, float] | None,
    retry: _RetryState,
    headers: dict[str, str] | None,
) -> requests.Response:
    last_error = None
    for _ in range(retry.retries - retry.attempt + 1):
        _check_cancelled(cancel=retry.cancel)
        if last_error is not None:
            _wait_for_retry(retry=retry, error=last_error)
        try:
            return sess.get(
                url,
                headers=headers,
                stream=True,
                verify=verify,
                timeout=timeout,
            )
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.ChunkedEncodingError,
        ) as error:
            if isinstance(
                error, (requests.exceptions.SSLError, requests.exceptions.ProxyError)
            ):
                raise
            last_error = error
    assert last_error is not None
    _raise_retries_exhausted(error=last_error, retries=retry.retries)


def _validate_resumed_response(
    *, response: requests.Response, offset: int, expected_total: int | None
) -> int:
    match = re.fullmatch(
        r"bytes (\d+)-(\d+)/(\d+|\*)", response.headers.get("Content-Range", "")
    )
    # An open-ended resume must cover the remaining file before publication.
    if (
        response.status_code != HTTPStatus.PARTIAL_CONTENT
        or match is None
        or int(match[1]) != offset
        or int(match[2]) < offset
        or (match[3] != "*" and int(match[2]) != int(match[3]) - 1)
        or (expected_total is not None and int(match[2]) != expected_total - 1)
        or not _has_only_identity_encoding(response=response, header="Content-Encoding")
        or (
            _is_content_length_comparable(response=response)
            and (length := _get_content_length_from_response(response=response))
            is not None
            and length != int(match[2]) - offset + 1
        )
    ):
        raise DownloadError(
            "Server did not honor the requested byte range; "
            "the partial file is preserved."
        )
    return int(match[3]) - offset if match[3] != "*" else int(match[2]) - offset + 1


def _get_download_response(
    *,
    sess: requests.Session,
    responses: contextlib.ExitStack,
    url: str,
    gdrive_file_id: str | None,
    format: str | None,
    verify: bool | str,
    timeout: float | tuple[float, float] | None,
    retry: _RetryState,
    use_cookies: bool,
    cookies_file: str,
) -> tuple[requests.Response, str]:
    url_origin = url
    while True:
        responses.close()
        res = _get_response_with_retries(
            sess=sess,
            url=url,
            verify=verify,
            timeout=timeout,
            retry=retry,
            headers=None,
        )
        responses.callback(res.close)

        if not gdrive_file_id:
            return res, url

        if url == url_origin and res.status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
            # The file could be Google Docs or Spreadsheets.
            url = f"https://drive.google.com/open?id={gdrive_file_id}"
            continue

        if res.headers["Content-Type"].startswith("text/html"):
            assert res.url is not None
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
                    f"Failed to save cookies to {cookies_file}: {e}", stacklevel=3
                )

        if "Content-Disposition" in res.headers:
            return res, url

        try:
            contents = res.text
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.ChunkedEncodingError,
        ) as error:
            responses.close()
            _wait_for_retry(retry=retry, error=error)
            continue
        try:
            url = get_url_from_gdrive_confirmation(contents)
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


def _prepare_partial_file(*, output: str, resume: bool) -> tuple[str, bool]:
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
        return existing_tmp_files[0], True
    # Close the temporary file before reopening it for Windows compatibility (#153).
    tmp_file_obj = tempfile.NamedTemporaryFile(
        suffix=".part",
        prefix=osp.basename(output),
        dir=osp.dirname(output),
        delete=False,
    )
    tmp_file = tmp_file_obj.name
    tmp_file_obj.close()
    return tmp_file, False


def _iter_response_chunks(
    *,
    sess: requests.Session,
    res: requests.Response,
    verify: bool | str,
    timeout: float | tuple[float, float] | None,
    retry: _RetryState,
    responses: contextlib.ExitStack,
    url: str,
    tmp_file: str | None,
    start_size: int,
    flush: Callable[[], None],
    pbar: tqdm.tqdm | None,
) -> Iterator[tuple[bytes, int | None]]:
    downloaded = 0
    reconnect = start_size != 0
    expected_total = (
        _get_content_length_from_response(response=res)
        if _is_content_length_comparable(response=res)
        else None
    )
    validator = res.headers.get("ETag")
    if validator is None or validator.startswith("W/"):
        validator = res.headers.get("Last-Modified")
    for _ in range(retry.retries - retry.attempt + 1):
        offset = start_size + downloaded
        range_size = None
        if reconnect:
            headers = {"Range": f"bytes={offset}-"} if offset else None
            if headers is not None and validator:
                # A changed remote file must not be spliced onto old bytes.
                headers["If-Range"] = validator
            responses.close()
            res = _get_response_with_retries(
                sess=sess,
                url=url,
                verify=verify,
                timeout=timeout,
                retry=retry,
                headers=headers,
            )
            responses.callback(res.close)
            if offset:
                range_size = _validate_resumed_response(
                    response=res, offset=offset, expected_total=expected_total
                )
            else:
                res.raise_for_status()

        content_length = (
            range_size
            if range_size is not None
            else _get_content_length_from_response(response=res)
        )
        total = None if content_length is None else content_length + offset
        expected_size = (
            content_length
            if range_size is not None or _is_content_length_comparable(response=res)
            else None
        )
        if expected_size is not None:
            expected_total = total
        if pbar is not None:
            pbar.total = total
        received = 0
        transfer_error: Exception | None = None
        # Exceptions raised by the consumer do not enter this generator,
        # so writes, hashing and caller callbacks cannot trigger a retry.
        try:
            for chunk in res.iter_content(chunk_size=CHUNK_SIZE):
                if expected_size is not None and received + len(chunk) > expected_size:
                    raise DownloadError("Response exceeds the announced byte range")
                received += len(chunk)
                downloaded += len(chunk)
                yield chunk, total
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.ChunkedEncodingError,
        ) as error:
            transfer_error = error

        if isinstance(transfer_error, requests.exceptions.ChunkedEncodingError) or (
            transfer_error is None
            and expected_size is not None
            and received < expected_size
        ):
            message = (
                f"Download is incomplete: received {start_size + downloaded} bytes"
            )
            if expected_size is not None:
                message += f" but the server announced {total} bytes"
            if tmp_file is not None:
                message += (
                    f".\nThe received bytes are kept in {tmp_file}, which resume "
                    "(--continue on the command line) picks up"
                )
            incomplete = DownloadError(message + ".")
            incomplete.__cause__ = transfer_error
            transfer_error = incomplete
        if transfer_error is None:
            return
        responses.close()
        flush()
        _wait_for_retry(retry=retry, error=transfer_error)
        reconnect = True


def _write_response(
    *,
    sess: requests.Session,
    res: requests.Response,
    verify: bool | str,
    timeout: float | tuple[float, float] | None,
    retry: _RetryState,
    responses: contextlib.ExitStack,
    url: str,
    f: BinaryIO,
    tmp_file: str | None,
    start_size: int,
    quiet: bool,
    speed: float | None,
    progress: Callable[[int, int | None], None] | None,
    hasher: "hashlib._Hash | None",
    stack: contextlib.ExitStack,
) -> None:
    pbar = None
    if not quiet:
        pbar = tqdm.tqdm(
            total=_get_content_length_from_response(response=res),
            unit="B",
            initial=start_size,
            unit_scale=True,
        )
        stack.callback(pbar.close)
    t_start = time.time()
    downloaded = 0
    for chunk, total in _iter_response_chunks(
        sess=sess,
        res=res,
        verify=verify,
        timeout=timeout,
        retry=retry,
        responses=responses,
        url=url,
        tmp_file=tmp_file,
        start_size=start_size,
        flush=f.flush,
        pbar=pbar,
    ):
        _check_cancelled(cancel=retry.cancel)
        f.write(chunk)
        if hasher is not None:
            hasher.update(chunk)
        downloaded += len(chunk)
        if pbar is not None:
            pbar.update(len(chunk))
        if progress is not None:
            progress(downloaded + start_size, total)
        if speed is None:
            continue
        elapsed_time_expected = downloaded / speed
        elapsed_time = time.time() - t_start
        if elapsed_time < elapsed_time_expected:
            _wait_or_cancel(
                seconds=elapsed_time_expected - elapsed_time, cancel=retry.cancel
            )


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
    hasher: "hashlib._Hash | None" = None,
    timeout: float | tuple[float, float] | None = None,
    retries: int = 0,
    cancel: threading.Event | None = None,
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
    hasher:
        A hashlib object fed every downloaded byte, so a caller verifying the
        file does not have to read it back afterwards. Bytes already on disk
        from a resumed download are fed to it before the transfer starts.
    timeout:
        Seconds to wait for the server between bytes, either as a single
        value or as a (connect, read) pair, as in requests. Default is None,
        which waits forever.

    retries:
        Additional attempts for transient network failures, per file. Default
        is zero. Retries resume the current transfer; use resume=True to reuse
        earlier partial downloads and skip completed files. Requires a filesystem
        destination. Ignored when skip_download is True.

    cancel:
        Optional threading.Event set by the caller to stop the operation before
        its network timeout. Interrupts response-header and body reads, retry
        backoff, and speed-limit waits. Does not interrupt DNS, connection/TLS
        setup, proxy negotiation, filesystem operations, or caller callbacks.
        An event already set cancels before work. The event is never cleared.
        Partial files remain available for resume; caller-owned streams stay open.
        Once final-file publication starts, a late event does not cancel success.

    Returns
    -------
    output:
        Output filename when downloading. When skip_download is True, a
        GoogleDriveFileToDownload whose path is the resolved Google Drive
        filename.

    Raises
    ------
    ValueError
        If neither url nor id is specified, or both are specified.
    FileURLRetrievalError
        If the file URL cannot be retrieved from Google Drive, or if
        skip_download is True and no Google Drive filename can be resolved.
    DownloadError
        If the download fails (e.g., the response body ends before the
        announced number of bytes, or multiple temporary files exist during
        resume).
    DownloadCancelled
        If cancellation is requested before final-file publication. Not retried.
    """
    _check_cancelled(cancel=cancel)
    _validate_retries(retries=retries)
    if (
        not skip_download
        and retries
        and output is not None
        and not isinstance(output, str)
    ):
        raise ValueError("retries requires a filesystem destination, not a stream")
    if not (id is None) ^ (url is None):
        raise ValueError("Either url or id has to be specified")
    if id is not None:
        url = f"https://drive.google.com/uc?id={id}"
    assert url is not None
    if user_agent is None:
        # We need to use different user agent for file download c.f., folder
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36"  # NOQA: E501
    if log_messages is None:
        log_messages = {}

    url_origin = url

    with contextlib.ExitStack() as stack:
        sess, cookies_file = _get_session(
            proxy=proxy,
            use_cookies=use_cookies,
            user_agent=user_agent,
            cookies_file=cookies_file,
        )

        stack.callback(sess.close)
        _configure_cancellation(session=sess, cancel=cancel)
        retry = _RetryState(
            retries=0 if skip_download else retries,
            quiet=quiet,
            cancel=cancel,
        )
        if not skip_download and (retries or resume):
            # Byte offsets must refer to the bytes written on disk.
            sess.headers["Accept-Encoding"] = "identity"
        responses = stack.enter_context(contextlib.ExitStack())

        gdrive_file_id, is_gdrive_download_link = parse_url(url=url)

        if gdrive_file_id:
            url = f"https://drive.google.com/uc?id={gdrive_file_id}"
            url_origin = url
            is_gdrive_download_link = True

        res, url = _get_download_response(
            sess=sess,
            responses=responses,
            url=url,
            gdrive_file_id=gdrive_file_id,
            format=format,
            verify=verify,
            timeout=timeout,
            retry=retry,
            use_cookies=use_cookies,
            cookies_file=cookies_file,
        )

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

        res.raise_for_status()
        if filename_from_url is None:
            filename_from_url = _sanitize_filename(filename=osp.basename(url))

        if output is None:
            output = filename_from_url

        if isinstance(output, str) and (
            output.endswith(("/", "\\")) or osp.isdir(output)
        ):
            if not osp.exists(output):
                os.makedirs(output)
            output = osp.join(output, filename_from_url)

        if isinstance(output, str):
            if resume and os.path.isfile(output):
                if not quiet:
                    print(f"Skipping already downloaded file {output}", file=sys.stderr)
                return output

            tmp_file, resume = _prepare_partial_file(output=output, resume=resume)
            f = open(tmp_file, "ab")
            stack.callback(f.close)
        else:
            tmp_file = None
            f = output

        if not quiet:
            print(
                log_messages.get("start", "Downloading...\n"), file=sys.stderr, end=""
            )
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
                    "To: "
                    f"{osp.abspath(output) if isinstance(output, str) else output}\n",
                ),
                file=sys.stderr,
                end="",
            )

        start_size = f.tell() if tmp_file is not None else 0
        if hasher is not None and start_size != 0:
            assert tmp_file is not None
            with open(tmp_file, "rb") as resumed:
                for block in iter(lambda: resumed.read(CHUNK_SIZE), b""):
                    hasher.update(block)
        _write_response(
            sess=sess,
            res=res,
            verify=verify,
            timeout=timeout,
            retry=retry,
            responses=responses,
            url=url,
            f=f,
            tmp_file=tmp_file,
            start_size=start_size,
            quiet=quiet,
            speed=speed,
            progress=progress,
            hasher=hasher,
            stack=stack,
        )

    _check_cancelled(cancel=cancel)
    if tmp_file is not None:
        assert isinstance(output, str)
        shutil.move(tmp_file, output)
    if isinstance(output, str) and last_modified_time:
        mtime = last_modified_time.timestamp()
        os.utime(output, (mtime, mtime))

    return output
