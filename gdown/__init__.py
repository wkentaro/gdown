#!/usr/bin/env python3

import argparse
import os
import os.path as osp
import pkg_resources
import shutil
import sys
import tempfile

import requests
import tqdm


__author__ = 'Kentaro Wada <www.kentaro.wada@gmail.com>'
__version__ = pkg_resources.get_distribution('gdown').version

GDRIVE_TLD="https://drive.google.com/"
CHUNK_SIZE = 1048576  # 1MB


this_dir = osp.dirname(osp.realpath(__file__))

def get_current_state(res):
    if res.headers.get('Location'):
        # Final download URL is here!
        state = res.headers.get('Location')
    elif res.headers.get('Set-Cookie'):
        headers = res.headers.get('Set-Cookie')
        header_parts = headers.split(';')
        state = header_parts[0]
        # Looks like: download_warning_13058876669334088843_1cKq-rgSNCYPCUJ38pCi_xy6_PJH-FZWD=p8lf

    return state

def get_confirm_cookie(res):
    state_cookie = get_current_state(res)
    cookie = state_cookie.split('=')[1]
    # Looks like: p8lf

    return cookie

def get_gdrive_documenthash(url):
    return url.split('?id=')[1]
    # Looks like: 0B_NiLAzvehC9R2stRmQyM3ZiVjQ


def download(url, output, quiet, stream_stdout):
    url_origin = url
    gdoc = get_gdrive_documenthash(url_origin)
    sess = requests.Session()

    with sess.get(url) as res:
        state = get_current_state(res)
        cookie = get_confirm_cookie(res)

        if 'download_warning' in state:
            url = "{}uc?export=download&confirm={}&id={}".format(GDRIVE_TLD, cookie, gdoc)
            res = sess.get(url, allow_redirects=False)

            state = get_current_state(res)
            cookie = get_confirm_cookie(res)

            if 'googleusercontent' in state:
                # We got the file Location! Ready to download
                url = state
                res = sess.get(url, stream=True)

            if stream_stdout is not None:
                for chunk in res.iter_content(chunk_size=CHUNK_SIZE):
                # https://stackoverflow.com/a/908440/457116
                    sys.stdout.buffer.write(chunk)
                return

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
                            pbar = tqdm.tqdm(total=total, unit='B', unit_scale=True)
                        for chunk in res.iter_content(chunk_size=CHUNK_SIZE):
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
    parser.add_argument('-s', '--stream_stdout', action='store_true', help='streams the download file directly to stdout for easy piping')
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
