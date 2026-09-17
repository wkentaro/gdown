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


from typing import TYPE_CHECKING, Any, Optional

import py_serializable as serializable

from ..exception.serialization import CycloneDxDeserializationException, SerializationOfUnexpectedValueException

if TYPE_CHECKING:  # pragma: no cover
    from typing import TypeVar

    _T_BR = TypeVar('_T_BR', bound='BomRef')


@serializable.serializable_class(ignore_unknown_during_deserialization=True)
class BomRef(serializable.helpers.BaseHelper):
    """
    An identifier that can be used to reference objects elsewhere in the BOM.

    This copies a similar pattern used in the CycloneDX PHP Library.

    .. note::
        See https://github.com/CycloneDX/cyclonedx-php-library/blob/master/docs/dev/decisions/BomDependencyDataModel.md
    """

    def __init__(self, value: Optional[str] = None) -> None:
        self.value = value

    @property
    @serializable.json_name('.')
    @serializable.xml_name('.')
    def value(self) -> Optional[str]:
        return self._value

    @value.setter
    def value(self, value: Optional[str]) -> None:
        # empty strings become `None`
        self._value = value or None

    def __eq__(self, other: object) -> bool:
        return (self is other) or (
            isinstance(other, BomRef)
            # `None` value is not discriminative in this domain
            # see also: `BomRefDiscriminator`
            and other._value is not None
            and self._value is not None
            and other._value == self._value
        )

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, BomRef):
            return str(self) < str(other)
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._value or f'__id__{id(self)}')

    def __repr__(self) -> str:
        return f'<BomRef {self._value!r} id={id(self)}>'

    def __str__(self) -> str:
        return self._value or ''

    def __bool__(self) -> bool:
        return self._value is not None

    # region impl BaseHelper

    @classmethod
    def serialize(cls, o: Any) -> Optional[str]:
        if isinstance(o, cls):
            return o.value
        raise SerializationOfUnexpectedValueException(
            f'Attempt to serialize a non-BomRef: {o!r}')

    @classmethod
    def deserialize(cls: 'type[_T_BR]', o: Any) -> '_T_BR':
        try:
            return cls(value=str(o))
        except ValueError as err:
            raise CycloneDxDeserializationException(
                f'BomRef string supplied does not parse: {o!r}'
            ) from err

    # endregion impl BaseHelper
