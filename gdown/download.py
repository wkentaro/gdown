from __future__ import print_function

import json
import os
import os.path as osp
import re
import shutil
import sys
import tempfile
import textwrap
import time

import requests
import six
import tqdm

from .parse_url import parse_url

CHUNK_SIZE = 512 * 1024  # 512KB
home = osp.expanduser("~")


# textwrap.indent for Python2
def indent(text, prefix):
    def prefixed_lines():
        for line in text.splitlines(True):
            yield (prefix + line if line.strip() else line)

    return "".join(prefixed_lines())


def get_url_from_gdrive_confirmation(contents):
    url = ""
    for line in contents.splitlines():
        m = re.search(r'href="(\/uc\?export=download[^"]+)', line)
        if m:
            url = "https://docs.google.com" + m.groups()[0]
            url = url.replace("&amp;", "&")
            break
        m = re.search('id="download-form" action="(.+?)"', line)
        if m:
            url = m.groups()[0]
            url = url.replace("&amp;", "&")
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
            raise RuntimeError(error)
    if not url:
        raise RuntimeError(
            "Cannot retrieve the public link of the file. "
            "You may need to change the permission to "
            "'Anyone with the link', or have had many accesses."
        )
    return url


def _get_session(proxy, use_cookies, return_cookies_file=False):
    sess = requests.session()

    sess.headers.update(
        {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6)"}
    )

    if proxy is not None:
        sess.proxies = {"http": proxy, "https": proxy}
        print("Using proxy:", proxy, file=sys.stderr)

    # Load cookies if exists
    cookies_file = osp.join(home, ".cache/gdown/cookies.json")
    if osp.exists(cookies_file) and use_cookies:
        with open(cookies_file) as f:
            cookies = json.load(f)
        for k, v in cookies:
            sess.cookies[k] = v

    if return_cookies_file:
        return sess, cookies_file
    else:
        return sess


def download(
    url=None,
    output=None,
    quiet=False,
    proxy=None,
    speed=None,
    use_cookies=True,
    verify=True,
    id=None,
    fuzzy=False,
    resume=False,
    format=None,
):
    """Download file from URL.

    Parameters
    ----------
    url: str
        URL. Google Drive URL is also supported.
    output: str
        Output filename. Default is basename of URL.
    quiet: bool
        Suppress terminal output. Default is False.
    proxy: str
        Proxy.
    speed: float
        Download byte size per second (e.g., 256KB/s = 256 * 1024).
    use_cookies: bool
        Flag to use cookies. Default is True.
    verify: bool or string
        Either a bool, in which case it controls whether the server's TLS
        certificate is verified, or a string, in which case it must be a path
        to a CA bundle to use. Default is True.
    id: str
        Google Drive's file ID.
    fuzzy: bool
        Fuzzy extraction of Google Drive's file Id. Default is False.
    resume: bool
        Resume the download from existing tmp file if possible.
        Default is False.
    format: str, optional
        Format of Google Docs, Spreadsheets and Slides. Default is:
            - Google Docs: 'docx'
            - Google Spreadsheet: 'xlsx'
            - Google Slides: 'pptx'

    Returns
    -------
    output: str
        Output filename.
    """
    if not (id is None) ^ (url is None):
        raise ValueError("Either url or id has to be specified")
    if id is not None:
        url = "https://drive.google.com/uc?id={id}".format(id=id)

    url_origin = url

    sess, cookies_file = _get_session(
        proxy=proxy, use_cookies=use_cookies, return_cookies_file=True
    )

    gdrive_file_id, is_gdrive_download_link = parse_url(url, warning=not fuzzy)

    if fuzzy and gdrive_file_id:
        # overwrite the url with fuzzy match of a file id
        url = "https://drive.google.com/uc?id={id}".format(id=gdrive_file_id)
        url_origin = url
        is_gdrive_download_link = True

    while True:
        try:
            res = sess.get(url, stream=True, verify=verify)
        except requests.exceptions.ProxyError as e:
            print(
                "An error has occurred using proxy:",
                sess.proxies,
                file=sys.stderr,
            )
            print(e, file=sys.stderr)
            return

        if url == url_origin and res.status_code == 500:
            # The file could be Google Docs or Spreadsheets.
            url = "https://drive.google.com/open?id={id}".format(
                id=gdrive_file_id
            )
            continue

        if res.headers["Content-Type"].startswith("text/html"):
            m = re.search("<title>(.+)</title>", res.text)
            if m and m.groups()[0].endswith(" - Google Docs"):
                url = (
                    "https://docs.google.com/document/d/{id}/export"
                    "?format={format}".format(
                        id=gdrive_file_id,
                        format="docx" if format is None else format,
                    )
                )
                continue
            elif m and m.groups()[0].endswith(" - Google Sheets"):
                url = (
                    "https://docs.google.com/spreadsheets/d/{id}/export"
                    "?format={format}".format(
                        id=gdrive_file_id,
                        format="xlsx" if format is None else format,
                    )
                )
                continue
            elif m and m.groups()[0].endswith(" - Google Slides"):
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
            if not osp.exists(osp.dirname(cookies_file)):
                os.makedirs(osp.dirname(cookies_file))
            # Save cookies
            with open(cookies_file, "w") as f:
                cookies = [
                    (k, v)
                    for k, v in sess.cookies.items()
                    if not k.startswith("download_warning_")
                ]
                json.dump(cookies, f, indent=2)

        if "Content-Disposition" in res.headers:
            # This is the file
            break
        if not (gdrive_file_id and is_gdrive_download_link):
            break

        # Need to redirect with confirmation
        try:
            url = get_url_from_gdrive_confirmation(res.text)
        except RuntimeError as e:
            print("Access denied with the following error:")
            error = "\n".join(textwrap.wrap(str(e)))
            error = indent(error, "\t")
            print("\n", error, "\n", file=sys.stderr)
            print(
                "You may still be able to access the file from the browser:",
                file=sys.stderr,
            )
            print("\n\t", url_origin, "\n", file=sys.stderr)
            return

    if gdrive_file_id and is_gdrive_download_link:
        content_disposition = six.moves.urllib_parse.unquote(
            res.headers["Content-Disposition"]
        )
        m = re.search(r"filename\*=UTF-8''(.*)", content_disposition)
        filename_from_url = m.groups()[0]
        filename_from_url = filename_from_url.replace(osp.sep, "_")
    else:
        filename_from_url = osp.basename(url)

    if output is None:
        output = filename_from_url

    output_is_path = isinstance(output, six.string_types)
    if output_is_path and output.endswith(osp.sep):
        if not osp.exists(output):
            os.makedirs(output)
        output = osp.join(output, filename_from_url)

    if output_is_path:
        existing_tmp_files = []
        for file in os.listdir(osp.dirname(output) or "."):
            if file.startswith(osp.basename(output)):
                existing_tmp_files.append(osp.join(osp.dirname(output), file))
        if resume and existing_tmp_files:
            if len(existing_tmp_files) != 1:
                print(
                    "There are multiple temporary files to resume:",
                    file=sys.stderr,
                )
                print("\n")
                for file in existing_tmp_files:
                    print("\t", file, file=sys.stderr)
                print("\n")
                print(
                    "Please remove them except one to resume downloading.",
                    file=sys.stderr,
                )
                return
            tmp_file = existing_tmp_files[0]
        else:
            resume = False
            # mkstemp is preferred, but does not work on Windows
            # https://github.com/wkentaro/gdown/issues/153
            tmp_file = tempfile.mktemp(
                suffix=tempfile.template,
                prefix=osp.basename(output),
                dir=osp.dirname(output),
            )
        f = open(tmp_file, "ab")
    else:
        tmp_file = None
        f = output

    if tmp_file is not None and f.tell() != 0:
        headers = {"Range": "bytes={}-".format(f.tell())}
        res = sess.get(url, headers=headers, stream=True, verify=verify)

    if not quiet:
        print("Downloading...", file=sys.stderr)
        if resume:
            print("Resume:", tmp_file, file=sys.stderr)
        if url_origin != url:
            print("From (uriginal):", url_origin, file=sys.stderr)
            print("From (redirected):", url, file=sys.stderr)
        else:
            print("From:", url, file=sys.stderr)
        print(
            "To:",
            osp.abspath(output) if output_is_path else output,
            file=sys.stderr,
        )

    try:
        total = res.headers.get("Content-Length")
        if total is not None:
            total = int(total)
        if not quiet:
            pbar = tqdm.tqdm(total=total, unit="B", unit_scale=True)
        t_start = time.time()
        for chunk in res.iter_content(chunk_size=CHUNK_SIZE):
            f.write(chunk)
            if not quiet:
                pbar.update(len(chunk))
            if speed is not None:
                elapsed_time_expected = 1.0 * pbar.n / speed
                elapsed_time = time.time() - t_start
                if elapsed_time < elapsed_time_expected:
                    time.sleep(elapsed_time_expected - elapsed_time)
        if not quiet:
            pbar.close()
        if tmp_file:
            f.close()
            shutil.move(tmp_file, output)
    except IOError as e:
        print(e, file=sys.stderr)
        return
    finally:
        sess.close()

    return output
