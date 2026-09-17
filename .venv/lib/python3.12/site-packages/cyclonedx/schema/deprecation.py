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
CycloneDX Schema Deprecation Warnings
=====================================

This module provides warning classes for deprecated features in CycloneDX schemas.
Each warning class corresponds to a specific schema version, enabling downstream
code to catch, filter, or otherwise handle schema-specific deprecation warnings.

Intended Usage
--------------

Downstream consumers can manage warnings using Python's ``warnings`` module.
Common scenarios include:

- Filtering by schema version
- Suppressing warnings in tests or batch processing
- Logging or reporting deprecation warnings without raising exceptions

Example
-------

.. code-block:: python

    import warnings
    from cyclonedx.schema.deprecation import (
        BaseSchemaDeprecationWarning,
        SchemaDeprecationWarning1Dot7,
    )

    # Suppress all CycloneDX schema deprecation warnings
    warnings.filterwarnings("ignore", category=BaseSchemaDeprecationWarning)

    # Suppress only warnings specific to schema version 1.7
    warnings.filterwarnings("ignore", category=SchemaDeprecationWarning1Dot7)

Notes
-----

- All deprecation warnings inherit from :class:`BaseSchemaDeprecationWarning`.
- The ``SCHEMA_VERSION`` class variable indicates the CycloneDX schema version
  where the feature became deprecated.
- These warning classes are designed for downstream **filtering and logging**,
  not for raising exceptions.
"""


from abc import ABC
from typing import ClassVar, Literal, Optional
from warnings import warn

from . import SchemaVersion

__all__ = [
    'BaseSchemaDeprecationWarning',
    'SchemaDeprecationWarning1Dot1',
    'SchemaDeprecationWarning1Dot2',
    'SchemaDeprecationWarning1Dot3',
    'SchemaDeprecationWarning1Dot4',
    'SchemaDeprecationWarning1Dot5',
    'SchemaDeprecationWarning1Dot6',
    'SchemaDeprecationWarning1Dot7',
]


class BaseSchemaDeprecationWarning(DeprecationWarning, ABC):
    """Base class for warnings about deprecated schema features."""

    SCHEMA_VERSION: ClassVar[SchemaVersion]

    @classmethod
    def _warn(cls, deprecated: str, instead: Optional[str] = None, *, stacklevel: int = 1) -> None:
        """Internal API. Not part of the public interface."""
        msg = f'`{deprecated}` is deprecated from CycloneDX v{cls.SCHEMA_VERSION.to_version()} onwards.'
        if instead:
            msg += f' Please use `{instead}` instead.'
        warn(msg, category=cls, stacklevel=stacklevel + 1)


class SchemaDeprecationWarning1Dot7(BaseSchemaDeprecationWarning):
    """Class for warnings about deprecated schema features in CycloneDX 1.7"""
    SCHEMA_VERSION: ClassVar[Literal[SchemaVersion.V1_7]] = SchemaVersion.V1_7


class SchemaDeprecationWarning1Dot6(BaseSchemaDeprecationWarning):
    """Class for warnings about deprecated schema features in CycloneDX 1.6"""
    SCHEMA_VERSION: ClassVar[Literal[SchemaVersion.V1_6]] = SchemaVersion.V1_6


class SchemaDeprecationWarning1Dot5(BaseSchemaDeprecationWarning):
    """Class for warnings about deprecated schema features in CycloneDX 1.5"""
    SCHEMA_VERSION: ClassVar[Literal[SchemaVersion.V1_5]] = SchemaVersion.V1_5


class SchemaDeprecationWarning1Dot4(BaseSchemaDeprecationWarning):
    """Class for warnings about deprecated schema features in CycloneDX 1.4"""
    SCHEMA_VERSION: ClassVar[Literal[SchemaVersion.V1_4]] = SchemaVersion.V1_4


class SchemaDeprecationWarning1Dot3(BaseSchemaDeprecationWarning):
    """Class for warnings about deprecated schema features in CycloneDX 1.3"""
    SCHEMA_VERSION: ClassVar[Literal[SchemaVersion.V1_3]] = SchemaVersion.V1_3


class SchemaDeprecationWarning1Dot2(BaseSchemaDeprecationWarning):
    """Class for warnings about deprecated schema features in CycloneDX 1.2"""
    SCHEMA_VERSION: ClassVar[Literal[SchemaVersion.V1_2]] = SchemaVersion.V1_2


class SchemaDeprecationWarning1Dot1(BaseSchemaDeprecationWarning):
    """Class for warnings about deprecated schema features in CycloneDX 1.1"""
    SCHEMA_VERSION: ClassVar[Literal[SchemaVersion.V1_1]] = SchemaVersion.V1_1
