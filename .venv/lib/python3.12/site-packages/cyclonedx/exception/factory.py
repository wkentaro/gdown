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
Exceptions relating to specific conditions that occur when factoring a model.

.. deprecated:: next
"""

__all__ = ['CycloneDxFactoryException', 'LicenseChoiceFactoryException',
           'InvalidSpdxLicenseException', 'LicenseFactoryException', 'InvalidLicenseExpressionException']

from ..contrib.license.exceptions import (
    FactoryException as _FactoryException,
    InvalidLicenseExpressionException as _InvalidLicenseExpressionException,
    InvalidSpdxLicenseException as _InvalidSpdxLicenseException,
    LicenseChoiceFactoryException as _LicenseChoiceFactoryException,
    LicenseFactoryException as _LicenseFactoryException,
)

# region deprecated re-export

# re-export NOT as inherited class with @deprecated, to keep the original subclassing intact!!1


CycloneDxFactoryException = _FactoryException
"""Deprecated — Alias of :class:`cyclonedx.contrib.license.exceptions.FactoryException`.

.. deprecated:: next
    This re-export location is deprecated.
    Use ``from cyclonedx.contrib.license.exceptions import FactoryException`` instead.
    The exported symbol itself is NOT deprecated — only this import path.
"""

LicenseChoiceFactoryException = _LicenseChoiceFactoryException
"""Deprecated — Alias of :class:`cyclonedx.contrib.license.exceptions.LicenseChoiceFactoryException`.

.. deprecated:: next
    This re-export location is deprecated.
    Use ``from cyclonedx.contrib.license.exceptions import LicenseChoiceFactoryException`` instead.
    The exported symbol itself is NOT deprecated — only this import path.
"""

InvalidSpdxLicenseException = _InvalidSpdxLicenseException
"""Deprecated — Alias of :class:`cyclonedx.contrib.license.exceptions.InvalidSpdxLicenseException`.

.. deprecated:: next
    This re-export location is deprecated.
    Use ``from cyclonedx.contrib.license.exceptions import InvalidSpdxLicenseException`` instead.
    The exported symbol itself is NOT deprecated — only this import path.
"""

LicenseFactoryException = _LicenseFactoryException
"""Deprecated — Alias of :class:`cyclonedx.contrib.license.exceptions.LicenseFactoryException`.

.. deprecated:: next
    This re-export location is deprecated.
    Use ``from cyclonedx.contrib.license.exceptions import LicenseFactoryException`` instead.
    The exported symbol itself is NOT deprecated — only this import path.
"""

InvalidLicenseExpressionException = _InvalidLicenseExpressionException
"""Deprecated — Alias of :class:`cyclonedx.contrib.license.exceptions.InvalidLicenseExpressionException`.

.. deprecated:: next
    This re-export location is deprecated.
    Use ``from cyclonedx.contrib.license.exceptions import InvalidLicenseExpressionException`` instead.
    The exported symbol itself is NOT deprecated — only this import path.
"""

# endregion deprecated re-export
