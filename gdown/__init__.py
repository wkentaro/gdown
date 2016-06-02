#!/usr/bin/env python

from __future__ import unicode_literals
import argparse
import codecs
import os
import pkg_resources
import re
import subprocess
import sys
import tempfile
try:
    from urlparse import urlparse
    from urlparse import parse_qs
except ImportError:
    from urllib.parse import urlparse
    from urllib.parse import parse_qs


__author__ = 'Kentaro Wada <www.kentaro.wada@gmail.com>'
__version__ = pkg_resources.get_distribution('gdown').version


this_dir = os.path.dirname(os.path.realpath(__file__))


def wget_download(url, filename, be_quiet):
    tmp_file = tempfile.mktemp()
    cmd = 'wget --load-cookie /tmp/{tmp_file}'
    if be_quiet:
        cmd += ' --quiet'
    cmd += ' --save-cookie /tmp/{tmp_file} "{url}"'
    cmd = cmd.format(tmp_file=tmp_file, url=url)
    if filename:
        cmd += ' -O {fname}'.format(fname=filename)
    subprocess.call(cmd, shell=True)


def main():
    class ShowVersionAction(argparse.Action):
        def __init__(self, *args, **kwargs):
            kwargs['nargs'] = 0
            self.version = kwargs.pop('version')
            super(self.__class__, self).__init__(*args, **kwargs)

        def __call__(self, parser, namespace, values, option_string=None):
            print('gdown {ver} at {pos}'.format(ver=self.version, pos=this_dir))
            parser.exit()

    parser = argparse.ArgumentParser()
    parser.add_argument('-V', '--version', version=__version__, action=ShowVersionAction)
    parser.add_argument('url')
    parser.add_argument('-O', '--output', default=None)
    parser.add_argument('-q', '--quiet', action='store_true')
    args = parser.parse_args()

    url = args.url
    filename = args.output
    be_quiet = args.quiet
    if filename is None:
        query = urlparse(url).query
        filename = parse_qs(query)['id'][0]

    wget_download(url, filename, be_quiet)

    while os.stat(filename).st_size < 100000:
        with codecs.open(filename, 'r', encoding='latin-1') as f:
            for line in f.readlines():
                m = re.search('href="(\/uc\?export=download[^"]+)', line)
                if m:
                    url = 'https://docs.google.com' + m.groups()[0]
                    url = url.replace('&amp;', '&')
                    confirm = ''
                    break
                m = re.search('confirm=([^;&]+)', line)
                if m:
                    confirm = m.groups()[0]
                    break
                m = re.search('"downloadUrl":"([^"]+)', line)
                if m:
                    url = m.groups()[0]
                    url = url.replace('\\u003d', '=')
                    url = url.replace('\\u0026', '&')
                    confirm = ''
                    break
            else:
                print('Small size file or invalid url.')
                quit()

        if confirm:
            url = re.sub(r'confirm=([^;&]+)', r'confirm='+confirm, url)

        wget_download(url=url, filename=filename, be_quiet=be_quiet)


if __name__ == '__main__':
    main()
