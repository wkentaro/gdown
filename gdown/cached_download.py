import hashlib
import os
import os.path as osp
import shutil
import sys
import tempfile

import filelock

from .download import download


cache_root = osp.join(osp.expanduser('~'), '.cache/gdown')


def md5sum(file):
    with open(file, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def cached_download(url, path=None, md5=None, quiet=False, postprocess=None):
    if path is None:
        path = url.replace('/', '-SLASH-')\
                  .replace(':', '-COLON-')\
                  .replace('=', '-EQUAL-')\
                  .replace('?', '-QUESTION-')
        path = osp.join(cache_root, path)

    # check existence
    if osp.exists(path) and not md5:
        if not quiet:
            print('[%s] File exists.' % path)
        return path
    elif osp.exists(path) and md5 and md5sum(path) == md5:
        return path

    # download
    lock_path = osp.join(cache_root, '_dl_lock')
    try:
        os.makedirs(osp.dirname(path))
    except OSError:
        pass
    temp_root = tempfile.mkdtemp(dir=cache_root)
    try:
        temp_path = osp.join(temp_root, 'dl')
        download(url, temp_path, quiet=quiet)
        with filelock.FileLock(lock_path):
            shutil.move(temp_path, path)
        if not quiet:
            print('Saved to: {}'.format(path), file=sys.stderr)
    except Exception:
        shutil.rmtree(temp_root)
        raise

    # postprocess
    if postprocess is not None:
        postprocess(path)

    return path
