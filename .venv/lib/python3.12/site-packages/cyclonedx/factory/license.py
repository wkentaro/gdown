# This file is part of CycloneDX Python Library
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) OWASP Foundation. All Rights Reserved.

"""
.. deprecated:: next
"""

__all__ = ['LicenseFactory']

import sys

if sys.version_info >= (3, 13):
    from warnings import deprecated
else:
    from typing_extensions import deprecated

from ..contrib.license.factories import LicenseFactory as _LicenseFactory

# region deprecated re-export


@deprecated('Deprecated re-export location - see docstring of "LicenseFactory" for details.')
class LicenseFactory(_LicenseFactory):
    """Deprecated — Alias of :class:`cyclonedx.contrib.license.factories.LicenseFactory`.

    .. deprecated:: next
        This re-export location is deprecated.
        Use ``from cyclonedx.contrib.license.factories import LicenseFactory`` instead.
        The exported symbol itself is NOT deprecated — only this import path.
    """
    pass

# endregion deprecated re-export
