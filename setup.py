#!/usr/bin/env python

from __future__ import print_function

from setuptools import find_packages
from setuptools import setup
import shlex
import subprocess
import sys


version = '3.4.4'


# release helper
if sys.argv[-1] == 'release':
    commands = [
        'python setup.py sdist',
        'twine upload dist/gdown-{0}.tar.gz'.format(version),
        'git tag v{0}'.format(version),
        'git push origin master --tag',
    ]
    for cmd in commands:
        subprocess.call(shlex.split(cmd))
    sys.exit(0)

setup(
    name='gdown',
    version=version,
    packages=find_packages(),
    install_requires=['requests', 'tqdm'],
    description='Google Drive direct download of big files.',
    long_description=open('README.md').read(),
    author='Kentaro Wada',
    author_email='www.kentaro.wada@gmail.com',
    url='http://github.com/wkentaro/gdown',
    license='MIT',
    keywords='utility',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX',
        'Topic :: Internet :: WWW/HTTP',
        ],
    scripts=['scripts/gdown'],
)
