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


__all__ = [
    'is_supported_id', 'fixup_id',
    'is_expression'
]

from json import load as json_load
from typing import TYPE_CHECKING, Optional

from license_expression import get_spdx_licensing  # type:ignore[import-untyped]

from .schema._res import SPDX_JSON as __SPDX_JSON_SCHEMA

if TYPE_CHECKING:  # pragma: no cover
    from license_expression import Licensing

# region init
# python's internal module loader will assure that this init-part runs only once.

# !!! this requires to ship the actual schema data with the package.
with open(__SPDX_JSON_SCHEMA) as schema:
    __IDS: set[str] = set(json_load(schema).get('enum', []))
assert len(__IDS) > 0, 'known SPDX-IDs should be non-empty set'

__IDS_LOWER_MAP: dict[str, str] = {id_.lower(): id_ for id_ in __IDS}

__SPDX_EXPRESSION_LICENSING: 'Licensing' = get_spdx_licensing()

# endregion


def is_supported_id(value: str) -> bool:
    """Validate SPDX-ID according to current spec."""
    return value in __IDS


def fixup_id(value: str) -> Optional[str]:
    """Fixup SPDX-ID.

    :returns: repaired value string, or `None` if fixup was unable to help.
    """
    return __IDS_LOWER_MAP.get(value.lower())


def is_expression(value: str) -> bool:
    """Validate SPDX license expression.

    .. note::
        Utilizes `license-expression library`_ to
        validate SPDX compound expression according to `SPDX license expression spec`_.

    .. _SPDX license expression spec: https://spdx.github.io/spdx-spec/v3.0.1/annexes/spdx-license-expressions/
    .. _license-expression library: https://github.com/nexB/license-expression
    """
    try:
        res = __SPDX_EXPRESSION_LICENSING.validate(value)
    except Exception:
        # the throw happens when internals crash due to unexpected input characters.
        return False
    return 0 == len(res.errors)
