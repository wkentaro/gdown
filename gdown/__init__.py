#!/usr/bin/env python

import argparse
import os
import os.path as osp
import shutil
import sys
import tempfile

import pkg_resources

import requests

import tqdm


__author__ = 'Kentaro Wada <www.kentaro.wada@gmail.com>'
__version__ = pkg_resources.get_distribution('gdown').version

GDRIVE_TLD = "https://drive.google.com/"
CHUNK_S = 524288  # 512KB


this_dir = osp.dirname(osp.realpath(__file__))


def get_current_state(res):
    state = None

    if res.headers.get('Location'):
        # Final download URL is here!
        state = res.headers.get('Location')
    elif res.headers.get('Set-Cookie'):
        headers = res.headers.get('Set-Cookie')
        header_parts = headers.split(';')
        state = header_parts[0]
    elif res.headers.get('Content-Disposition'):
        headers = res.headers.get('Content-Disposition')
        state = headers

    return state


def get_confirm_cookie(res):
    state_cookie = get_current_state(res)
    cookie = state_cookie.split('=')[1]
    # Looks like: p8lf

    return cookie


def get_gdrive_documenthash(url):
    gdrive_id_pattern = '?id='
    if gdrive_id_pattern in url:
        # Looks like: 0B_NiLAzvehC9R2stRmQyM3ZiVjQ
        return url.split('?id=')[1], True
    else:
        return url, False


def stream_to_stdout(res):
    try:
        for chunk in res.iter_content(chunk_size=CHUNK_S):
            # https://stackoverflow.com/a/908440/457116
            sys.stdout.buffer.write(chunk)
        return
    except requests.exceptions.ChunkedEncodingError as e:
        print(res.headers)
        print(str(e))


def download(url, output, quiet, stream_stdout):
    url_origin = url
    gdoc, is_gdrive_url = get_gdrive_documenthash(url_origin)
    sess = requests.Session()

    with sess.get(url) as res:
        state = get_current_state(res)

        if not is_gdrive_url or 'attachment;filename=' in state:
            if stream_stdout:
                stream_to_stdout(res)
            else:
                with open(output, 'wb') as regular_download:
                    regular_download.write(res.content)
        else:
            cookie = get_confirm_cookie(res)

            if 'download_warning' in state:
                state_confirm = 'uc?export=download&confirm='
                url = "{}{}{}&id={}".format(GDRIVE_TLD, state_confirm,
                                            cookie, gdoc)
                res = sess.get(url, allow_redirects=False)

                state = get_current_state(res)
                cookie = get_confirm_cookie(res)

                if 'googleusercontent' in state:
                    # We got the file Location! Ready to download
                    url = state
                    res = sess.get(url, stream=True)

                if stream_stdout is not None:
                    stream_to_stdout(res)

            if not quiet:
                if not stream_stdout:
                    print('Downloading...')
                    print('From: %s' % url_origin)
                    print('To: %s' % osp.abspath(output))

                else:
                    tmp_file = tempfile.mktemp(
                        suffix=tempfile.template,
                        prefix=osp.basename(output),
                        dir=osp.dirname(output),
                    )

                    try:
                        with open(tmp_file, 'wb') as f:
                            total = res.headers.get('Content-Length')
                            if total is not None:
                                total = int(total)
                            if not quiet:
                                pbar = tqdm.tqdm(total=total, unit='B',
                                                 unit_scale=True)
                            for chunk in res.iter_content(chunk_size=CHUNK_S):
                                f.write(chunk)
                                if not quiet:
                                    pbar.update(len(chunk))
                            if not quiet:
                                pbar.close()
                        shutil.copy(tmp_file, output)
                    except IOError as e:
                        print(e, file=sys.stderr)
                        return
                    finally:
                        try:
                            os.remove(tmp_file)
                        except OSError:
                            pass

                    return output


class _ShowVersionAction(argparse.Action):
    def __init__(self, *args, **kwargs):
        kwargs['nargs'] = 0
        self.version = kwargs.pop('version')
        super(self.__class__, self).__init__(*args, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        print('gdown {ver} at {pos}'
              .format(ver=self.version, pos=this_dir))
        parser.exit()


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-V', '--version', version=__version__,
                        action=_ShowVersionAction, help='display version')
    parser.add_argument(
        'url_or_id', help='url or file id (with --id) to download file from')
    parser.add_argument('-O', '--output', help='output filename')
    parser.add_argument('-s', '--stream_stdout', action='store_true',
                        help='streams the download file directly to \
                              stdout for easy piping')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='suppress standard output')
    parser.add_argument('--id', action='store_true',
                        help='flag to specify file id instead of url')
    args = parser.parse_args()

    if args.id:
        url = 'https://drive.google.com/uc?id={id}'.format(id=args.url_or_id)
    else:
        url = args.url_or_id

    download(
        url=url,
        output=args.output,
        quiet=args.quiet,
        stream_stdout=args.stream_stdout
    )


if __name__ == '__main__':
    main()
