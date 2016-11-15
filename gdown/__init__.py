#!/usr/bin/env python

import argparse
import itertools
import os.path as osp
import pkg_resources
import re
import sys

import requests


__author__ = 'Kentaro Wada <www.kentaro.wada@gmail.com>'
__version__ = pkg_resources.get_distribution('gdown').version


this_dir = osp.dirname(osp.realpath(__file__))


def get_url_from_gdrive_confirmation(contents):
    url = ''
    for line in contents.splitlines():
        m = re.search('href="(\/uc\?export=download[^"]+)', line)
        if m:
            url = 'https://docs.google.com' + m.groups()[0]
            url = url.replace('&amp;', '&')
            return url
        m = re.search('confirm=([^;&]+)', line)
        if m:
            confirm = m.groups()[0]
            url = re.sub(r'confirm=([^;&]+)', r'confirm='+confirm, url)
            return url
        m = re.search('"downloadUrl":"([^"]+)', line)
        if m:
            url = m.groups()[0]
            url = url.replace('\\u003d', '=')
            url = url.replace('\\u0026', '&')
            return url


def _is_google_drive_url(url):
    m = re.match('^https?://drive.google.com/uc\?id=.*$', url)
    return m is not None


def download(url, output, quiet):
    sess = requests.session()

    is_gdrive = _is_google_drive_url(url)

    spinner = itertools.cycle(list('|/-\\'))
    msg = 'Downloading from: {}'.format(url)
    while True:
        if not quiet:
            sys.stdout.write(msg + ' ' + next(spinner))
            sys.stdout.flush()
            sys.stdout.write('\r')

        res = sess.get(url, stream=True)
        if 'Content-Disposition' in res.headers:
            # This is the file
            break
        if not is_gdrive:
            break

        # Need to redirect with confiramtion
        url = get_url_from_gdrive_confirmation(res.text)

    if output is None
        if is_gdrive:
            m = re.search('filename="(.*)"', res.headers['Content-Disposition'])
            output = m.groups()[0]
        else:
            output = osp.basename(url)

    with open(output, 'wb') as f:
        for chunk in res.iter_content(chunk_size=256):
            if not quiet:
                sys.stdout.write(msg + ' ' + next(spinner))
                sys.stdout.flush()
                sys.stdout.write('\r')
            f.write(chunk)

    if not quiet:
        sys.stdout.write('\n')
        sys.stdout.write('Saved as: {}\n'.format(output))


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
    parser = argparse.ArgumentParser()
    parser.add_argument('-V', '--version', version=__version__,
                        action=_ShowVersionAction)
    parser.add_argument('url', help='URL to download file from.')
    parser.add_argument('-O', '--output', default=None,
                        help='Output filename.')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='Suppress standard output.')
    args = parser.parse_args()

    url = args.url
    output = args.output
    quiet = args.quiet

    download(url, output, quiet)


if __name__ == '__main__':
    main()
