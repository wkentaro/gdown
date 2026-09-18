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

import django_filters


class PackageURLFilter(django_filters.CharFilter):
    """
    Filter by an exact Package URL string.

    The special "EMPTY" value allows retrieval of objects with an empty Package URL.

    This filter depends on `for_package_url` and `empty_package_url`
    methods to be available on the Model Manager,
    see for example `PackageURLQuerySetMixin`.

    When exact_match_only is True, the filter will match only exact Package URL strings.
    """

    is_empty = "EMPTY"
    exact_match_only = False
    help_text = (
        'Match Package URL. Use "EMPTY" as value to retrieve objects with empty Package URL.'
    )

    def __init__(self, *args, **kwargs):
        self.exact_match_only = kwargs.pop("exact_match_only", False)
        kwargs.setdefault("help_text", self.help_text)
        super().__init__(*args, **kwargs)

    def filter(self, qs, value):
        none_values = ([], (), {}, "", None)
        if value in none_values:
            return qs

        if self.distinct:
            qs = qs.distinct()

        if value == self.is_empty:
            return qs.empty_package_url()

        return qs.for_package_url(value, exact_match=self.exact_match_only)
