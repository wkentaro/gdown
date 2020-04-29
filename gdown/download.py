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


if hasattr(textwrap, "indent"):
    indent_func = textwrap.indent
else:

    def indent_func(text, prefix):
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
            return url
        m = re.search("confirm=([^;&]+)", line)
        if m:
            confirm = m.groups()[0]
            url = re.sub(
                r"confirm=([^;&]+)", r"confirm={}".format(confirm), url
            )
            return url
        m = re.search('"downloadUrl":"([^"]+)', line)
        if m:
            url = m.groups()[0]
            url = url.replace("\\u003d", "=")
            url = url.replace("\\u0026", "&")
            return url
        m = re.search('<p class="uc-error-subcaption">(.*)</p>', line)
        if m:
            error = m.groups()[0]
            raise RuntimeError(error)


def download(
    url, output=None, quiet=False, proxy=None, speed=None, use_cookies=True
):
    """Download file from URL.

    Parameters
    ----------
    url: str
        URL. Google Drive URL is also supported.
    output: str, optional
        Output filename. Default is basename of URL.
    quiet: bool
        Suppress terminal output. Default is False.
    proxy: str
        Proxy.
    speed: float
        Download byte size per second (e.g., 256KB/s = 256 * 1024).
    use_cookies: bool
        Flag to use cookies. Default is True.

    Returns
    -------
    output: str
        Output filename.
    """
    url_origin = url
    sess = requests.session()

    # Load cookies
    cache_dir = osp.join(home, ".cache", "gdown")
    if not osp.exists(cache_dir):
        os.makedirs(cache_dir)
    cookies_file = osp.join(cache_dir, "cookies.json")
    if osp.exists(cookies_file) and use_cookies:
        with open(cookies_file) as f:
            cookies = json.load(f)
        for k, v in cookies:
            sess.cookies[k] = v

    if proxy is not None:
        sess.proxies = {"http": proxy, "https": proxy}
        print("Using proxy:", proxy, file=sys.stderr)

    file_id, is_download_link = parse_url(url)

    while True:

        try:
            res = sess.get(url, stream=True)
        except requests.exceptions.ProxyError as e:
            print("An error has occurred using proxy:", proxy, file=sys.stderr)
            print(e, file=sys.stderr)
            return

        # Save cookies
        with open(cookies_file, "w") as f:
            json.dump(sess.cookies.items(), f, indent=2)

        if "Content-Disposition" in res.headers:
            # This is the file
            break
        if not (file_id and is_download_link):
            break

        # Need to redirect with confirmation
        try:
            url = get_url_from_gdrive_confirmation(res.text)
        except RuntimeError as e:
            print("Access denied with the following error:")
            error = "\n".join(textwrap.wrap(str(e)))
            error = indent_func(error, "\t")
            print("\n", error, "\n", file=sys.stderr)
            print(
                "You may still be able to access the file from the browser:",
                file=sys.stderr,
            )
            print("\n\t", url_origin, "\n", file=sys.stderr)
            return

        if url is None:
            print("Permission denied:", url_origin, file=sys.stderr)
            print(
                "Maybe you need to change permission over "
                "'Anyone with the link'?",
                file=sys.stderr,
            )
            return

    if output is None:
        if file_id and is_download_link:
            m = re.search(
                'filename="(.*)"', res.headers["Content-Disposition"]
            )
            output = m.groups()[0]
        else:
            output = osp.basename(url)

    output_is_path = isinstance(output, six.string_types)

    if not quiet:
        print("Downloading...", file=sys.stderr)
        print("From:", url_origin, file=sys.stderr)
        print(
            "To:",
            osp.abspath(output) if output_is_path else output,
            file=sys.stderr,
        )

    if output_is_path:
        tmp_file = tempfile.mktemp(
            suffix=tempfile.template,
            prefix=osp.basename(output),
            dir=osp.dirname(output),
        )
        f = open(tmp_file, "wb")
    else:
        tmp_file = None
        f = output

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
        try:
            if tmp_file:
                os.remove(tmp_file)
        except OSError:
            pass

    return output
