import datetime
import email.utils
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
from http.cookiejar import MozillaCookieJar
from typing import BinaryIO

import bs4
import requests
import tqdm

from .exceptions import DownloadError
from .exceptions import FileURLRetrievalError
from .parse_url import parse_url

CHUNK_SIZE = 512 * 1024  # 512KB
home = osp.expanduser("~")


def get_url_from_gdrive_confirmation(contents: str) -> str:
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


def _sanitize_filename(filename: str) -> str:
    filename = filename.replace("\x00", "")
    filename = filename.replace("/", "_").replace("\\", "_").strip()
    if filename in ("", ".", ".."):
        return "_"
    return filename


def _get_filename_from_response(response: requests.Response) -> str | None:
    content_disposition = urllib.parse.unquote(response.headers["Content-Disposition"])

    m = re.search(r"filename\*=UTF-8''(.*)", content_disposition)
    if m:
        return _sanitize_filename(filename=m.groups()[0])

    m = re.search('attachment; filename="(.*?)"', content_disposition)
    if m:
        return _sanitize_filename(filename=m.groups()[0])

    return None


def _get_modified_time_from_response(
    response: requests.Response,
) -> datetime.datetime | None:
    if "Last-Modified" not in response.headers:
        return None

    raw = response.headers["Last-Modified"]
    if raw is None:
        return None

    return email.utils.parsedate_to_datetime(raw)


def _get_session(
    proxy: str | None,
    use_cookies: bool,
    user_agent: str,
) -> tuple[requests.Session, str]:
    sess = requests.session()

    sess.headers.update({"User-Agent": user_agent})

    if proxy is not None:
        sess.proxies = {"http": proxy, "https": proxy}
        print("Using proxy:", proxy, file=sys.stderr)

    cookies_file = osp.join(home, ".cache/gdown/cookies.txt")
    if use_cookies and osp.exists(cookies_file):
        cookie_jar = MozillaCookieJar(cookies_file)
        try:
            cookie_jar.load()
            sess.cookies.update(cookie_jar)
        except OSError as e:
            warnings.warn(
                f"Failed to load cookies from {cookies_file}: {e}",
                stacklevel=2,
            )

    return sess, cookies_file


def download(
    url: str | None = None,
    output: str | BinaryIO | None = None,
    quiet: bool = False,
    proxy: str | None = None,
    speed: float | None = None,
    use_cookies: bool = True,
    verify: bool | str = True,
    id: str | None = None,
    resume: bool = False,
    format: str | None = None,
    user_agent: str | None = None,
    log_messages: dict[str, str] | None = None,
    progress: Callable[[int, int | None], None] | None = None,
) -> str | BinaryIO:
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

    Returns
    -------
    output:
        Output filename.

    Raises
    ------
    ValueError
        If neither url nor id is specified, or both are specified.
    FileURLRetrievalError
        If the file URL cannot be retrieved from Google Drive.
    DownloadError
        If the download fails (e.g., multiple temporary files exist during
        resume).
    """
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

    sess, cookies_file = _get_session(
        proxy=proxy,
        use_cookies=use_cookies,
        user_agent=user_agent,
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

        if url == url_origin and res.status_code == 500:
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
            cookie_jar = MozillaCookieJar(cookies_file)
            for cookie in sess.cookies:
                cookie_jar.set_cookie(cookie)
            cookie_jar.save()

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

    if tmp_file is not None and f.tell() != 0:
        start_size = f.tell()
        headers = {"Range": f"bytes={start_size}-"}
        res = sess.get(url, headers=headers, stream=True, verify=verify)
    else:
        start_size = 0

    if not quiet:
        print(log_messages.get("start", "Downloading...\n"), file=sys.stderr, end="")
        if resume:
            print("Resume:", tmp_file, file=sys.stderr)
        if url_origin != url:
            print("From (original):", url_origin, file=sys.stderr)
            print("From (redirected):", url, file=sys.stderr)
        else:
            print("From:", url, file=sys.stderr)
        print(
            log_messages.get(
                "output",
                f"To: {osp.abspath(output) if isinstance(output, str) else output}\n",
            ),
            file=sys.stderr,
            end="",
        )

    try:
        total = res.headers.get("Content-Length")
        if total is not None:
            total = int(total) + start_size
        if not quiet:
            pbar = tqdm.tqdm(total=total, unit="B", initial=start_size, unit_scale=True)
        t_start = time.time()
        downloaded = 0
        for chunk in res.iter_content(chunk_size=CHUNK_SIZE):
            f.write(chunk)
            downloaded += len(chunk)
            if not quiet:
                pbar.update(len(chunk))
            if progress is not None:
                progress(downloaded + start_size, total)
            if speed is not None:
                elapsed_time_expected = downloaded / speed
                elapsed_time = time.time() - t_start
                if elapsed_time < elapsed_time_expected:
                    time.sleep(elapsed_time_expected - elapsed_time)
        if not quiet:
            pbar.close()
        if tmp_file:
            f.close()
            assert isinstance(output, str)
            shutil.move(tmp_file, output)
        if isinstance(output, str) and last_modified_time:
            mtime = last_modified_time.timestamp()
            os.utime(output, (mtime, mtime))
    finally:
        sess.close()

    return output
