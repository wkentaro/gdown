#!/usr/bin/env python

from __future__ import print_function

import distutils.spawn
from setuptools import find_packages
from setuptools import setup
import shlex
import subprocess
import sys

import github2pypi


version = '3.7.3'


if not hasattr(github2pypi, '__file__'):
    print('Please update submodule:\n\n\tgit submodule update --init')
    sys.exit(1)


with open('README.md') as f:
    long_description = github2pypi.replace_url(
        slug='wkentaro/gdown', content=f.read()
    )


if sys.argv[1] == 'release':
    if not distutils.spawn.find_executable('twine'):
        print(
            'Please install twine:\n\n\tpip install twine\n',
            file=sys.stderr,
        )
        sys.exit(1)

    commands = [
        'git pull origin master',
        'git tag v{:s}'.format(version),
        'git push origin master --tag',
        'python setup.py sdist',
        'twine upload dist/gdown-{:s}.tar.gz'.format(version),
    ]
    for cmd in commands:
        subprocess.check_call(shlex.split(cmd))
    sys.exit(0)


setup(
    name='gdown',
    version=version,
    packages=find_packages(),
    install_requires=['filelock', 'requests', 'six', 'tqdm'],
    description='Google Drive direct download of big files.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Kentaro Wada',
    author_email='www.kentaro.wada@gmail.com',
    url='http://github.com/wkentaro/gdown',
    license='MIT',
    keywords='Data Download',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
    ],
    entry_points={'console_scripts': ['gdown=gdown.cli:main']},
)
