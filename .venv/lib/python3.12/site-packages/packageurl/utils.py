# -*- coding: utf-8 -*-
#
# Copyright (c) the purl authors
# SPDX-License-Identifier: MIT
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# Visit https://github.com/package-url/packageurl-python for support and
# download.

from typing import Optional
from typing import Union

from packageurl import PackageURL


def get_golang_purl(go_package: str):
    """
    Return a PackageURL object given an imported ``go_package``
    or go module "name version" string as seen in a go.mod file.
    >>> get_golang_purl(go_package="github.com/gorilla/mux v1.8.1")
    PackageURL(type='golang', namespace='github.com/gorilla', name='mux', version='v1.8.1', qualifiers={}, subpath=None)
    """
    if not go_package:
        return
    version = None
    # Go package in *.mod files is represented like this
    # package version
    # github.com/gorilla/mux v1.8.1
    # https://github.com/moby/moby/blob/6c10086976d07d4746e03dcfd188972a2f07e1c9/vendor.mod#L51
    if "@" in go_package:
        raise Exception(f"{go_package} should not contain ``@``")
    if " " in go_package:
        go_package, _, version = go_package.rpartition(" ")
    parts = go_package.split("/")
    if not parts:
        return
    name = parts[-1]
    namespace = "/".join(parts[:-1])
    return PackageURL(type="golang", namespace=namespace, name=name, version=version)


def ensure_str(value: Optional[Union[str, bytes]]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8")  # or whatever encoding is right
    return value
