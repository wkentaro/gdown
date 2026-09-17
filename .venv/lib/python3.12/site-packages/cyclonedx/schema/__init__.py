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


from enum import Enum, auto, unique
from typing import Any, TypeVar


@unique
class OutputFormat(Enum):
    """Output formats.

    Cases are hashable.

    Do not rely on the actual/literal values, just use enum cases, like so:
        my_of = OutputFormat.XML
    """

    JSON = auto()
    XML = auto()

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: Any) -> bool:
        return self is other


_SV = TypeVar('_SV', bound='SchemaVersion')


@unique
class SchemaVersion(Enum):
    """
    Schema version.

    Cases are hashable.
    Cases are comparable(!=,>=,>,==,<,<=)

    Do not rely on the actual/literal values, just use enum cases, like so:
        my_sv = SchemaVersion.V1_3
    """

    V1_7 = (1, 7)
    V1_6 = (1, 6)
    V1_5 = (1, 5)
    V1_4 = (1, 4)
    V1_3 = (1, 3)
    V1_2 = (1, 2)
    V1_1 = (1, 1)
    V1_0 = (1, 0)

    @classmethod
    def from_version(cls: type[_SV], version: str) -> _SV:
        """Return instance based of a version string - e.g. `1.4`"""
        return cls(tuple(map(int, version.split('.')))[:2])

    def to_version(self) -> str:
        """Return as a version string - e.g. `1.4`"""
        return '.'.join(map(str, self.value))

    def __ne__(self, other: Any) -> bool:
        if isinstance(other, self.__class__):
            return self.value != other.value
        return NotImplemented  # pragma: no cover

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, self.__class__):
            return self.value < other.value
        return NotImplemented  # pragma: no cover

    def __le__(self, other: Any) -> bool:
        if isinstance(other, self.__class__):
            return self.value <= other.value
        return NotImplemented  # pragma: no cover

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, self.__class__):
            return self.value == other.value
        return NotImplemented  # pragma: no cover

    def __ge__(self, other: Any) -> bool:
        if isinstance(other, self.__class__):
            return self.value >= other.value
        return NotImplemented  # pragma: no cover

    def __gt__(self, other: Any) -> bool:
        if isinstance(other, self.__class__):
            return self.value > other.value
        return NotImplemented  # pragma: no cover

    def __hash__(self) -> int:
        return hash(self.name)
