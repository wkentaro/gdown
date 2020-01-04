from __future__ import print_function

import argparse
import sys

import pkg_resources
import six

from .download import download


distribution = pkg_resources.get_distribution('gdown')


class _ShowVersionAction(argparse.Action):
    def __init__(self, *args, **kwargs):
        kwargs['nargs'] = 0
        self.version = kwargs.pop('version')
        super(self.__class__, self).__init__(*args, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        print(
            'gdown {ver} at {pos}'.format(
                ver=self.version, pos=distribution.location
            )
        )
        parser.exit()


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '-V',
        '--version',
        version=distribution.version,
        action=_ShowVersionAction,
        help='display version',
    )
    parser.add_argument(
        'url_or_id', help='url or file id (with --id) to download file from'
    )
    parser.add_argument('-O', '--output', help='output filename')
    parser.add_argument(
        '-q', '--quiet', action='store_true', help='suppress standard output'
    )
    parser.add_argument(
        '--id',
        action='store_true',
        help='flag to specify file id instead of url',
    )
    parser.add_argument(
        '--proxy',
        help='<protocol://host:port> download using the specified proxy',
    )

    args = parser.parse_args()

    if args.output == '-':
        if six.PY3:
            args.output = sys.stdout.buffer
        else:
            args.output = sys.stdout

    if args.id:
        url = 'https://drive.google.com/uc?id={id}'.format(id=args.url_or_id)
    else:
        url = args.url_or_id

    download(url=url, output=args.output, quiet=args.quiet, proxy=args.proxy)


if __name__ == '__main__':
    main()
